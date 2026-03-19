import { Shield, Play, CheckCircle2, XCircle, Info } from 'lucide-react';
import { useState } from 'react';
import type { PanelAdapterContext } from '../types/panelAdapter';

interface PolicySimulatorProps {
  onSimulate: (event: any) => Promise<any>;
  context?: PanelAdapterContext;
}

const PolicySimulator = ({ onSimulate, context }: PolicySimulatorProps) => {
  const [eventJson, setEventJson] = useState('{\n  "user": {\n    "role": "admin",\n    "id": 1\n  },\n  "action": "delete"\n}');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSimulate = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const event = JSON.parse(eventJson);
      const res = await onSimulate(event);
      setResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid JSON payload';
      setResult({ error: 'Simulation failed' });
      setErrorMessage(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-violet-400" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-white">Policy Simulator</h2>
        </div>
        {context?.selectedDefinition ? (
          <span className="text-[10px] text-violet-300 font-mono">
            {context.selectedDefinition.kind}:{context.selectedDefinition.id}
          </span>
        ) : null}
        <button 
          onClick={handleSimulate}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1 rounded-lg bg-violet-600 hover:bg-violet-500 text-[10px] font-bold text-white transition-all disabled:opacity-50"
        >
          <Play className="w-3 h-3 fill-current" />
          {loading ? 'RUNNING...' : 'SIMULATE'}
        </button>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="h-1/2 border-b border-white/5 flex flex-col">
          <div className="px-4 py-2 bg-white/[0.02] flex items-center justify-between">
            <span className="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Event JSON (Actor/Context)</span>
          </div>
          <textarea 
            value={eventJson}
            onChange={(e) => setEventJson(e.target.value)}
            className="flex-1 bg-transparent p-4 text-[11px] font-mono text-cyan-300 focus:outline-none resize-none scrollbar-hide"
          />
        </div>

        <div className="flex-1 overflow-auto flex flex-col">
          <div className="px-4 py-2 bg-white/[0.02] border-b border-white/5">
            <span className="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Simulation Result</span>
          </div>
          
          <div className="flex-1 p-4 space-y-4">
            {result?.error ? (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-[11px] flex items-center gap-2">
                <XCircle className="w-4 h-4" />
                {result.error}{errorMessage ? `: ${errorMessage}` : ''}
              </div>
            ) : result ? (
              <>
                <div className={`p-4 rounded-xl border flex items-center justify-between ${
                  result.allow 
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                    : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                }`}>
                  <div className="flex items-center gap-3">
                    {result.allow ? <CheckCircle2 className="w-6 h-6" /> : <XCircle className="w-6 h-6" />}
                    <div>
                      <div className="text-lg font-bold leading-none">{result.allow ? 'ALLOW' : 'DENY'}</div>
                      <p className="text-[10px] opacity-60 uppercase tracking-widest mt-1">Decision made by Policy Engine</p>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                    <Info className="w-3 h-3" />
                    Reasons
                  </h3>
                  <div className="space-y-1">
                    {result.reasons?.map((r: any, i: number) => (
                      <div
                        key={i}
                        className={`text-[11px] pl-5 border-l py-1 ${
                          String(r.code || '').includes('DENY') || String(r.code || '').includes('FAIL')
                            ? 'text-amber-300 border-amber-500/30'
                            : 'text-gray-400 border-white/10'
                        }`}
                      >
                        <span className="text-violet-400 font-mono mr-2">[{r.code}]</span>
                        {r.summary}
                      </div>
                    ))}
                    {(!result.reasons || result.reasons.length === 0) && (
                      <p className="text-[10px] text-gray-600 italic">No specific reasons provided</p>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Intents / Targets</h3>
                  <div className="space-y-1">
                    {result.intents?.map((intent: any, i: number) => (
                      <div key={i} className="text-[11px] text-cyan-300 pl-4 border-l border-cyan-500/20 py-1 font-mono">
                        {intent.kind} - {intent.target}
                      </div>
                    ))}
                    {(!result.intents || result.intents.length === 0) && (
                      <p className="text-[10px] text-gray-600 italic">No intents emitted.</p>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-2 opacity-50 pt-8">
                <Shield className="w-8 h-8" />
                <p className="text-xs">Click simulate to test policies</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PolicySimulator;
