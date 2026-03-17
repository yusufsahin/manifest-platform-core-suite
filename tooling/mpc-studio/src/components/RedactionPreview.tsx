import { EyeOff, Play } from 'lucide-react';
import { useState } from 'react';

const RedactionPreview = ({ dsl, onRedact }: { dsl: string, onRedact: (data: any) => Promise<any> }) => {
  const [sampleData, setSampleData] = useState('{\n  "name": "John Doe",\n  "email": "john@example.com",\n  "salary": 120000,\n  "ssn": "123-456-7890"\n}');
  const [redactedData, setRedactedData] = useState<any>(null);

  const handleRun = async () => {
    try {
      const data = JSON.parse(sampleData);
      const res = await onRedact(data);
      setRedactedData(res.data);
    } catch (e) {
      alert('Invalid JSON or Redaction Error: ' + e);
    }
  };

  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="flex items-center gap-4 mb-8">
        <div className="p-3 rounded-2xl bg-rose-500/10 border border-rose-500/20">
          <EyeOff className="w-6 h-6 text-rose-400" />
        </div>
        <div>
          <h2 className="text-xl font-bold tracking-tight">Redaction Preview</h2>
          <p className="text-sm text-gray-500">Test field-level redaction rules against sample data.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-4">
           <div className="flex items-center justify-between">
             <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Sample Data (JSON)</h3>
             <button 
               onClick={handleRun}
               className="flex items-center gap-2 px-3 py-1.5 bg-rose-500/20 text-rose-400 text-[10px] font-bold rounded-lg border border-rose-500/30 hover:bg-rose-500/30 transition-all"
             >
               <Play className="w-3 h-3" /> RUN REDACTION
             </button>
           </div>
           <textarea 
             value={sampleData}
             onChange={(e) => setSampleData(e.target.value)}
             className="w-full h-[300px] bg-black/40 border border-white/5 rounded-2xl p-4 font-mono text-[11px] text-gray-400 focus:outline-none focus:border-rose-500/30 transition-all"
           />
        </div>

        <div className="space-y-4">
           <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Redacted Output</h3>
           <div className="w-full h-[300px] bg-black/60 border border-white/5 rounded-3xl p-6 overflow-auto">
             {redactedData ? (
               <pre className="font-mono text-[11px] text-emerald-400/80">
                 {JSON.stringify(redactedData, null, 2)}
               </pre>
             ) : (
               <div className="h-full flex items-center justify-center text-gray-700 italic text-[11px]">
                 Click "Run Redaction" to see results
               </div>
             )}
           </div>
        </div>
      </div>
    </div>
  );
};

export default RedactionPreview;
