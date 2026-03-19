import { ChevronDown, Download, Play, RotateCcw, Save, SkipBack, StepForward, Workflow } from 'lucide-react';
import { useMemo, useState } from 'react';
import { mpcEngine, type WorkflowLimits, type WorkflowPermissionSet, type WorkflowSession, type WorkflowSnapshot, type WorkflowStep } from '../engine/mpc-engine';
import { createWorkflowAuditEvent } from '../services/workflowAudit';
import { createWorkflowSnapshot, restoreWorkflowSnapshot } from '../services/workflowTraceVersioning';

interface WorkflowSimulatorProps {
  dsl: string;
  workflowId?: string;
  defaultTenantId?: string;
  useTenantActiveManifest?: boolean;
}

const defaultLimits: WorkflowLimits = {
  maxSteps: 100,
  maxPayloadBytes: 16_384,
  maxEventNameLength: 128,
};

const defaultPermissions: WorkflowPermissionSet = {
  read: true,
  simulate: true,
  export: true,
  reset: true,
};

const defaultEventQueue = JSON.stringify(
  [
    { event: 'begin', context: { actor: 'ops-user' } },
    { event: 'finish', context: { approved: true } },
  ],
  null,
  2,
);

const WorkflowSimulator = ({
  dsl,
  workflowId,
  defaultTenantId = 'tenant-default',
  useTenantActiveManifest = false,
}: WorkflowSimulatorProps) => {
  const traceUiV2Enabled = import.meta.env.VITE_WORKFLOW_TRACE_V2 !== 'false';
  const [tenantId, setTenantId] = useState(defaultTenantId);
  const [actorId, setActorId] = useState('operator-1');
  const [actorRolesInput, setActorRolesInput] = useState('admin,operator');
  const [eventName, setEventName] = useState('begin');
  const [eventContextJson, setEventContextJson] = useState('{\n  "source": "studio"\n}');
  const [eventQueueJson, setEventQueueJson] = useState(defaultEventQueue);
  const [limits, setLimits] = useState<WorkflowLimits>(defaultLimits);
  const [permissions, setPermissions] = useState<WorkflowPermissionSet>(defaultPermissions);
  const [session, setSession] = useState<WorkflowSession>({
    runId: crypto.randomUUID(),
    tenantId: defaultTenantId,
    actorId: 'operator-1',
    initialState: '',
    currentState: '',
    availableTransitions: [],
    steps: [],
    auditTrail: [],
    updatedAt: new Date().toISOString(),
  });
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [snapshotName, setSnapshotName] = useState('');
  const [snapshots, setSnapshots] = useState<WorkflowSnapshot[]>([]);

  const actorRoles = useMemo(
    () => actorRolesInput.split(',').map((value) => value.trim()).filter(Boolean),
    [actorRolesInput],
  );

  const pushAudit = (entry: { action: Parameters<typeof createWorkflowAuditEvent>[0]['action']; allowed: boolean; detail?: string }) => {
    setSession((prev) => ({
      ...prev,
      auditTrail: [
        ...prev.auditTrail,
        createWorkflowAuditEvent({ session: prev, tenantId, actorId, ...entry }),
      ],
      updatedAt: new Date().toISOString(),
    }));
  };

  const ensurePermission = (action: keyof WorkflowPermissionSet) => {
    if (!permissions[action]) {
      const detail = `Permission denied for action '${action}'.`;
      setErrorText(detail);
      pushAudit({ action: 'denied', allowed: false, detail });
      return false;
    }
    return true;
  };

  const ensureTenantIsolation = () => {
    if (session.steps.length > 0 && session.tenantId !== tenantId) {
      const detail = 'TENANT_CONTEXT_MISMATCH: Existing run belongs to a different tenant.';
      setErrorText(detail);
      pushAudit({ action: 'denied', allowed: false, detail });
      return false;
    }
    return true;
  };

  const safeParse = <T,>(raw: string, fallback: T): T => {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return fallback;
    }
  };

  const handleStep = async () => {
    if (!ensurePermission('simulate') || !ensureTenantIsolation()) {
      return;
    }

    setLoading(true);
    setErrorText(null);
    try {
      const parsedContext = safeParse<Record<string, unknown>>(eventContextJson, {});
      const response = await mpcEngine.workflowStep({
        dsl,
        workflowId,
        useTenantActiveManifest,
        event: eventName,
        context: parsedContext,
        currentState: session.currentState || undefined,
        initialState: session.initialState || undefined,
        actorId,
        actorRoles,
        tenantId,
        limits,
      });
      setSession((prev) => ({
        ...prev,
        tenantId,
        actorId,
        initialState: response.initialState,
        currentState: response.currentState,
        availableTransitions: response.availableTransitions,
        steps: [...prev.steps, response.step],
        updatedAt: new Date().toISOString(),
      }));
      pushAudit({ action: 'step', allowed: true, detail: `Event '${eventName}' evaluated.` });
    } catch (err) {
      setErrorText(String(err));
      pushAudit({ action: 'step', allowed: false, detail: String(err) });
    } finally {
      setLoading(false);
    }
  };

  const handleRun = async () => {
    if (!ensurePermission('simulate') || !ensureTenantIsolation()) {
      return;
    }

    setLoading(true);
    setErrorText(null);
    try {
      const queue = safeParse<Array<{ event: string; context?: Record<string, unknown> }>>(eventQueueJson, []);
      const response = await mpcEngine.workflowRun({
        dsl,
        workflowId,
        useTenantActiveManifest,
        events: queue,
        initialState: session.initialState || undefined,
        actorId,
        actorRoles,
        tenantId,
        limits,
      });
      setSession((prev) => ({
        ...prev,
        tenantId,
        actorId,
        initialState: response.initialState,
        currentState: response.currentState,
        availableTransitions: response.availableTransitions,
        steps: [...prev.steps, ...response.steps],
        updatedAt: new Date().toISOString(),
      }));
      pushAudit({ action: 'run', allowed: true, detail: `Processed ${response.steps.length} events.` });
    } catch (err) {
      setErrorText(String(err));
      pushAudit({ action: 'run', allowed: false, detail: String(err) });
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    if (!ensurePermission('simulate')) {
      return;
    }
    setSession((prev) => mpcEngine.workflowBack(prev));
    pushAudit({ action: 'back', allowed: true, detail: 'Reverted one step.' });
  };

  const handleReset = () => {
    if (!ensurePermission('reset')) {
      return;
    }
    setSession((prev) => mpcEngine.workflowReset(prev));
    pushAudit({ action: 'reset', allowed: true, detail: 'Reset to initial state.' });
  };

  const handleSnapshotSave = () => {
    const snapshot = createWorkflowSnapshot(session, snapshotName);
    setSnapshots((prev) => [snapshot, ...prev].slice(0, 20));
    setSnapshotName('');
    pushAudit({ action: 'snapshot', allowed: true, detail: `Snapshot '${snapshot.name}' created.` });
  };

  const handleSnapshotRestore = (snapshot: WorkflowSnapshot) => {
    setSession(restoreWorkflowSnapshot(snapshot));
    pushAudit({ action: 'restore', allowed: true, detail: `Restored snapshot '${snapshot.name}'.` });
  };

  const handleExport = () => {
    if (!ensurePermission('export')) {
      return;
    }
    const payload = mpcEngine.exportWorkflowTrace(session);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `workflow-trace-${session.runId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    pushAudit({ action: 'export', allowed: true, detail: `Exported ${payload.steps.length} steps.` });
  };

  const lastStep = session.steps[session.steps.length - 1] as WorkflowStep | undefined;
  const successCount = session.steps.filter((step) => step.allow).length;
  const failureCount = session.steps.length - successCount;

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Workflow className="w-4 h-4 text-cyan-400" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-white">Workflow Simulator</h2>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleStep} disabled={loading} className="px-3 py-1 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-[10px] font-bold text-white disabled:opacity-50 flex items-center gap-1"><StepForward className="w-3 h-3" />STEP</button>
          <button onClick={handleRun} disabled={loading} className="px-3 py-1 rounded-lg bg-violet-600 hover:bg-violet-500 text-[10px] font-bold text-white disabled:opacity-50 flex items-center gap-1"><Play className="w-3 h-3 fill-current" />RUN</button>
          <button onClick={handleBack} className="px-3 py-1 rounded-lg bg-white/10 hover:bg-white/15 text-[10px] font-bold text-gray-200 flex items-center gap-1"><SkipBack className="w-3 h-3" />BACK</button>
          <button onClick={handleReset} className="px-3 py-1 rounded-lg bg-white/10 hover:bg-white/15 text-[10px] font-bold text-gray-200 flex items-center gap-1"><RotateCcw className="w-3 h-3" />RESET</button>
          <button onClick={handleExport} className="px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-[10px] font-bold text-white flex items-center gap-1"><Download className="w-3 h-3" />EXPORT</button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 p-3 border-b border-white/5">
        <input value={tenantId} onChange={(event) => setTenantId(event.target.value)} placeholder="tenantId" className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[11px] text-gray-200" />
        <input value={actorId} onChange={(event) => setActorId(event.target.value)} placeholder="actorId" className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[11px] text-gray-200" />
        <input value={actorRolesInput} onChange={(event) => setActorRolesInput(event.target.value)} placeholder="roles (comma separated)" className="col-span-2 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[11px] text-gray-200" />
        <input value={eventName} onChange={(event) => setEventName(event.target.value)} placeholder="single step event" className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[11px] text-gray-200" />
        <div className="grid grid-cols-3 gap-2">
          <input type="number" aria-label="max steps" title="max steps" value={limits.maxSteps} onChange={(event) => setLimits((prev) => ({ ...prev, maxSteps: Number(event.target.value || 0) }))} className="bg-white/5 border border-white/10 rounded-lg px-2 py-2 text-[10px] text-gray-200" />
          <input type="number" aria-label="max payload bytes" title="max payload bytes" value={limits.maxPayloadBytes} onChange={(event) => setLimits((prev) => ({ ...prev, maxPayloadBytes: Number(event.target.value || 0) }))} className="bg-white/5 border border-white/10 rounded-lg px-2 py-2 text-[10px] text-gray-200" />
          <input type="number" aria-label="max event name length" title="max event name length" value={limits.maxEventNameLength} onChange={(event) => setLimits((prev) => ({ ...prev, maxEventNameLength: Number(event.target.value || 0) }))} className="bg-white/5 border border-white/10 rounded-lg px-2 py-2 text-[10px] text-gray-200" />
        </div>
        <textarea aria-label="step event context json" title="step event context json" placeholder='{"source":"studio"}' value={eventContextJson} onChange={(event) => setEventContextJson(event.target.value)} className="col-span-2 h-20 bg-black/40 border border-white/10 rounded-lg p-2 text-[10px] font-mono text-cyan-300 resize-none" />
        <textarea aria-label="event queue json" title="event queue json" placeholder='[{"event":"begin"}]' value={eventQueueJson} onChange={(event) => setEventQueueJson(event.target.value)} className="col-span-2 h-24 bg-black/40 border border-white/10 rounded-lg p-2 text-[10px] font-mono text-violet-300 resize-none" />
      </div>

      <div className="px-3 py-2 border-b border-white/5 flex items-center gap-4 text-[10px] text-gray-400 uppercase">
        <label><input type="checkbox" title="read permission" checked={permissions.read} onChange={(event) => setPermissions((prev) => ({ ...prev, read: event.target.checked }))} /> read</label>
        <label><input type="checkbox" title="simulate permission" checked={permissions.simulate} onChange={(event) => setPermissions((prev) => ({ ...prev, simulate: event.target.checked }))} /> simulate</label>
        <label><input type="checkbox" title="export permission" checked={permissions.export} onChange={(event) => setPermissions((prev) => ({ ...prev, export: event.target.checked }))} /> export</label>
        <label><input type="checkbox" title="reset permission" checked={permissions.reset} onChange={(event) => setPermissions((prev) => ({ ...prev, reset: event.target.checked }))} /> reset</label>
      </div>

      <div className="grid grid-cols-4 gap-2 px-3 pt-3">
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
          <div className="text-[10px] uppercase text-gray-500">Current State</div>
          <div className="text-xs font-mono text-cyan-300 mt-1">{session.currentState || 'n/a'}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
          <div className="text-[10px] uppercase text-gray-500">Initial State</div>
          <div className="text-xs font-mono text-violet-300 mt-1">{session.initialState || 'n/a'}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
          <div className="text-[10px] uppercase text-gray-500">Steps</div>
          <div className="text-xs font-mono text-white mt-1">{session.steps.length}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
          <div className="text-[10px] uppercase text-gray-500">Allow / Deny</div>
          <div className="text-xs font-mono mt-1">
            <span className="text-emerald-400">{successCount}</span>
            <span className="text-gray-500"> / </span>
            <span className="text-amber-400">{failureCount}</span>
          </div>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-3 gap-3 p-3 overflow-hidden">
        <div className="col-span-2 bg-white/[0.02] rounded-xl border border-white/10 overflow-auto p-3 space-y-2">
          {errorText ? <div className="text-[11px] text-red-400 border border-red-500/30 rounded-lg p-2">{errorText}</div> : null}
          {session.steps.map((step, index) => (
            traceUiV2Enabled ? (
              <details key={step.stepId + step.timestamp} className="border border-white/10 rounded-lg bg-black/20" open={index === session.steps.length - 1}>
                <summary className="list-none cursor-pointer px-2 py-2 text-[11px] flex items-center justify-between">
                  <div className="font-mono text-gray-300 truncate">
                    {step.from} --{step.event}--&gt; {step.to}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={step.allow ? 'text-emerald-400' : 'text-amber-400'}>{step.allow ? 'ALLOW' : 'DENY'}</span>
                    <ChevronDown className="w-3 h-3 text-gray-500" />
                  </div>
                </summary>
                <div className="px-2 pb-2 space-y-2 border-t border-white/5">
                  <div className="text-[10px] text-gray-500">
                    guard: {step.guardResult} {step.errorCode ? `| error: ${step.errorCode}` : ''} | at: {step.timestamp}
                  </div>
                  {step.reasons.length > 0 ? (
                    <div className="text-[10px]">
                      <div className="uppercase text-gray-500 mb-1">Reasons</div>
                      {step.reasons.map((reason, reasonIdx) => (
                        <div key={`${step.stepId}-reason-${reasonIdx}`} className="text-gray-300 font-mono">
                          {reason.code}{reason.summary ? `: ${reason.summary}` : ''}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {step.errors.length > 0 ? (
                    <div className="text-[10px]">
                      <div className="uppercase text-gray-500 mb-1">Errors</div>
                      {step.errors.map((error, errorIdx) => (
                        <div key={`${step.stepId}-error-${errorIdx}`} className="text-red-300 font-mono">
                          {error.code}: {error.message}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {step.remediationHint ? <div className="text-[10px] text-amber-400">{step.remediationHint}</div> : null}
                </div>
              </details>
            ) : (
              <div key={step.stepId + step.timestamp} className="border border-white/10 rounded-lg p-2 text-[11px] bg-black/20">
                <div className="font-mono text-gray-300">{step.from} --{step.event}{'-->'} {step.to}</div>
                <div className="text-[10px] text-gray-500">
                  guard: {step.guardResult} | allow: {String(step.allow)} {step.errorCode ? `| error: ${step.errorCode}` : ''}
                </div>
                {step.remediationHint ? <div className="text-[10px] text-amber-400 mt-1">{step.remediationHint}</div> : null}
              </div>
            )
          ))}
          {session.steps.length === 0 ? <div className="h-full flex items-center justify-center text-gray-600 text-xs">No transitions executed yet.</div> : null}
        </div>
        <div className="bg-white/[0.02] rounded-xl border border-white/10 overflow-auto p-3 space-y-3">
          <div>
            <h3 className="text-[10px] text-gray-500 uppercase mb-2">Available Transitions</h3>
            <div className="space-y-1">
              {session.availableTransitions.map((transition, index) => (
                <div key={`${transition.from}-${transition.event}-${index}`} className="text-[10px] font-mono text-gray-300 border-l border-white/10 pl-2">
                  {transition.from} --{transition.event}{'-->'} {transition.to}
                </div>
              ))}
              {session.availableTransitions.length === 0 ? <div className="text-[10px] text-gray-600 italic">No transitions discovered.</div> : null}
            </div>
          </div>
          <div>
            <h3 className="text-[10px] text-gray-500 uppercase mb-2">Trace Snapshots</h3>
            {traceUiV2Enabled ? (
              <>
                <div className="flex gap-2 mb-2">
                  <input
                    value={snapshotName}
                    onChange={(event) => setSnapshotName(event.target.value)}
                    placeholder="snapshot name (optional)"
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-[10px] text-gray-200"
                  />
                  <button
                    onClick={handleSnapshotSave}
                    className="px-2 py-1 rounded-lg bg-blue-600/80 hover:bg-blue-500 text-[10px] font-bold text-white flex items-center gap-1"
                  >
                    <Save className="w-3 h-3" />
                    SAVE
                  </button>
                </div>
                <div className="space-y-1 max-h-28 overflow-auto">
                  {snapshots.map((snapshot) => (
                    <button
                      key={snapshot.id}
                      onClick={() => handleSnapshotRestore(snapshot)}
                      className="w-full text-left text-[10px] border border-white/10 rounded-lg px-2 py-1 hover:bg-white/5"
                    >
                      <div className="text-gray-300 font-mono truncate">{snapshot.name}</div>
                      <div className="text-gray-500">{snapshot.summary.steps} steps | final: {snapshot.summary.finalState}</div>
                    </button>
                  ))}
                  {snapshots.length === 0 ? <div className="text-[10px] text-gray-600 italic">No snapshots.</div> : null}
                </div>
              </>
            ) : (
              <div className="text-[10px] text-gray-600 italic">
                Snapshot controls disabled (legacy trace mode enabled via kill switch).
              </div>
            )}
          </div>
          <div>
            <h3 className="text-[10px] text-gray-500 uppercase mb-2">Audit Trail</h3>
            <div className="space-y-1">
              {session.auditTrail.map((entry, index) => (
                <div key={`${entry.timestamp}-${index}`} className="text-[10px] text-gray-400 border-l border-white/10 pl-2">
                  [{entry.action}] {entry.allowed ? 'allow' : 'deny'} - {entry.detail}
                </div>
              ))}
              {session.auditTrail.length === 0 ? <div className="text-[10px] text-gray-600 italic">No audit events.</div> : null}
            </div>
          </div>
          <div className="text-[10px] text-gray-500 uppercase">
            Last status: <span className={lastStep?.allow ? 'text-emerald-400' : 'text-amber-400'}>{lastStep ? (lastStep.allow ? 'ALLOW' : 'DENY') : 'N/A'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkflowSimulator;
