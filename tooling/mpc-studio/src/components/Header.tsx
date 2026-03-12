import { Box, Play, Save, Settings, Share2 } from 'lucide-react';

const Header = () => {
  return (
    <header className="h-[56px] glass border-b border-white/5 flex items-center justify-between px-6 z-50">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-violet-500/20">
          <Box className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight text-white leading-none">MPC STUDIO</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">Manifest Platform Core</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 transition-all text-xs font-medium">
          <Save className="w-3.5 h-3.5" />
          <span>Save</span>
        </button>
        <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 transition-all text-xs font-medium">
          <Share2 className="w-3.5 h-3.5" />
          <span>Share</span>
        </button>
        <div className="w-px h-4 bg-white/10 mx-2" />
        <button className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 shadow-lg shadow-violet-600/20 transition-all text-xs font-bold text-white">
          <Play className="w-3.5 h-3.5 fill-current" />
          <span>RUN VALIDATION</span>
        </button>
        <button className="p-2 rounded-lg hover:bg-white/5 transition-all text-gray-400">
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
};

export default Header;
