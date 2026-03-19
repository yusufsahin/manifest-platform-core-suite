import type { DefinitionDescriptor } from '../types/definition';

interface DefinitionInspectorProps {
  definition?: DefinitionDescriptor;
  reason?: string;
}

const DefinitionInspector = ({ definition, reason }: DefinitionInspectorProps) => {
  if (!definition) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500 text-xs italic">
        Select a definition to inspect metadata.
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5">
        <h2 className="text-xs font-bold uppercase tracking-widest text-white">Generic Definition Inspector</h2>
        {reason ? <p className="mt-1 text-[10px] text-amber-400">{reason}</p> : null}
      </div>
      <div className="flex-1 overflow-auto p-4">
        <div className="rounded-xl border border-white/10 bg-black/20 p-3">
          <pre className="text-[11px] font-mono text-gray-300 whitespace-pre-wrap">
            {JSON.stringify(definition, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default DefinitionInspector;
