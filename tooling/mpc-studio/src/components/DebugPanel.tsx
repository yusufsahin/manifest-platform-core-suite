import { Activity, CornerDownRight } from 'lucide-react';

interface TraceStep {
  node_type: string;
  value: any;
  depth: number;
}

interface DebugPanelProps {
  trace: TraceStep[] | null;
  value: any;
  type: string | null;
}

const DebugPanel = ({ trace, value, type }: DebugPanelProps) => {
  if (!trace) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-600 space-y-2">
        <Activity className="w-8 h-8 opacity-20" />
        <p className="text-xs italic">Enable Debug Mode to see evaluation traces</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="h-10 border-b border-white/5 flex items-center px-4 justify-between bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-amber-500" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">Trace Inspector</span>
        </div>
        <div className="flex items-center gap-3">
           <span className="text-[9px] text-gray-600 uppercase">Result Type:</span>
           <span className="text-[10px] font-mono text-cyan-400">{type || 'unknown'}</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-1">
        {trace.map((step, i) => (
          <div 
            key={i} 
            className="flex items-start gap-2 hover:bg-white/5 p-1 rounded transition-colors group"
            style={{ paddingLeft: `${step.depth * 12}px` }}
          >
            {step.depth > 0 && <CornerDownRight className="w-3 h-3 mt-1 text-gray-700" />}
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-gray-500 uppercase">{step.node_type}</span>
                <span className="text-[10px] font-mono text-amber-500/80 scale-0 group-hover:scale-100 transition-transform">STEP {i+1}</span>
              </div>
              <div className="text-[11px] font-mono text-gray-300 break-all">
                {typeof step.value === 'object' ? JSON.stringify(step.value) : String(step.value)}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 border-t border-white/5 bg-amber-500/5">
        <p className="text-[9px] text-amber-500/60 uppercase mb-1 font-bold">Final Evaluation</p>
        <div className="text-sm font-mono text-white break-all">
          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
        </div>
      </div>
    </div>
  );
};

export default DebugPanel;
