import {
  WORKFLOW_CONTRACT_VERSION,
  type WorkflowDefinition,
  type WorkflowRunRequest,
  type WorkflowRunResponse,
  type WorkflowSession,
  type WorkflowStepRequest,
  type WorkflowStepResponse,
  type WorkflowTraceExport,
} from '../types/workflow';
import type {
  DefinitionDescriptor,
  DefinitionDiagnostic,
  DefinitionPreviewResult,
  DefinitionSimulationResult,
  WorkerEnvelope,
} from '../types/definition';
import { isDefinitionCapability, normalizeDefinitionDescriptor } from '../types/definition';
import { redactUnknown } from '../lib/redaction';
import { FORM_CONTRACT_VERSION, type FormPackage, type RemoteFormPackageResponse } from '../types/form';
import type { OverlayComposeResult } from '../types/overlay';

const KNOWN_RUNTIME_ERROR_CODES = new Set([
  'INVALID_TRANSITION',
  'GUARD_FAILED',
  'AUTHZ_DENIED',
  'NO_INITIAL_STATE',
  'UNKNOWN_STATE',
  'WORKFLOW_EXECUTION_FAILED',
  'MANIFEST_INVALID_SHAPE',
  'MANIFEST_PARSE_ERROR',
  'POLICY_EVAL_FAILED',
  'ACTIVE_ARTIFACT_REQUIRED',
  'ARTIFACT_NOT_FOUND',
  'TENANT_MISMATCH',
  'FORBIDDEN',
  'E_FORM_ACTOR_TOO_LARGE',
  'E_FORM_DATA_TOO_LARGE',
  'E_FORM_DSL_TOO_LARGE',
  'E_FORM_EXPR_FAILED',
  'E_FORM_TIMEOUT',
]);

class RemoteRuntimeError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, message: string, retryable: boolean) {
    super(message);
    this.code = code;
    this.retryable = retryable;
  }
}

function mapRemoteFormPackageResponse(response: RemoteFormPackageResponse): FormPackage {
  return {
    formContractVersion: response.form_contract_version ?? FORM_CONTRACT_VERSION,
    jsonSchema: (response.json_schema ?? {}) as any,
    uiSchema: (response.ui_schema ?? {}) as any,
    fieldState: (response.field_state ?? []) as any,
    validation: (response.validation ?? { valid: true, errors: [] }) as any,
  };
}

interface RuntimeSourceOptions {
  dsl: string;
  artifactId?: string;
  useTenantActiveManifest?: boolean;
}

export interface WorkerRuntimeMetrics {
  contractVersion: string;
  requestId: string;
  type: string;
  timestamp: string;
  durationMs?: number;
  diagnosticCount: number;
}

export interface RuleArtifactSummary {
  id: string;
  tenant_id: string;
  status: string;
  version: number;
  checksum: string;
  created_at: string;
}

export interface RuleArtifactDetail extends RuleArtifactSummary {
  manifest_text: string;
  signature?: string | null;
}

export class MPCEngine {
  private worker: Worker;
  private pendingRequests: Map<string, { resolve: (value: unknown) => void; reject: (reason?: unknown) => void }> = new Map();
  private remoteFailures = 0;
  private circuitOpenedAt: number | null = null;
  private lastWorkerEnvelope: WorkerRuntimeMetrics | null = null;
  private lastWorkerDiagnostics: DefinitionDiagnostic[] = [];

  constructor() {
    this.worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
    this.worker.onmessage = this.handleMessage.bind(this);
  }

  private handleMessage(e: MessageEvent) {
    const { id, type, payload } = e.data;
    const request = this.pendingRequests.get(id);
    
    if (request) {
      if (type === 'ERROR') {
        request.reject(payload);
      } else {
        request.resolve(payload);
      }
      this.pendingRequests.delete(id);
    }
  }

  private postMessage<T>(message: { type: string; payload: any }): Promise<T> {
    const id = Math.random().toString(36).substring(7);
    return new Promise<T>((resolve, reject) => {
      this.pendingRequests.set(id, { 
        resolve: (val: any) => resolve(val as T), 
        reject 
      });
      this.worker.postMessage({ id, ...message });
    });
  }

  private isWorkerEnvelope<TPayload>(value: unknown): value is WorkerEnvelope<TPayload> {
    if (!value || typeof value !== 'object') return false;
    const candidate = value as Partial<WorkerEnvelope<TPayload>>;
    return (
      typeof candidate.contractVersion === 'string' &&
      typeof candidate.requestId === 'string' &&
      typeof candidate.timestamp === 'string' &&
      typeof candidate.type === 'string' &&
      'payload' in candidate
    );
  }

