import { Database, Search, FileCode } from 'lucide-react';
import { useMemo, useState } from 'react';

interface Definition {
  kind: string;
  id: string;
  name?: string;
}

interface DomainRegistryProps {
  definitions: Definition[];
  onSelectDefinition?: (def: Definition) => void;
}

const DomainRegistry = ({ definitions, onSelectDefinition }: DomainRegistryProps) => {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return definitions;
    return definitions.filter((d) => {
      const kind = (d.kind ?? '').toLowerCase();
      const id = (d.id ?? '').toLowerCase();
      const name = (d.name ?? '').toLowerCase();
      return kind.includes(q) || id.includes(q) || name.includes(q);
    });
  }, [definitions, query]);

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold uppercase tracking-widest text-white">Domain Registry</h2>
          </div>
          <span className="text-[10px] bg-cyan-500/10 text-cyan-400 px-2 py-0.5 rounded-full border border-cyan-500/20">
            {filtered.length} ITEMS
          </span>
        </div>
        
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input 
            type="text" 
            placeholder="Search definitions..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-lg py-1.5 pl-9 pr-4 text-xs text-white placeholder:text-gray-600 focus:outline-none focus:border-violet-500/50 transition-colors"
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-2">
        <div className="space-y-1">
          {filtered.map((def, i) => (
            <div 
              key={i}
              className="group flex items-center justify-between p-2 rounded-lg hover:bg-white/5 border border-transparent hover:border-white/5 transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-lg bg-white/5 flex items-center justify-center text-gray-500 group-hover:text-violet-400 transition-colors">
                  <FileCode className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="text-[11px] font-bold text-gray-200 group-hover:text-white transition-colors">{def.id}</div>
                  <div className="text-[9px] text-gray-500 font-mono uppercase tracking-tighter">{def.kind}</div>
                </div>
              </div>
              <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  onClick={() => onSelectDefinition?.(def)}
                  className="text-[9px] font-bold text-violet-400 hover:text-violet-300 uppercase tracking-widest"
                >
                  Detail
                </button>
              </div>
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="py-12 flex flex-col items-center justify-center text-gray-600 gap-2">
              <Database className="w-8 h-8 opacity-10" />
              <p className="text-[10px] italic">No definitions in current manifest</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DomainRegistry;
