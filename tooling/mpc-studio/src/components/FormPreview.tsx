import { useEffect, useMemo, useState } from 'react';
import { Layout, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react';
import type { DefinitionDiagnostic } from '../types/definition';
import type { WorkerRuntimeMetrics, WorkflowStepResponse } from '../engine/mpc-engine';
import type { FormPackage } from '../types/form';
import { renderWidget, resolveWidgetId } from '../forms/registry';

export default function FormPreview(props: {
  formId: string;
  onGeneratePackage: (input: { formId: string; data: Record<string, unknown> }) => Promise<FormPackage>;
  onWorkflowStep?: (input: { event: string; currentState?: string; initialState?: string }) => Promise<WorkflowStepResponse>;
  getLastRuntimeInfo?: () => { metrics: WorkerRuntimeMetrics | null; diagnostics: DefinitionDiagnostic[] };
}) {
  const { formId, onGeneratePackage, onWorkflowStep, getLastRuntimeInfo } = props;
  const [loading, setLoading] = useState(false);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [pkg, setPkg] = useState<FormPackage | null>(null);
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [submitted, setSubmitted] = useState(false);
  const [workflowStep, setWorkflowStep] = useState<WorkflowStepResponse | null>(null);
  const [runtimeInfo, setRuntimeInfo] = useState<{
    metrics: WorkerRuntimeMetrics | null;
    diagnostics: DefinitionDiagnostic[];
  }>({ metrics: null, diagnostics: [] });

  const fieldStateById = useMemo(() => {
    const map = new Map<string, { visible: boolean; readonly: boolean }>();
    for (const s of pkg?.fieldState ?? []) {
      map.set(s.field_id, { visible: s.visible, readonly: s.readonly });
    }
    return map;
  }, [pkg]);

  const handleGenerate = async (nextData?: Record<string, unknown>) => {
    setLoading(true);
    setEngineError(null);
    try {
      const result = await onGeneratePackage({ formId, data: nextData ?? formData });
      setPkg(result);
      if (getLastRuntimeInfo) {
        setRuntimeInfo(getLastRuntimeInfo());
      } else {
        setRuntimeInfo({ metrics: null, diagnostics: [] });
      }
      return result;
    } catch (err) {
      setPkg(null);
      setEngineError(err instanceof Error ? err.message : String(err));
      return null;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void handleGenerate({});
  }, [formId]);

  const schema = pkg?.jsonSchema;
  const properties = schema?.properties ?? {};
  const uiOrder = (pkg?.uiSchema as any)?.['ui:order'];
  const orderedFieldIds: string[] = Array.isArray(uiOrder)
    ? uiOrder.filter((v: unknown): v is string => typeof v === 'string')
    : Object.keys(properties);
  const required = new Set(schema?.required ?? []);
  const hasDiagnostics = (runtimeInfo.diagnostics ?? []).length > 0;
  const errorDiagnostics = (runtimeInfo.diagnostics ?? []).filter((d) => d.severity === 'error');
  const fieldErrorsById = useMemo(() => {
    const map = new Map<string, Array<{ message: string; expr?: string | null }>>();
    for (const err of pkg?.validation?.errors ?? []) {
      if (!err?.field_id) continue;
      const list = map.get(err.field_id) ?? [];
      list.push({ message: err.message, expr: err.expr });
      map.set(err.field_id, list);
    }
    return map;
  }, [pkg]);

  type LayoutGroup = { title?: string; columns: string[][] };
  const layoutGroups: LayoutGroup[] = useMemo(() => {
    const ui = (pkg?.uiSchema ?? {}) as any;
    const all = orderedFieldIds.filter((id) => typeof id === 'string' && id.length > 0);
    const used = new Set<string>();
    const groups: LayoutGroup[] = [];

    const normalizeColumn = (value: unknown): string[] =>
      Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];

    const normalizeColumns = (value: unknown): string[][] => {
      if (Array.isArray(value) && value.every(Array.isArray)) {
        return value.map(normalizeColumn).filter((col) => col.length > 0);
      }
      return [];
    };

    const uiGroups = ui?.['ui:groups'];
    if (Array.isArray(uiGroups)) {
      for (const g of uiGroups) {
        if (!g || typeof g !== 'object') continue;
        const title = typeof g.title === 'string' ? g.title : undefined;
        const candidateA = normalizeColumns((g as any)['ui:columns']);
        const candidateB = normalizeColumns((g as any).columns);
        const candidateC = (() => {
          const fields = normalizeColumn((g as any).fields);
          const cols = Math.max(1, Math.min(4, Number((g as any).columns ?? 1) || 1));
          if (fields.length === 0) return [];
          if (cols === 1) return [fields];
          const out: string[][] = Array.from({ length: cols }, () => []);
          fields.forEach((id, idx) => out[idx % cols].push(id));
          return out;
        })();
        const columns = candidateA.length > 0 ? candidateA : candidateB.length > 0 ? candidateB : candidateC;
        const effective = (Array.isArray(columns) ? columns : []).filter((c) => c.length > 0);
        if (effective.length === 0) continue;
        for (const col of effective) for (const id of col) used.add(id);
        groups.push({ title, columns: effective });
      }
    }

    const uiColumns = normalizeColumns(ui?.['ui:columns']);
    if (groups.length === 0 && uiColumns.length > 0) {
      for (const col of uiColumns) for (const id of col) used.add(id);
      groups.push({ columns: uiColumns });
    }

    if (groups.length === 0) {
      for (const id of all) used.add(id);
      groups.push({ columns: [all] });
    }

    const remainder = all.filter((id) => !used.has(id));
    if (remainder.length > 0) {
      groups.push({ title: 'Other', columns: [remainder] });
    }

    return groups;
  }, [pkg, orderedFieldIds]);

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layout className="w-4 h-4 text-violet-400" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-white">Form Preview</h2>
          <span className="text-[10px] text-gray-600 font-mono">{formId}</span>
          {runtimeInfo.metrics?.requestId ? (
            <button
              type="button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(runtimeInfo.metrics?.requestId ?? '');
                } catch {
                  // ignore clipboard failures (permissions / insecure context)
                }
              }}
              className="text-[9px] px-1.5 py-0.5 rounded-full bg-white/5 text-gray-400 font-mono hover:bg-white/10 transition-colors"
              title="Copy requestId"
            >
              req: {runtimeInfo.metrics.requestId.slice(0, 8)}
            </button>
          ) : null}
          {runtimeInfo.metrics?.durationMs != null ? (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-white/5 text-gray-400 font-mono">
              {Math.round(runtimeInfo.metrics.durationMs)}ms
            </span>
          ) : null}
          {hasDiagnostics ? (
            <span
              className={`text-[9px] px-1.5 py-0.5 rounded-full font-mono ${
                errorDiagnostics.length > 0 ? 'bg-red-500/10 text-red-300' : 'bg-yellow-500/10 text-yellow-200'
              }`}
              title={runtimeInfo.diagnostics.map((d) => `[${d.severity}] ${d.code}: ${d.message}`).join('\n')}
            >
              diag: {runtimeInfo.diagnostics.length}
            </span>
          ) : null}
        </div>
        <button
          onClick={() => void handleGenerate()}
          disabled={loading}
          className="p-1.5 rounded-lg hover:bg-white/5 text-gray-500 hover:text-white transition-all disabled:opacity-50"
          title="Regenerate"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {engineError ? (
        <div className="p-4 text-[11px] text-red-300 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5" />
          <div className="font-mono whitespace-pre-wrap">{engineError}</div>
        </div>
      ) : null}

      {hasDiagnostics ? (
        <div
          className={`mx-4 mt-4 rounded-xl border p-3 ${
            errorDiagnostics.length > 0 ? 'border-red-500/20 bg-red-500/5' : 'border-yellow-500/20 bg-yellow-500/5'
          }`}
        >
          <p
            className={`text-[10px] font-bold uppercase tracking-widest ${
              errorDiagnostics.length > 0 ? 'text-red-200' : 'text-yellow-200'
            }`}
          >
            Diagnostics
          </p>
          <ul className="mt-2 space-y-1 text-[11px] font-mono">
            {(runtimeInfo.diagnostics ?? []).map((d, idx) => (
              <li key={idx} className={d.severity === 'error' ? 'text-red-200' : 'text-yellow-200'}>
                [{d.severity}] {d.code} — {d.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex-1 overflow-auto p-4 space-y-4">
        {!pkg ? (
          <div className="h-[240px] flex items-center justify-center text-gray-600 opacity-60 text-[11px]">
            Generate a form package to preview.
          </div>
        ) : (
          <>
            <div className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
              <div className="px-4 py-3 border-b border-white/5">
                <p className="text-[11px] font-bold text-white">{schema?.title || formId}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  {schema?.['x-workflow-state'] ? (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-400 font-mono">
                      state: {schema?.['x-workflow-state']}
                    </span>
                  ) : null}
                  {schema?.['x-workflow-trigger'] ? (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 font-mono">
                      trigger: {schema?.['x-workflow-trigger']}
                    </span>
                  ) : null}
                  {workflowStep?.step ? (
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded-full font-mono ${
                        workflowStep.step.allow ? 'bg-green-500/15 text-green-300' : 'bg-red-500/15 text-red-200'
                      }`}
                      title={(workflowStep.step.reasons ?? [])
                        .map((r) => r.summary || r.code)
                        .filter(Boolean)
                        .join('\n')}
                    >
                      wf: {workflowStep.currentState}
                    </span>
                  ) : null}
                </div>
              </div>

              <div className="p-4 space-y-4">
                {layoutGroups.map((group, groupIdx) => (
                  <div key={groupIdx} className="space-y-3">
                    {group.title ? (
                      <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500">{group.title}</div>
                    ) : null}

                    <div
                      className={
                        group.columns.length <= 1
                          ? ''
                          : group.columns.length === 2
                            ? 'grid gap-4 grid-cols-2'
                            : group.columns.length === 3
                              ? 'grid gap-4 grid-cols-3'
                              : 'grid gap-4 grid-cols-4'
                      }
                    >
                      {group.columns.map((column, colIdx) => (
                        <div key={colIdx} className="space-y-4">
                          {column.map((fieldId) => {
                            const field = (properties as any)[fieldId] as any;
                            const state = fieldStateById.get(fieldId) ?? { visible: true, readonly: false };
                            if (!state.visible) return null;

                            const label = field?.title || fieldId;
                            const isRequired = required.has(fieldId);
                            const inputId = `form-preview-${formId}-${fieldId}`;
                            const value = formData[fieldId];
                            const disabled = state.readonly;
                            const ui = ((pkg?.uiSchema as any)?.[fieldId] ?? {}) as Record<string, any>;
                            const placeholder = (ui?.['ui:placeholder'] ?? field?.['x-placeholder'] ?? fieldId) as string;
                            const resolved = resolveWidgetId({
                              jsonSchema: schema as any,
                              uiSchema: pkg?.uiSchema as any,
                              fieldId,
                            });
                            const fieldErrors = fieldErrorsById.get(fieldId) ?? [];

                            const baseClass =
                              'w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[11px] text-white ' +
                              'focus:outline-none focus:border-violet-500/60 transition-colors placeholder-gray-600 disabled:opacity-60';

                            return (
                              <div key={fieldId} className="space-y-1.5">
                                <label className="flex items-center gap-1 text-[10px] font-medium text-gray-400">
                                  {label}
                                  {isRequired ? <span className="text-red-400">*</span> : null}
                                  <span className="text-[9px] font-mono text-gray-700 ml-1">({field?.type ?? 'any'})</span>
                                  {resolved.source === 'uiSchema' &&
                                  resolved.requested &&
                                  resolved.widget === 'text' &&
                                  resolved.requested !== 'text' ? (
                                    <span
                                      className="text-[9px] font-mono text-yellow-200 ml-2 px-1.5 py-0.5 rounded bg-yellow-500/10 border border-yellow-500/20"
                                      title={`Unknown ui:widget '${resolved.requested}', falling back to 'text'.`}
                                    >
                                      widget:{resolved.requested}
                                    </span>
                                  ) : null}
                                </label>

                                {renderWidget(resolved.widget, {
                                  inputId,
                                  label,
                                  value,
                                  disabled,
                                  placeholder,
                                  onChange: (next) => setFormData((prev) => ({ ...prev, [fieldId]: next })),
                                  schema: field ?? {},
                                  ui,
                                  className: baseClass,
                                })}

                                {fieldErrors.length > 0 ? (
                                  <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2">
                                    <ul className="text-[10px] text-red-200 font-mono space-y-1">
                                      {fieldErrors.map((err, idx) => (
                                        <li key={idx}>
                                          {err.message}
                                          {err.expr ? (
                                            <span className="text-[9px] text-red-200/70 ml-2" title={err.expr}>
                                              expr
                                            </span>
                                          ) : null}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div className="px-4 pb-4 space-y-3">
                {!pkg.validation.valid ? (
                  <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-red-200">Validation</p>
                    <ul className="mt-2 space-y-1 text-[11px] text-red-200 font-mono">
                      {pkg.validation.errors.map((err, idx) => (
                        <li key={idx}>
                          [{err.field_id}] {err.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {workflowStep?.step && !workflowStep.step.allow ? (
                  <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-red-200">Workflow</p>
                    <ul className="mt-2 space-y-1 text-[11px] text-red-200 font-mono">
                      {(workflowStep.step.reasons ?? []).map((r, idx) => (
                        <li key={idx}>[{r.code}] {r.summary || r.code}</li>
                      ))}
                      {(workflowStep.step.errors ?? []).map((e, idx) => (
                        <li key={`e-${idx}`}>[{e.code}] {e.message}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <button
                  onClick={async () => {
                    setSubmitted(false);
                    const next = await handleGenerate(formData);
                    setWorkflowStep(null);
                    const trigger = next?.jsonSchema?.['x-workflow-trigger'];
                    if (next && next.validation?.valid && onWorkflowStep && trigger) {
                      try {
                        const step = await onWorkflowStep({
                          event: String(trigger),
                          currentState: workflowStep?.currentState,
                          initialState: workflowStep?.initialState,
                        });
                        setWorkflowStep(step);
                      } catch (err) {
                        setEngineError(err instanceof Error ? err.message : String(err));
                      }
                    }
                    setSubmitted(true);
                    setTimeout(() => setSubmitted(false), 1500);
                  }}
                  className="w-full py-2 rounded-lg bg-violet-600/30 hover:bg-violet-600/50 border border-violet-500/30 text-[10px] font-bold text-violet-300 transition-all flex items-center justify-center gap-2"
                >
                  {submitted ? (
                    <>
                      <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                      <span className="text-green-400">Validated</span>
                    </>
                  ) : (
                    'VALIDATE'
                  )}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

