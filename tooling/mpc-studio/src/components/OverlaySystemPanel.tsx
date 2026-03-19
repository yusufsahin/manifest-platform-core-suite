import { Layers, Sparkles } from 'lucide-react';

interface OverlayDefinition {
  kind: string;
  id: string;
  name?: string;
  properties: Record<string, unknown>;
}

interface OverlaySystemPanelProps {
  definitions: OverlayDefinition[];
}

const OVERLAY_KINDS = new Set(['Overlay', 'OverlayRule', 'Projection', 'ViewOverlay']);

const OverlaySystemPanel = ({ definitions }: OverlaySystemPanelProps) => {
  const overlays = definitions.filter((definition) => OVERLAY_KINDS.has(definition.kind));

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 flex items-center gap-2">
        <Layers className="w-4 h-4 text-blue-400" />
        <h2 className="text-xs font-bold uppercase tracking-widest text-white">Overlay System</h2>
      </div>

      <div className="p-3 border-b border-white/5 grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="text-[10px] uppercase text-gray-500">Overlay Definitions</p>
          <p className="text-sm font-mono text-cyan-300 mt-1">{overlays.length}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="text-[10px] uppercase text-gray-500">Runtime Mode</p>
          <p className="text-sm font-mono text-violet-300 mt-1">Preview</p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3 space-y-2">
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
              <pre className="text-[10px] font-mono text-gray-400 overflow-auto">
                {JSON.stringify(overlay.properties, null, 2)}
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
