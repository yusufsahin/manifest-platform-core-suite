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
          </div>
        ) : null}

        {result?.diffs?.length ? (
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">Diffs</p>
            <ul className="mt-2 space-y-1 text-[11px] font-mono text-gray-300">
              {result.diffs.slice(0, 25).map((d, idx) => (
                <li key={idx}>
                  {d.key}
                </li>
              ))}
              {result.diffs.length > 25 ? (
                <li className="text-gray-500">… +{result.diffs.length - 25} more</li>
              ) : null}
            </ul>
          </div>
        ) : null}

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
