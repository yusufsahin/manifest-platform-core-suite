import { Box, Play, Save, Settings, FolderOpen, Bug } from 'lucide-react';

interface HeaderProps {
  onOpenFolder: () => void;
  onSave: () => void;
  onRun: () => void;
  isSaving?: boolean;
  debugMode?: boolean;
  onToggleDebug?: () => void;
  isEmbedded?: boolean;
}

const Header = ({ onOpenFolder, onSave, onRun, isSaving, debugMode, onToggleDebug, isEmbedded }: HeaderProps) => {
  if (isEmbedded) return null;
  return (
    <header className="glass border-b border-white/5 px-6 py-3 z-50">
      <div className="flex items-start justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-teal-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Box className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white leading-none">MPC STUDIO</h1>
            <p className="text-xs text-slate-400 mt-1">Manifest Platform Core</p>
          </div>
        </div>
        <div className="hidden lg:flex items-center text-xs text-slate-400 gap-2">
          <span className="font-semibold text-slate-300">Quick start:</span>
          <span>Open a folder, edit manifest, run validation.</span>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-3">
        <button 
          onClick={onOpenFolder}
          className="btn-primary flex items-center gap-2 px-4 py-2 rounded-lg transition-all text-xs font-semibold"
        >
          <FolderOpen className="w-3.5 h-3.5" />
          <span>Open Folder</span>
        </button>
        <button 
          onClick={onSave}
          disabled={isSaving}
          className="btn-secondary flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-xs font-medium disabled:opacity-50"
        >
          <Save className="w-3.5 h-3.5" />
          <span>{isSaving ? 'Saving...' : 'Save'}</span>
        </button>
        <button 
          onClick={onToggleDebug}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all text-xs font-medium ${
            debugMode 
              ? 'bg-amber-500/12 text-amber-300 border-amber-500/30' 
              : 'bg-slate-900/60 text-slate-400 border-slate-700 hover:bg-slate-800/70'
          }`}
          title="Toggle Debug Mode (Enables Expression Tracing)"
        >
          <Bug className="w-3.5 h-3.5" />
          <span>Debug Mode</span>
        </button>
        <div className="w-px h-4 bg-slate-700 mx-1" />
        <button 
          onClick={onRun}
          className="btn-secondary flex items-center gap-2 px-4 py-2 rounded-lg transition-all text-xs font-semibold"
        >
          <Play className="w-3.5 h-3.5 fill-current" />
          <span>Run Validation</span>
        </button>
        <button className="p-2 rounded-lg hover:bg-slate-800/70 transition-all text-slate-400">
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
};

export default Header;
