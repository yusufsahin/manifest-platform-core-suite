import { Database, FileCode, Layers, ShieldCheck, Activity } from 'lucide-react';

interface SidebarProps {
  dsl: string;
  result: any;
}

const Sidebar = ({ result }: SidebarProps) => {
  const menuItems = [
    { icon: FileCode, label: 'Manifest Editor', active: true },
    { icon: Database, label: 'Domain Registry', active: false },
    { icon: ShieldCheck, label: 'Security Policies', active: false },
    { icon: Activity, label: 'Workflow Engine', active: false },
    { icon: Layers, label: 'Overlay System', active: false },
  ];

  return (
    <aside className="w-[260px] glass-card m-4 mr-0 flex flex-col border border-white/10 overflow-hidden">
      <div className="p-6">
        <h2 className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-6">Explorer</h2>
        <div className="space-y-2">
          {menuItems.map((item, i) => (
            <button
              key={i}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                item.active 
                  ? 'bg-violet-600/10 text-violet-400 border border-violet-500/20 shadow-inner' 
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-300 border border-transparent'
              }`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-xs font-semibold">{item.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-auto p-6 border-t border-white/5">
        <div className="bg-white/5 rounded-2xl p-4 border border-white/5">
          <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-3">Registry Artifact</h3>
          <div className="space-y-3">
            <div>
              <p className="text-[9px] text-gray-600 mb-1 uppercase">AST Hash</p>
              <p className="text-[10px] font-mono text-violet-400/80 truncate">{result?.ast_hash || 'pending...'}</p>
            </div>
            <div>
              <p className="text-[9px] text-gray-600 mb-1 uppercase">Dependencies</p>
              <p className="text-[10px] font-bold text-gray-300">0 Total</p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