  private unwrapEnvelopePayload<TPayload>(value: unknown): TPayload {
    if (this.isWorkerEnvelope<TPayload>(value)) {
      this.lastWorkerEnvelope = {
        contractVersion: value.contractVersion,
        requestId: value.requestId,
        type: value.type,
        timestamp: value.timestamp,
        durationMs: value.durationMs,
        diagnosticCount: value.diagnostics?.length ?? 0,
      };
      this.lastWorkerDiagnostics = Array.isArray(value.diagnostics) ? value.diagnostics : [];
      return value.payload;
    }
    return value as TPayload;
  }

  getLastWorkerMetrics(): WorkerRuntimeMetrics | null {
    return this.lastWorkerEnvelope;
  }

  getLastWorkerDiagnostics(): DefinitionDiagnostic[] {
    return this.lastWorkerDiagnostics.slice();
  }

  private runtimeMode(): 'local' | 'remote' {
    const configured = String(import.meta.env.VITE_MPC_RUNTIME_MODE ?? 'local').toLowerCase().trim();
    return configured === 'remote' ? 'remote' : 'local';
  }

  private runtimeBaseUrl(): string {
    const configured = String(import.meta.env.VITE_MPC_RUNTIME_BASE_URL ?? '').trim();
    if (configured) {
      return configured.replace(/\/+$/, '');
    }
    return '/api/v1/rule-artifacts';
  }

  private isCircuitOpen(): boolean {
    if (this.circuitOpenedAt === null) return false;
    const cooldownMs = Number(import.meta.env.VITE_MPC_RUNTIME_CIRCUIT_COOLDOWN_MS ?? 10_000);
    if (Date.now() - this.circuitOpenedAt > cooldownMs) {
      this.circuitOpenedAt = null;
      this.remoteFailures = 0;
      return false;
    }
    return true;
  }

  private noteRemoteFailure() {
    this.remoteFailures += 1;
    const failureThreshold = Number(import.meta.env.VITE_MPC_RUNTIME_CIRCUIT_THRESHOLD ?? 3);
    if (this.remoteFailures >= failureThreshold) {
      this.circuitOpenedAt = Date.now();
    }
  }

  private noteRemoteSuccess() {
    this.remoteFailures = 0;
    this.circuitOpenedAt = null;
  }

