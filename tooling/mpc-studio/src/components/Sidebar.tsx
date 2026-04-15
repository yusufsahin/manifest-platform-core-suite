import { Activity, Database, EyeOff, FileText, Layers, Lock, Shield, Workflow } from 'lucide-react';
import type { MenuGroup } from '../lib/capabilityRouter';

interface ValidationSummary {
  status?: string;
  ast_hash?: string;
  errors?: unknown[];
  ast?: {
    defs: any[];
  };
}

interface SidebarProps {
  result: ValidationSummary | null;
  files: File[];
  activeFile: string;
  onOpenFolder?: () => void;
  onFileSelect: (fileName: string) => void;
  activeTab: string;
  onTabChange: (tab: string) => void;
  isEmbedded?: boolean;
  menuGroups?: MenuGroup[];
}

const defaultMenuGroups: MenuGroup[] = [
    {
      group: 'Authoring',
      items: [
        { id: 'editor', icon: 'FileText', label: 'Manifest Editor' },
        { id: 'registry', icon: 'Database', label: 'Domain Registry' },
      ],
    },
    {
      group: 'Security',
      items: [
        { id: 'security', icon: 'Shield', label: 'Policy Simulator' },
        { id: 'redaction', icon: 'EyeOff', label: 'Redaction Preview' },
        { id: 'acl', icon: 'Lock', label: 'ACL Explorer' },
      ],
    },
    {
      group: 'Runtime',
      items: [
        { id: 'governance', icon: 'Activity', label: 'Governance' },
        { id: 'workflow', icon: 'Workflow', label: 'Workflow Engine' },
        { id: 'overlays', icon: 'Layers', label: 'Overlay System' },
      ],
    },
];

const iconMap = {
  FileText,
  Database,
  Shield,
  EyeOff,
  Lock,
  Activity,
  Workflow,
  Layers,
} as const;

const Sidebar = ({ result, files, activeFile, onOpenFolder, onFileSelect, activeTab, onTabChange, isEmbedded, menuGroups }: SidebarProps) => {
  const resolvedMenuGroups = menuGroups ?? defaultMenuGroups;

  return (
    <aside className="w-[260px] glass-card m-4 mr-0 flex flex-col border border-white/10 overflow-hidden">
      <div className="p-6">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-[0.15em] mb-4">Navigation</h2>
        <div className="space-y-5 mb-6">
          {resolvedMenuGroups.map((section) => (
            <div key={section.group}>
              <p className="text-[10px] text-slate-500 uppercase tracking-[0.18em] mb-2">{section.group}</p>
              <div className="space-y-1">
                {section.items.map((item) => {
                  const Icon = iconMap[item.icon as keyof typeof iconMap];
                  return (
                    <button
                      key={item.id}
                      onClick={() => onTabChange(item.id)}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all group ${
                        activeTab === item.id
                          ? 'bg-blue-500/12 text-blue-300 border border-blue-500/30 shadow-lg shadow-blue-500/10'
                          : 'text-slate-400 hover:bg-slate-800/55 hover:text-slate-200 border border-transparent'
                      }`}
                    >
                      <Icon className={`w-4 h-4 transition-colors ${activeTab === item.id ? 'text-blue-300' : 'group-hover:text-slate-200'}`} />
                      <span className="text-[12px] font-medium tracking-wide">{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {!isEmbedded && (
          <>
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-[0.15em] mb-4">Workspace</h2>
            <div className="space-y-1 overflow-y-auto max-h-[300px] pr-2 scrollbar-hide">
              {files.length > 0 ? (
                files.map((file, i) => (
                  <button
                    key={i}
                    onClick={() => onFileSelect(file.name)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl transition-all ${
                      activeFile === file.name
                        ? 'bg-blue-600/12 text-blue-300 border border-blue-500/30 shadow-inner'
                        : 'text-slate-400 hover:bg-slate-800/55 hover:text-slate-200 border border-transparent'
                    }`}
                  >
                    <div className={`w-1.5 h-1.5 rounded-full ${activeFile === file.name ? 'bg-blue-300' : 'bg-slate-600'}`} />
                    <span className="text-[11px] font-medium truncate">{file.name}</span>
                  </button>
                ))
              ) : (
                <div className="rounded-xl border border-slate-700/70 bg-slate-900/60 p-3 space-y-2">
                  <p className="text-[11px] text-slate-300 font-medium">No folder opened</p>
                  <p className="text-[10px] text-slate-500">Open a folder to load manifest files and activate validation.</p>
                  {onOpenFolder ? (
                    <button
                      onClick={onOpenFolder}
                      className="text-[10px] font-semibold px-2.5 py-1.5 rounded-md bg-blue-500/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30 transition-colors"
                    >
                      Open Folder
                    </button>
                  ) : null}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="mt-auto p-6 border-t border-white/5">
        <div className="bg-slate-900/65 rounded-2xl p-4 border border-slate-700/70">
          <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Registry Artifact</h3>
          <div className="space-y-3">
            <div>
              <p className="text-[9px] text-slate-600 mb-1 uppercase">AST Hash</p>
              <p className="text-[10px] font-mono text-blue-300/80 truncate">{result?.ast_hash || 'pending...'}</p>
            </div>
            <div>
              <p className="text-[9px] text-slate-600 mb-1 uppercase">Definitions</p>
              <p className="text-[10px] font-bold text-slate-300">{result?.ast?.defs?.length || 0} Total</p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
