export const WORKFLOW_CONTRACT_VERSION = '1.0.0';

export interface WorkflowPermissionSet {
  read: boolean;
  simulate: boolean;
  export: boolean;
  reset: boolean;
}

export interface WorkflowReason {
  code: string;
  summary?: string | null;
}

export interface WorkflowError {
  code: string;
  message: string;
}

export interface WorkflowTransition {
  from: string;
  event: string;
  to: string;
  guard?: string | null;
}

export interface WorkflowStep {
  stepId: string;
  event: string;
  from: string;
  to: string;
  allow: boolean;
  guardResult: 'pass' | 'fail' | 'not_applicable';
  reasons: WorkflowReason[];
  errors: WorkflowError[];
  actionsExecuted: string[];
  errorCode?: string;
  remediationHint?: string;
  timestamp: string;
}

export interface WorkflowAuditEvent {
  runId: string;
  tenantId: string;
  actorId: string;
  action: 'step' | 'run' | 'back' | 'reset' | 'export' | 'snapshot' | 'restore' | 'denied';
  allowed: boolean;
  timestamp: string;
  detail?: string;
}

export interface WorkflowSession {
  runId: string;
  tenantId: string;
  actorId: string;
  initialState: string;
  currentState: string;
  availableTransitions: WorkflowTransition[];
  steps: WorkflowStep[];
  auditTrail: WorkflowAuditEvent[];
  updatedAt: string;
}

export interface WorkflowLimits {
  maxSteps: number;
  maxPayloadBytes: number;
  maxEventNameLength: number;
}

export interface WorkflowStepRequest {
  dsl: string;
  artifactId?: string;
  useTenantActiveManifest?: boolean;
  event: string;
  context?: Record<string, unknown>;
  currentState?: string;
  initialState?: string;
  actorId: string;
  actorRoles: string[];
  tenantId: string;
  limits: WorkflowLimits;
}

export interface WorkflowStepResponse {
  initialState: string;
  currentState: string;
  step: WorkflowStep;
  availableTransitions: WorkflowTransition[];
}

export interface WorkflowRunRequest {
  dsl: string;
  artifactId?: string;
  useTenantActiveManifest?: boolean;
  events: Array<{ event: string; context?: Record<string, unknown> }>;
  initialState?: string;
  actorId: string;
  actorRoles: string[];
  tenantId: string;
  limits: WorkflowLimits;
}

export interface WorkflowRunResponse {
  initialState: string;
  currentState: string;
  steps: WorkflowStep[];
  availableTransitions: WorkflowTransition[];
}

export interface WorkflowTraceExport {
  contractVersion: string;
  runId: string;
  tenantId: string;
  actorId: string;
  generatedAt: string;
  steps: WorkflowStep[];
  auditTrail: WorkflowAuditEvent[];
  redactionPolicy: {
    enabled: boolean;
    mode: 'default-sensitive-patterns';
  };
  summary: {
    totalSteps: number;
    successfulSteps: number;
    failedSteps: number;
    finalState: string;
  };
  errors: Array<{
    stepId: string;
    code: string;
    message: string;
  }>;
}

export interface WorkflowSnapshot {
  id: string;
  name: string;
  createdAt: string;
  summary: {
    steps: number;
    finalState: string;
  };
  session: WorkflowSession;
}