  private createIdempotencyKey(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return `idem-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }

  private async postRemote<T>(path: string, payload: unknown): Promise<T> {
    const maxRetries = Number(import.meta.env.VITE_MPC_RUNTIME_RETRY_ATTEMPTS ?? 2);
    let attempt = 0;
    const url = `${this.runtimeBaseUrl()}${path}`;
    const csrfCookieName = String(import.meta.env.VITE_MPC_CSRF_COOKIE_NAME ?? 'servera_csrf_token');
    const csrfHeaderName = String(import.meta.env.VITE_MPC_CSRF_HEADER_NAME ?? 'X-CSRF-Token');
    const csrfToken = this.readCookie(csrfCookieName);
    while (attempt <= maxRetries) {
      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          'Idempotency-Key': this.createIdempotencyKey(),
        };
        const tenantHeader = (payload as { tenant_id?: string })?.tenant_id;
        if (tenantHeader) {
          headers['X-Tenant-Id'] = tenantHeader;
        }
        if (csrfToken) {
          headers[csrfHeaderName] = csrfToken;
        }
        const response = await fetch(url, {
          method: 'POST',
          credentials: 'include',
          headers,
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          const body = (await response.json().catch(() => ({}))) as {
            code?: string;
            message?: string;
            detail?: { code?: string; message?: string };
            retryable?: boolean;
          };
          const code = body?.code || body?.detail?.code || `REMOTE_RUNTIME_${response.status}`;
          const message = body?.message || body?.detail?.message || code;
          throw new RemoteRuntimeError(code, message, Boolean(body?.retryable) || response.status >= 500);
        }
        const data = (await response.json()) as T;
        this.noteRemoteSuccess();
        return data;
      } catch (error) {
        attempt += 1;
        this.noteRemoteFailure();
        if (
          error instanceof RemoteRuntimeError &&
          (!error.retryable || KNOWN_RUNTIME_ERROR_CODES.has(error.code))
        ) {
          throw error;
        }
        if (attempt > maxRetries) {
          throw error;
        }
      }
    }
    throw new Error('REMOTE_RUNTIME_FAILED');
  }

  private async putRemote<T>(path: string, payload: unknown): Promise<T> {
    const url = `${this.runtimeBaseUrl()}${path}`;
    const csrfCookieName = String(import.meta.env.VITE_MPC_CSRF_COOKIE_NAME ?? 'servera_csrf_token');
    const csrfHeaderName = String(import.meta.env.VITE_MPC_CSRF_HEADER_NAME ?? 'X-CSRF-Token');
    const csrfToken = this.readCookie(csrfCookieName);
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Idempotency-Key': this.createIdempotencyKey(),
    };
    const tenantHeader = (payload as { tenant_id?: string })?.tenant_id;
    if (tenantHeader) {
      headers['X-Tenant-Id'] = tenantHeader;
    }
    if (csrfToken) {
      headers[csrfHeaderName] = csrfToken;
    }
    const response = await fetch(url, {
      method: 'PUT',
      credentials: 'include',
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as { detail?: { message?: string }; message?: string };
      throw new Error(body?.detail?.message || body?.message || `REMOTE_RUNTIME_${response.status}`);
    }
    return (await response.json()) as T;
  }

  private readCookie(name: string): string | null {
    if (typeof document === 'undefined' || !document.cookie) {
      return null;
    }
    const target = `${encodeURIComponent(name)}=`;
    const parts = document.cookie.split(';');
    for (const part of parts) {
      const value = part.trim();
      if (value.startsWith(target)) {
        return decodeURIComponent(value.slice(target.length));
      }
    }
    return null;
  }

  private buildRuntimeSource(options: RuntimeSourceOptions): { manifest_text?: string; artifact_id?: string } {
    if (options.artifactId) {
      return { artifact_id: options.artifactId };
    }
    if (options.useTenantActiveManifest) {
      return {};
    }
    return { manifest_text: options.dsl };
  }

  private async getRemote<T>(path: string, tenantId: string): Promise<T> {
    const url = new URL(`${this.runtimeBaseUrl()}${path}`, window.location.origin);
    url.searchParams.set('tenant_id', tenantId);
    const response = await fetch(url.toString(), {
      method: 'GET',
      credentials: 'include',
      headers: {
        'X-Tenant-Id': tenantId,
      },
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as { detail?: { message?: string }; message?: string };
      throw new Error(body?.detail?.message || body?.message || `REMOTE_RUNTIME_${response.status}`);
    }
    return (await response.json()) as T;
  }

  private async workflowStepRemote(payload: WorkflowStepRequest): Promise<WorkflowStepResponse> {
    const response = await this.postRemote<{
      initial_state: string;
      current_state: string;
      step: {
        step_id: string;
        event: string;
        from: string;
        to: string;
        allow: boolean;
        guard_result: 'pass' | 'fail' | 'not_applicable';
        reasons: Array<{ code: string; summary?: string | null }>;
        errors: Array<{ code: string; message: string }>;
        actions_executed: string[];
        error_code?: string;
        remediation_hint?: string;
        timestamp: string;
      };
      available_transitions: Array<{ from: string; event: string; to: string; guard?: string | null }>;
    }>('/runtime/workflow/step', {
      tenant_id: payload.tenantId,
      source: this.buildRuntimeSource({
        dsl: payload.dsl,
        artifactId: payload.artifactId,
        useTenantActiveManifest: payload.useTenantActiveManifest,
      }),
      workflow_id: payload.workflowId,
      event: payload.event,
      current_state: payload.currentState,
      initial_state: payload.initialState,
    });
    return {
      initialState: response.initial_state,
      currentState: response.current_state,
      step: {
        stepId: response.step.step_id,
        event: response.step.event,
        from: response.step.from,
        to: response.step.to,
        allow: response.step.allow,
        guardResult: response.step.guard_result,
        reasons: response.step.reasons,
        errors: response.step.errors,
        actionsExecuted: response.step.actions_executed,
        errorCode: response.step.error_code,
        remediationHint: response.step.remediation_hint,
        timestamp: response.step.timestamp,
      },
      availableTransitions: response.available_transitions,
    };
  }

  private async workflowRunRemote(payload: WorkflowRunRequest): Promise<WorkflowRunResponse> {
    const response = await this.postRemote<{
      initial_state: string;
      current_state: string;
      steps: Array<{
        step_id: string;
        event: string;
        from: string;
        to: string;
        allow: boolean;
        guard_result: 'pass' | 'fail' | 'not_applicable';
        reasons: Array<{ code: string; summary?: string | null }>;
        errors: Array<{ code: string; message: string }>;
        actions_executed: string[];
        error_code?: string;
        remediation_hint?: string;
        timestamp: string;
      }>;
      available_transitions: Array<{ from: string; event: string; to: string; guard?: string | null }>;
    }>('/runtime/workflow/run', {
      tenant_id: payload.tenantId,
      source: this.buildRuntimeSource({
        dsl: payload.dsl,
        artifactId: payload.artifactId,
        useTenantActiveManifest: payload.useTenantActiveManifest,
      }),
      workflow_id: payload.workflowId,
      events: payload.events,
      initial_state: payload.initialState,
    });
    return {
      initialState: response.initial_state,
      currentState: response.current_state,
      steps: response.steps.map((step) => ({
        stepId: step.step_id,
        event: step.event,
        from: step.from,
        to: step.to,
        allow: step.allow,
        guardResult: step.guard_result,
        reasons: step.reasons,
        errors: step.errors,
        actionsExecuted: step.actions_executed,
        errorCode: step.error_code,
        remediationHint: step.remediation_hint,
        timestamp: step.timestamp,
      })),
      availableTransitions: response.available_transitions,
    };
  }

  async parseAndValidate(dsl: string): Promise<unknown> {
    return this.postMessage<unknown>({ type: 'PARSE_AND_VALIDATE', payload: dsl });
  }

  async getMermaid(dsl: string, workflowId?: string): Promise<string> {
    const preview = await this.previewDefinition({
      dsl,
      definitionId: workflowId,
      kindHint: 'Workflow',
    });
    return preview.renderer === 'mermaid' ? preview.content : '';
  }

  async listDefinitions(dsl: string): Promise<DefinitionDescriptor[]> {
    const response = await this.postMessage<unknown>({
      type: 'LIST_DEFINITIONS',
      payload: { dsl },
    });
    const payload = this.unwrapEnvelopePayload<{ items?: unknown[]; diagnostics?: DefinitionDiagnostic[] }>(response);
    const diagnostics = payload.diagnostics ?? [];
    return (payload.items ?? []).map((item) => {
      const descriptor = normalizeDefinitionDescriptor(item);
      const rawCaps =
        item && typeof item === 'object' && Array.isArray((item as { capabilities?: unknown }).capabilities)
          ? ((item as { capabilities: unknown[] }).capabilities.filter(
              (capability): capability is string => typeof capability === 'string',
            ) as string[])
          : [];
      const unsupported = rawCaps
        .filter((capability) => !isDefinitionCapability(capability))
        .map<DefinitionDiagnostic>((capability) => ({
          code: 'UNKNOWN_CAPABILITY',
          message: `Definition '${descriptor.id}' has unsupported capability '${capability}'.`,
          severity: 'warning',
        }));
      const related = diagnostics.filter((diagnostic) => diagnostic.message.includes(descriptor.id));
      return {
        ...descriptor,
        diagnostics: [...descriptor.diagnostics, ...related, ...unsupported],
      };
    });
  }

  async previewDefinition(payload: { dsl: string; definitionId?: string; kindHint?: string }): Promise<DefinitionPreviewResult> {
    const response = await this.postMessage<unknown>({
      type: 'PREVIEW_DEFINITION',
      payload,
    });
    return this.unwrapEnvelopePayload<DefinitionPreviewResult>(response);
  }

  async simulateDefinition(payload: {
    dsl: string;
    definitionId?: string;
    kindHint?: string;
    input?: unknown;
  }): Promise<DefinitionSimulationResult> {
    const response = await this.postMessage<unknown>({
      type: 'SIMULATE_DEFINITION',
      payload,
    });
    return this.unwrapEnvelopePayload<DefinitionSimulationResult>(response);
  }

  async listWorkflows(dsl: string): Promise<WorkflowDefinition[]> {
    const definitions = await this.listDefinitions(dsl);
    return definitions
      .filter((definition) => definition.kind === 'Workflow')
      .map((definition) => ({
        id: definition.id,
        name: definition.name,
        kind: definition.kind,
      }));
  }

  async listFormsForState(dsl: string, workflowState: string): Promise<Array<{ id: string; title?: string | null }>> {
    const local = await this.postMessage<unknown>({
      type: 'LIST_FORMS_FOR_STATE',
      payload: { dsl, workflowState },
    });
    return this.unwrapEnvelopePayload<Array<{ id: string; title?: string | null }>>(local);
  }

  async evaluateExpr(expr: string, context?: any, enableTrace: boolean = false): Promise<any> {
    return this.postMessage<any>({ 
      type: 'EVALUATE_EXPR', 
      payload: { expr, context, enable_trace: enableTrace } 
    });
  }

  async evaluatePolicy(
    dsl: string,
    event: any,
    options?: { tenantId?: string; artifactId?: string; useTenantActiveManifest?: boolean },
  ): Promise<any> {
    const enrichedEvent =
      options?.tenantId && !(event as { tenantId?: string })?.tenantId
        ? { ...event, tenantId: options.tenantId }
        : event;
    if (this.runtimeMode() === 'remote' && !this.isCircuitOpen()) {
      try {
        return await this.postRemote('/runtime/policy/evaluate', {
          tenant_id:
            options?.tenantId ||
            String((enrichedEvent as { tenantId?: string })?.tenantId ?? '') ||
            undefined,
          source: this.buildRuntimeSource({
            dsl,
            artifactId: options?.artifactId,
            useTenantActiveManifest: options?.useTenantActiveManifest,
          }),
          event: enrichedEvent,
        });
      } catch (error) {
        if (error instanceof RemoteRuntimeError && KNOWN_RUNTIME_ERROR_CODES.has(error.code)) {
          throw error;
        }
        // Fail closed to local runtime fallback so Studio remains usable offline.
      }
    }
    return this.postMessage<any>({
      type: 'EVALUATE_POLICY',
      payload: { dsl, event: enrichedEvent }
    });
  }

  async generateUISchema(dsl: string): Promise<any> {
    return this.postMessage<any>({
      type: 'GENERATE_UISCHEMA',
      payload: { dsl }
    });
  }

  async generateFormPackage(input: {
    dsl: string;
    formId: string;
    data?: Record<string, unknown>;
    actorRoles?: string[];
    actorAttrs?: Record<string, unknown>;
    tenantId?: string;
    artifactId?: string;
    useTenantActiveManifest?: boolean;
  }): Promise<FormPackage> {
    if (this.runtimeMode() === 'remote' && !this.isCircuitOpen()) {
      try {
        const response = await this.postRemote<RemoteFormPackageResponse>('/runtime/forms/package', {
          tenant_id: input.tenantId,
          source: this.buildRuntimeSource({
            dsl: input.dsl,
            artifactId: input.artifactId,
            useTenantActiveManifest: input.useTenantActiveManifest,
          }),
          form_id: input.formId,
          data: input.data ?? {},
          actor_roles: input.actorRoles ?? [],
          actor_attrs: input.actorAttrs ?? {},
        });

        return mapRemoteFormPackageResponse(response);
      } catch (error) {
        if (error instanceof RemoteRuntimeError && KNOWN_RUNTIME_ERROR_CODES.has(error.code)) {
          throw error;
        }
        // Fall back to local worker when remote runtime is unavailable.
      }
    }

    const local = await this.postMessage<unknown>({
      type: 'GENERATE_FORM_PACKAGE',
      payload: {
        dsl: input.dsl,
        formId: input.formId,
        data: input.data ?? {},
        actorRoles: input.actorRoles ?? [],
        actorAttrs: input.actorAttrs ?? {},
      },
    });
    return this.unwrapEnvelopePayload<FormPackage>(local);
  }

  async redactData(dsl: string, data: any, context?: any): Promise<any> {
    return this.postMessage<any>({
      type: 'REDACT_DATA',
      payload: { dsl, data, context }
    });
  }

  async overlayCompose(dsl: string): Promise<OverlayComposeResult> {
    const local = await this.postMessage<unknown>({
      type: 'OVERLAY_COMPOSE',
      payload: { dsl },
    });
    return this.unwrapEnvelopePayload<OverlayComposeResult>(local);
  }

  async simulateACL(dsl: string, role: string, resource: string, action: string): Promise<any> {
    return this.postMessage<any>({
      type: 'SIMULATE_ACL',
      payload: { dsl, role, resource, action }
    });
  }

  async workflowStep(payload: WorkflowStepRequest): Promise<WorkflowStepResponse> {
    if (this.runtimeMode() === 'remote' && !this.isCircuitOpen()) {
      try {
        return await this.workflowStepRemote(payload);
      } catch (error) {
        if (error instanceof RemoteRuntimeError && KNOWN_RUNTIME_ERROR_CODES.has(error.code)) {
          throw error;
        }
        // Fall back to local worker when remote runtime is unavailable.
      }
    }
    return this.postMessage<WorkflowStepResponse>({
      type: 'WORKFLOW_STEP',
      payload,
    });
  }

  async workflowRun(payload: WorkflowRunRequest): Promise<WorkflowRunResponse> {
    if (this.runtimeMode() === 'remote' && !this.isCircuitOpen()) {
      try {
        return await this.workflowRunRemote(payload);
      } catch (error) {
        if (error instanceof RemoteRuntimeError && KNOWN_RUNTIME_ERROR_CODES.has(error.code)) {
          throw error;
        }
        // Fall back to local worker when remote runtime is unavailable.
      }
    }
    return this.postMessage<WorkflowRunResponse>({
      type: 'WORKFLOW_RUN',
      payload,
    });
  }

  workflowBack(session: WorkflowSession): WorkflowSession {
    if (session.steps.length === 0) {
      return session;
    }
    const steps = session.steps.slice(0, -1);
    const currentState = steps.length > 0 ? steps[steps.length - 1].to : session.initialState;
    return {
      ...session,
      currentState,
      steps,
      updatedAt: new Date().toISOString(),
    };
  }

  workflowReset(session: WorkflowSession): WorkflowSession {
    return {
      ...session,
      currentState: session.initialState,
      steps: [],
      updatedAt: new Date().toISOString(),
    };
  }

  exportWorkflowTrace(session: WorkflowSession): WorkflowTraceExport {
    const errors = session.steps
      .filter((step) => step.errorCode)
      .map((step) => ({
        stepId: step.stepId,
        code: step.errorCode as string,
        message: step.reasons?.map((reason) => reason.summary || reason.code).join('; ') || 'Workflow step failed',
      }));

    return {
      contractVersion: WORKFLOW_CONTRACT_VERSION,
      runId: session.runId,
      tenantId: session.tenantId,
      actorId: session.actorId,
      generatedAt: new Date().toISOString(),
      steps: redactUnknown(session.steps),
      auditTrail: redactUnknown(session.auditTrail),
      redactionPolicy: {
        enabled: true,
        mode: 'default-sensitive-patterns',
      },
      summary: {
        totalSteps: session.steps.length,
        successfulSteps: session.steps.filter((step) => step.allow).length,
        failedSteps: session.steps.filter((step) => !step.allow).length,
        finalState: session.currentState,
      },
      errors,
    };
  }

  async listRuleArtifacts(tenantId: string): Promise<RuleArtifactSummary[]> {
    const response = await this.getRemote<{ items: RuleArtifactSummary[] }>('', tenantId);
    return response.items || [];
  }

  async getRuleArtifact(tenantId: string, artifactId: string): Promise<RuleArtifactDetail> {
    return this.getRemote<RuleArtifactDetail>(`/${artifactId}`, tenantId);
  }

  async createRuleArtifact(payload: {
    tenantId: string;
    manifestText: string;
    signature?: string | null;
  }): Promise<{ id: string; status: string; checksum: string }> {
    return this.postRemote<{ id: string; status: string; checksum: string }>('', {
      tenant_id: payload.tenantId,
      manifest_text: payload.manifestText,
      signature: payload.signature ?? null,
    });
  }

  async updateRuleArtifact(payload: {
    tenantId: string;
    artifactId: string;
    manifestText: string;
    signature?: string | null;
  }): Promise<RuleArtifactDetail> {
    return this.putRemote<RuleArtifactDetail>(`/${payload.artifactId}`, {
      tenant_id: payload.tenantId,
      manifest_text: payload.manifestText,
      signature: payload.signature ?? null,
    });
  }

  async activateRuleArtifact(tenantId: string, artifactId: string): Promise<{ id: string; status: string }> {
    return this.postRemote<{ id: string; status: string }>(`/${artifactId}/activate`, {
      tenant_id: tenantId,
    });
  }
}

export const mpcEngine = new MPCEngine();
export type {
  WorkflowAuditEvent,
  WorkflowLimits,
  WorkflowPermissionSet,
  WorkflowReason,
  WorkflowRunRequest,
  WorkflowRunResponse,
  WorkflowSession,
  WorkflowSnapshot,
  WorkflowStepRequest,
  WorkflowStepResponse,
  WorkflowStep,
  WorkflowTraceExport,
  WorkflowTransition,
} from '../types/workflow';
