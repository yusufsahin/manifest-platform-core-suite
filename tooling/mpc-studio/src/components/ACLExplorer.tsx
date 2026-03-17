import { ShieldCheck, User, Play, Lock, CheckCircle, XCircle } from 'lucide-react';
import { useState } from 'react';
import { mpcEngine } from '../engine/mpc-engine';

const ACLExplorer = ({ definitions, dsl }: { definitions: any[], dsl: string }) => {
  const aclDefs = definitions.filter(d => d.kind === 'ACL' || d.kind === 'AccessControl');
  const [role, setRole] = useState('admin');
  const [resource, setResource] = useState('order');
  const [action, setAction] = useState('read');
  const [simResult, setSimResult] = useState<boolean | null>(null);

  const handleSimulate = async () => {
    try {
      const res = await mpcEngine.simulateACL(dsl, role, resource, action);
      setSimResult(res.allowed);
    } catch (e) {
      alert('Simulation Error: ' + e);
    }
  };
  
  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-violet-500/10 border border-violet-500/20">
            <ShieldCheck className="w-6 h-6 text-violet-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold tracking-tight">ACL Explorer</h2>
            <p className="text-sm text-gray-500">Analyze and test access control rules in your manifest.</p>
          </div>
        </div>
      </div>

      <div className="glass p-8 rounded-3xl border border-white/5 mb-8">
         <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-6 flex items-center gap-2">
           <Lock className="w-3 h-3 text-violet-400" /> PERMISSION SIMULATOR
         </h3>
         <div className="grid grid-cols-3 gap-4 items-end">
            <div className="space-y-2">
              <label className="text-[10px] text-gray-600 uppercase">Role</label>
              <input value={role} onChange={e => setRole(e.target.value)} className="w-full bg-black/20 border border-white/5 rounded-xl px-3 py-2 text-[11px] text-gray-300 focus:border-violet-500/30" />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] text-gray-600 uppercase">Resource</label>
              <input value={resource} onChange={e => setResource(e.target.value)} className="w-full bg-black/20 border border-white/5 rounded-xl px-3 py-2 text-[11px] text-gray-300 focus:border-violet-500/30" />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] text-gray-600 uppercase">Action</label>
              <div className="flex gap-2">
                <input value={action} onChange={e => setAction(e.target.value)} className="w-full bg-black/20 border border-white/5 rounded-xl px-3 py-2 text-[11px] text-gray-300 focus:border-violet-500/30" />
                <button 
                  onClick={handleSimulate}
                  className="px-4 py-2 bg-violet-600/20 text-violet-400 text-[11px] font-bold rounded-xl border border-violet-500/30 hover:bg-violet-600/30 transition-all"
                >
                  TEST
                </button>
              </div>
            </div>
         </div>
         {simResult !== null && (
            <div className={`mt-6 p-4 rounded-2xl border flex items-center gap-3 transition-all ${
              simResult ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
            }`}>
              {simResult ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
              <span className="text-[11px] font-bold uppercase tracking-widest">
                Access {simResult ? 'GRANTED' : 'DENIED'}
              </span>
            </div>
         )}
      </div>

      <div className="grid grid-cols-1 gap-4">
        {aclDefs.length > 0 ? (
          aclDefs.map((acl, i) => (
            <div key={i} className="glass p-6 rounded-2xl border border-white/5 hover:border-violet-500/30 transition-all group">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                   <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center">
                     <User className="w-4 h-4 text-gray-400" />
                   </div>
                   <h3 className="font-bold text-gray-200">{acl.id}</h3>
                </div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-violet-500/70 bg-violet-500/5 px-2 py-1 rounded-md border border-violet-500/10">
                  {acl.kind}
                </span>
              </div>
              <div className="space-y-2">
                 <pre className="text-[11px] font-mono text-gray-500 bg-black/20 p-3 rounded-xl">
                   {JSON.stringify(acl.properties, null, 2)}
                 </pre>
              </div>
            </div>
          ))
        ) : (
          <div className="h-[200px] flex flex-col items-center justify-center border-2 border-dashed border-white/5 rounded-3xl text-gray-600 italic">
            <p>No ACL definitions found in the current manifest.</p>
            <p className="text-[10px] mt-2 non-italic uppercase tracking-widest">Try adding "def ACL main { ... }"</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ACLExplorer;
