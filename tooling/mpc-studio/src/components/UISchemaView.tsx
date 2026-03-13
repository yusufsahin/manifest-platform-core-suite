import { FileJson, RefreshCw, AlertTriangle } from 'lucide-react';
import { useState } from 'react';

interface UISchemaViewProps {
  onGenerate: () => Promise<any>;
}

const UISchemaView = ({ onGenerate }: UISchemaViewProps) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    const res = await onGenerate();
    setData(res);
    setLoading(false);
  };

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileJson className="w-4 h-4 text-cyan-400" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-white">UI Schema Preview</h2>
        </div>
        <button 
          onClick={handleGenerate}
          disabled={loading}
          className="p-1.5 rounded-lg hover:bg-white/5 text-gray-500 hover:text-white transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {data ? (
          <div className="space-y-6">
            {data.warnings?.length > 0 && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-500 text-[10px] space-y-1">
                <div className="flex items-center gap-2 font-bold uppercase mb-1">
                   <AlertTriangle className="w-3.5 h-3.5" />
                   Warnings
                </div>
                {data.warnings.map((w: string, i: number) => <div key={i}>• {w}</div>)}
              </div>
            )}

            {Object.entries(data.schemas || {}).map(([key, schema]: [string, any]) => (
              <div key={key} className="space-y-2">
                <div className="flex items-center gap-2 border-b border-white/5 pb-1">
                  <span className="text-[10px] font-mono text-cyan-400 uppercase">{key.split(':')[0]}</span>
                  <span className="text-[11px] font-bold text-white">{key.split(':')[1]}</span>
                </div>
                <pre className="text-[10px] font-mono text-gray-500 bg-white/[0.02] p-3 rounded-lg overflow-x-auto">
                  {JSON.stringify(schema, null, 2)}
                </pre>
              </div>
            ))}

            {Object.keys(data.schemas || {}).length === 0 && (
              <div className="py-12 flex flex-col items-center justify-center text-gray-600 gap-2">
                <FileJson className="w-8 h-8 opacity-10" />
                <p className="text-[10px] italic">No schema generated</p>
              </div>
            )}
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-4 opacity-50">
             <div className="p-6 rounded-3xl bg-white/[0.02] border border-white/5">
               <FileJson className="w-12 h-12" />
             </div>
             <div className="text-center space-y-1">
               <p className="text-xs font-bold uppercase tracking-widest text-white">Generate UI Schema</p>
               <p className="text-[10px] max-w-[200px]">Auto-generate JSON schemas and form definitions from current manifest</p>
             </div>
             <button 
              onClick={handleGenerate}
              className="px-6 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-[10px] font-bold text-white transition-all"
             >
               FETCH SCHEMAS
             </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UISchemaView;
