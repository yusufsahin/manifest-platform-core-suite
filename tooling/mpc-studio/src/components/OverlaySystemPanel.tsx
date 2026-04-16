import { Layers, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { DefinitionDescriptor } from '../types/definition';
import type { PanelAdapterContext } from '../types/panelAdapter';
import { mpcEngine } from '../engine/mpc-engine';
import type { OverlayComposeResult } from '../types/overlay';

interface OverlaySystemPanelProps {
  dsl: string;
  definitions: DefinitionDescriptor[];
  context?: PanelAdapterContext;
}

const OVERLAY_KINDS = new Set(['Overlay', 'OverlayRule', 'Projection', 'ViewOverlay']);

const OverlaySystemPanel = ({ dsl, definitions, context }: OverlaySystemPanelProps) => {
  const overlays = definitions.filter((definition) => OVERLAY_KINDS.has(definition.kind));
  const [result, setResult] = useState<OverlayComposeResult | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      setErrorText(null);
      try {
        const res = await mpcEngine.overlayCompose(dsl);
        if (!cancelled) setResult(res);
      } catch (e) {
        if (!cancelled) setErrorText(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [dsl]);

  const diffCount = result?.diffs?.length ?? 0;
  const trace = result?.trace ?? [];
  const traceForSelected = selectedKey ? trace.filter((t) => t.target_key === selectedKey) : [];
  const conflictSuggestions = (() => {
    const suggestions: Array<{ title: string; items: string[] }> = [];

    const replacePathGroups = new Map<string, Set<string>>();
    for (const t of trace) {
      if (t.op !== 'replace' || !t.path) continue;
      const key = `${t.target_key}::${t.path}`;
      const set = replacePathGroups.get(key) ?? new Set<string>();
      set.add(t.overlay_id);
      replacePathGroups.set(key, set);
    }

    const replaceConflicts = Array.from(replacePathGroups.entries())
      .filter(([, ids]) => ids.size > 1)
      .map(([k, ids]) => ({ k, ids: Array.from(ids).sort() }));

    if (replaceConflicts.length > 0) {
      const lines: string[] = [];
      for (const c of replaceConflicts.slice(0, 6)) {
        const [targetKey, path] = c.k.split('::');
        lines.push(`Replace conflict on ${targetKey} path '${path}': overlays=${c.ids.join(', ')}`);
      }
      suggestions.push({
        title: 'Conflicting replace ops',
        items: [
          ...lines,
          'Fix options:',
          '- Keep a single replace overlay for a given (target_key, path).',
          "- Convert the others to 'merge' or 'patch' if you intend to combine changes.",
          '- Or merge the changes into one overlay to avoid conflicts.',
        ],
      });
    }

    const unknownSelector = (result?.conflicts ?? []).some((c) => c.code === 'E_OVERLAY_UNKNOWN_SELECTOR');
    if (unknownSelector) {
      suggestions.push({
        title: 'Unknown selector',
        items: [
          'Ensure each Overlay has a stable selector:',
          "- Prefer selector: { kind, namespace, id } over a loose 'target'.",
          'Verify the selected (kind, id) exists in the base manifest.',
        ],
      });
    }

    const invalidOp = (result?.conflicts ?? []).some((c) => c.code === 'E_OVERLAY_INVALID_OP');
    if (invalidOp) {
      suggestions.push({
        title: 'Invalid op',
        items: ['Allowed overlay ops: replace, merge, append, remove, patch.'],
      });
    }

    return suggestions;
  })();

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 flex items-center gap-2">
        <Layers className="w-4 h-4 text-blue-400" />
        <h2 className="text-xs font-bold uppercase tracking-widest text-white">Overlay System</h2>
        {context?.selectedDefinition ? (
          <span className="ml-auto text-[10px] text-blue-200/80 font-mono">
            {context.selectedDefinition.kind}:{context.selectedDefinition.id}
          </span>
        ) : null}
      </div>

      <div className="p-3 border-b border-white/5 grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="text-[10px] uppercase text-gray-500">Overlay Definitions</p>
          <p className="text-sm font-mono text-cyan-300 mt-1">{overlays.length}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="text-[10px] uppercase text-gray-500">Compose</p>
          <p className="text-sm font-mono text-violet-300 mt-1">
            {loading ? 'Running…' : errorText ? 'Error' : 'OK'}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3 space-y-2">
        {errorText ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3 text-[11px] font-mono text-red-200">
            {errorText}
          </div>
        ) : null}

        {result?.conflicts?.length ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-red-200">Conflicts</p>
            <ul className="mt-2 space-y-1 text-[11px] font-mono text-red-200">
              {result.conflicts.map((c, idx) => (
                <li key={idx}>
                  [{c.code}] {c.message}
                </li>
              ))}
            </ul>
            {conflictSuggestions.length > 0 ? (
              <div className="mt-3 space-y-3">
                {conflictSuggestions.map((s, idx) => (
                  <div key={idx} className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-300">{s.title}</p>
                    <ul className="mt-2 space-y-1 text-[11px] font-mono text-gray-300">
                      {s.items.map((line, i) => (
                        <li key={i}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {result?.diffs?.length ? (
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">Diffs</p>
            <ul className="mt-2 space-y-1 text-[11px] font-mono text-gray-300">
              {result.diffs.slice(0, 25).map((d, idx) => (
                <li key={idx}>
                  <button
                    type="button"
                    onClick={() => setSelectedKey(d.key)}
                    className={`text-left w-full hover:text-white transition-colors ${selectedKey === d.key ? 'text-white' : ''}`}
                    title="Show overlay trace for this node"
                  >
                    {d.key}
                  </button>
                </li>
              ))}
              {result.diffs.length > 25 ? (
                <li className="text-gray-500">… +{result.diffs.length - 25} more</li>
              ) : null}
            </ul>
          </div>
        ) : null}

        {selectedKey && (
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">Trace</p>
            <p className="mt-1 text-[10px] font-mono text-gray-500">{selectedKey}</p>
            {traceForSelected.length === 0 ? (
              <p className="mt-2 text-[11px] font-mono text-gray-500">No trace entries for this node.</p>
            ) : (
              <div className="mt-2 space-y-2">
                {traceForSelected.slice(0, 20).map((t, idx) => (
                  <div key={idx} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-cyan-300">{t.overlay_id}</span>
                      <span className="text-[10px] font-mono text-violet-300">{t.op}</span>
                    </div>
                    <div className="mt-1 text-[10px] font-mono text-gray-500">
                      path: {t.path ?? '(node)'}
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <pre className="text-[10px] font-mono text-gray-400 overflow-auto max-h-40">
                        {JSON.stringify(t.before, null, 2)}
                      </pre>
                      <pre className="text-[10px] font-mono text-gray-400 overflow-auto max-h-40">
                        {JSON.stringify(t.after, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
                {traceForSelected.length > 20 ? (
                  <p className="text-[10px] font-mono text-gray-500">… +{traceForSelected.length - 20} more</p>
                ) : null}
              </div>
            )}
          </div>
        )}

        {overlays.length === 0 ? (
          <div className="h-full flex items-center justify-center rounded-xl border border-dashed border-white/10 text-gray-500 text-xs">
            No overlay definitions found in current manifest.
          </div>
        ) : (
          overlays.map((overlay, index) => (
            <div key={`${overlay.id}-${index}`} className="rounded-xl border border-white/10 bg-black/20 p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[11px] text-gray-200 font-semibold">{overlay.name || overlay.id}</div>
                <span className="text-[10px] font-mono text-blue-300 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                  {overlay.kind}
                </span>
              </div>
              {diffCount > 0 ? (
                <div className="mb-2 text-[10px] text-gray-500 font-mono">compose diffs: {diffCount}</div>
              ) : null}
              <pre className="text-[10px] font-mono text-gray-400 overflow-auto">
                {JSON.stringify(overlay, null, 2)}
              </pre>
            </div>
          ))
        )}
      </div>

      <div className="p-3 border-t border-white/5 text-[10px] text-gray-500 flex items-center gap-2 uppercase">
        <Sparkles className="w-3 h-3 text-blue-300" />
        Overlay pipeline preview (authoring-side)
      </div>
    </div>
  );
};

export default OverlaySystemPanel;
