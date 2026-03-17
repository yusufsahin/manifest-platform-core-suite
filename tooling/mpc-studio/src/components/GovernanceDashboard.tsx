import { Activity, Fingerprint, ShieldAlert, CheckCircle2 } from 'lucide-react';

const GovernanceDashboard = () => {
  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="flex items-center gap-4 mb-8">
        <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20">
          <Activity className="w-6 h-6 text-amber-400" />
        </div>
        <div>
          <h2 className="text-xl font-bold tracking-tight">Governance Dashboard</h2>
          <p className="text-sm text-gray-500">Monitor manifest integrity, signing, and activation protocols.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="glass p-6 rounded-2xl border border-white/5">
           <div className="flex items-center gap-3 mb-4">
             <Fingerprint className="w-5 h-5 text-violet-400" />
             <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Bundle Integrity</h3>
           </div>
           <div className="space-y-4">
             <div className="flex items-center justify-between text-xs">
               <span className="text-gray-500">Hashing Algo</span>
               <span className="text-gray-300 font-mono">SHA-256 (Canonical)</span>
             </div>
             <div className="flex items-center justify-between text-xs">
               <span className="text-gray-500">Current Hash</span>
               <span className="text-emerald-400 font-mono">Verified ✓</span>
             </div>
           </div>
        </div>

        <div className="glass p-6 rounded-2xl border border-white/5">
           <div className="flex items-center gap-3 mb-4">
             <ShieldAlert className="w-5 h-5 text-amber-400" />
             <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Signing Status</h3>
           </div>
           <div className="flex items-center justify-center h-12 bg-amber-500/5 border border-amber-500/10 rounded-xl">
             <span className="text-[10px] font-bold text-amber-500/80 uppercase tracking-widest">Awaiting HMAC-SHA256 Signature</span>
           </div>
        </div>
      </div>

      <div className="glass p-6 rounded-3xl border border-white/5 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-5">
           <CheckCircle2 className="w-32 h-32" />
        </div>
        <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider mb-6">Activation Protocol</h3>
        <div className="space-y-2">
           {[
             { step: 'Artifact Upload', status: 'Completed', color: 'text-emerald-400' },
             { step: 'Semantic Verification', status: 'Completed', color: 'text-emerald-400' },
             { step: 'Attestation Check', status: 'Pending', color: 'text-amber-400' },
             { step: 'Atomic Swap', status: 'Inhibited', color: 'text-gray-600' },
           ].map((s, i) => (
             <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/5">
               <span className="text-xs text-gray-400">{s.step}</span>
               <span className={`text-[10px] font-bold uppercase tracking-widest ${s.color}`}>{s.status}</span>
             </div>
           ))}
        </div>
      </div>
    </div>
  );
};

export default GovernanceDashboard;
