import { Activity, Database, EyeOff, FileText, Layers, Lock, Shield, Workflow } from 'lucide-react';

interface ValidationSummary {
  status?: string;
  ast_hash?: string;
  errors?: unknown[];
  ast?: {
    defs: any[];
  };
}

interface SidebarProps {
  dsl: string;
  result: ValidationSummary | null;
  files: File[];
  activeFile: string;
  onFileSelect: (fileName: string) => void;
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const Sidebar = ({ result, files, activeFile, onFileSelect, activeTab, onTabChange }: SidebarProps) => {
  const menuItems = [
    { id: 'editor', icon: FileText, label: 'Manifest Editor' },
    { id: 'registry', icon: Database, label: 'Domain Registry' },
    { id: 'security', icon: Shield, label: 'Security Policies' },
    { id: 'redaction', icon: EyeOff, label: 'Redaction Preview' },
    { id: 'acl', icon: Lock, label: 'ACL Explorer' },
    { id: 'governance', icon: Activity, label: 'Governance' },
    { id: 'workflow', icon: Workflow, label: 'Workflow Engine' },
    { id: 'overlays', icon: Layers, label: 'Overlay System' },
  ];

  return (
    <aside className="w-[260px] glass-card m-4 mr-0 flex flex-col border border-white/10 overflow-hidden">
      <div className="p-6">
        <h2 className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-4">Navigation</h2>
        <div className="space-y-1 mb-6">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all group ${
                activeTab === item.id 
                  ? 'bg-violet-500/10 text-violet-400 border border-violet-500/20 shadow-lg shadow-violet-500/5' 
                  : 'text-gray-500 hover:bg-white/5 hover:text-gray-300 border border-transparent'
              }`}
            >
              <item.icon className={`w-4 h-4 transition-colors ${activeTab === item.id ? 'text-violet-400' : 'group-hover:text-gray-300'}`} />
              <span className="text-[11px] font-semibold tracking-wide">{item.label}</span>
            </button>
          ))}
        </div>

        <h2 className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-4">Workspace</h2>
        <div className="space-y-1 overflow-y-auto max-h-[300px] pr-2 scrollbar-hide">
          {files.length > 0 ? (
            files.map((file, i) => (
              <button
                key={i}
                onClick={() => onFileSelect(file.name)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl transition-all ${
                  activeFile === file.name
                    ? 'bg-violet-600/10 text-violet-400 border border-violet-500/20 shadow-inner'
                    : 'text-gray-400 hover:bg-white/5 hover:text-gray-300 border border-transparent'
                }`}
              >
                <div className={`w-1.5 h-1.5 rounded-full ${activeFile === file.name ? 'bg-violet-400' : 'bg-gray-600'}`} />
                <span className="text-[11px] font-medium truncate">{file.name}</span>
              </button>
            ))
          ) : (
            <div className="text-[10px] text-gray-600 italic px-3">No folder opened</div>
          )}
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
              <p className="text-[9px] text-gray-600 mb-1 uppercase">Definitions</p>
              <p className="text-[10px] font-bold text-gray-300">{result?.ast?.defs?.length || 0} Total</p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
