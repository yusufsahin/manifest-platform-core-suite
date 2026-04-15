import { useEffect, useMemo, useState } from 'react';
import { Layout, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react';
import type { DefinitionDiagnostic } from '../types/definition';
import type { WorkerRuntimeMetrics } from '../engine/mpc-engine';

type FormPackage = {
  jsonSchema: {
    title?: string;
    properties?: Record<string, any>;
    required?: string[];
    'x-form-id'?: string;
    'x-workflow-state'?: string;
    'x-workflow-trigger'?: string;
  };
  uiSchema: Record<string, any>;
  fieldState: Array<{ field_id: string; visible: boolean; readonly: boolean }>;
  validation: { valid: boolean; errors: Array<{ field_id: string; message: string; expr?: string | null }> };
};

export default function FormPreview(props: {
  formId: string;
  onGeneratePackage: (input: { formId: string; data: Record<string, unknown> }) => Promise<FormPackage>;
  getLastRuntimeInfo?: () => { metrics: WorkerRuntimeMetrics | null; diagnostics: DefinitionDiagnostic[] };
}) {
  const { formId, onGeneratePackage, getLastRuntimeInfo } = props;
  const [loading, setLoading] = useState(false);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [pkg, setPkg] = useState<FormPackage | null>(null);
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [submitted, setSubmitted] = useState(false);
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
    } catch (err) {
      setPkg(null);
      setEngineError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void handleGenerate({});
  }, [formId]);

  const schema = pkg?.jsonSchema;
  const properties = schema?.properties ?? {};
  const required = new Set(schema?.required ?? []);
  const hasDiagnostics = (runtimeInfo.diagnostics ?? []).length > 0;
  const errorDiagnostics = (runtimeInfo.diagnostics ?? []).filter((d) => d.severity === 'error');

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
                </div>
              </div>

              <div className="p-4 space-y-4">
                {Object.entries(properties).map(([fieldId, field]) => {
                  const state = fieldStateById.get(fieldId) ?? { visible: true, readonly: false };
                  if (!state.visible) return null;

                  const label = field?.title || fieldId;
                  const isRequired = required.has(fieldId);
                  const inputId = `form-preview-${formId}-${fieldId}`;
                  const value = formData[fieldId];
                  const disabled = state.readonly;

                  const baseClass =
                    'w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[11px] text-white ' +
                    'focus:outline-none focus:border-violet-500/60 transition-colors placeholder-gray-600 disabled:opacity-60';

                  return (
                    <div key={fieldId} className="space-y-1.5">
                      <label className="flex items-center gap-1 text-[10px] font-medium text-gray-400">
                        {label}
                        {isRequired ? <span className="text-red-400">*</span> : null}
                        <span className="text-[9px] font-mono text-gray-700 ml-1">({field?.type ?? 'any'})</span>
                      </label>

                      {field?.enum ? (
                        <select
                          id={inputId}
                          aria-label={label}
                          value={(value as any) ?? ''}
                          disabled={disabled}
                          onChange={(e) => setFormData((prev) => ({ ...prev, [fieldId]: e.target.value }))}
                          className={baseClass}
                        >
                          <option value="">Seçiniz...</option>
                          {(field.enum as string[]).map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      ) : field?.type === 'boolean' ? (
                        <input
                          id={inputId}
                          aria-label={label}
                          type="checkbox"
                          checked={Boolean(value)}
                          disabled={disabled}
                          onChange={(e) => setFormData((prev) => ({ ...prev, [fieldId]: e.target.checked }))}
                          className="w-4 h-4 rounded accent-violet-500 disabled:opacity-60"
                        />
                      ) : field?.type === 'number' ? (
                        <input
                          id={inputId}
                          aria-label={label}
                          type="number"
                          value={(value as any) ?? ''}
                          disabled={disabled}
                          min={field.minimum}
                          max={field.maximum}
                          onChange={(e) => setFormData((prev) => ({ ...prev, [fieldId]: e.target.valueAsNumber }))}
                          className={baseClass}
                          placeholder={field?.['x-placeholder'] ?? fieldId}
                        />
                      ) : (
                        <input
                          id={inputId}
                          aria-label={label}
                          type="text"
                          value={(value as any) ?? ''}
                          disabled={disabled}
                          onChange={(e) => setFormData((prev) => ({ ...prev, [fieldId]: e.target.value }))}
                          className={baseClass}
                          placeholder={field?.['x-placeholder'] ?? fieldId}
                        />
                      )}
                    </div>
                  );
                })}
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

                <button
                  onClick={async () => {
                    setSubmitted(false);
                    await handleGenerate(formData);
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

