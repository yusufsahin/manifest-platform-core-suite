import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';
import { mpcEngine } from '../engine/mpc-engine';

mermaid.initialize({
  startOnLoad: true,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#8b5cf6',
    primaryTextColor: '#fff',
    primaryBorderColor: '#a78bfa',
    lineColor: '#4b5563',
    secondaryColor: '#1e293b',
    tertiaryColor: '#111827',
  }
});

interface VisualizerProps {
  dsl: string;
  definitionId?: string;
  definitionKind?: string;
}


const Visualizer = ({ dsl, definitionId, definitionKind }: VisualizerProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const renderChart = async () => {
      const container = containerRef.current;
      if (!container) return;

      try {
        const preview = await mpcEngine.previewDefinition({
          dsl,
          definitionId,
          kindHint: definitionKind,
        });
        
        // Component might have unmounted while awaiting preview.
        if (containerRef.current !== container) return;
        container.replaceChildren();

        if (preview.renderer === 'mermaid') {
          if (preview.content && preview.content.trim().length > 0) {
            await mermaid.parse(preview.content, { suppressErrors: false });
            const renderId = `mpc-mermaid-${Date.now()}`;
            const { svg } = await mermaid.render(renderId, preview.content);
            if (containerRef.current !== container) return;
            container.innerHTML = svg;
          } else {
            const empty = document.createElement('div');
            empty.className = 'flex items-center justify-center h-full text-gray-600 text-xs italic';
            empty.textContent = 'No workflow definitions found to visualize.';
            container.appendChild(empty);
          }
        } else if (preview.renderer === 'json') {
          const pre = document.createElement('pre');
          pre.className = 'max-w-full text-[11px] text-gray-300 bg-black/20 border border-white/10 rounded-xl p-4 overflow-auto';
          pre.textContent = preview.content || '{}';
          container.appendChild(pre);
        } else {
          const empty = document.createElement('div');
          empty.className = 'flex items-center justify-center h-full text-gray-600 text-xs italic';
          empty.textContent = preview.content || 'No preview available for selected definition.';
          container.appendChild(empty);
        }
      } catch (err) {
        console.error('Mermaid error:', err);
        if (containerRef.current !== container) return;
        container.replaceChildren();
        const error = document.createElement('div');
        error.className = 'flex flex-col items-center justify-center h-full text-xs gap-2 px-6 text-center';
        const title = document.createElement('div');
        title.className = 'text-red-400 font-semibold';
        title.textContent = 'Mermaid render failed';
        const detail = document.createElement('div');
        detail.className = 'text-gray-400 font-mono break-all';
        detail.textContent = err instanceof Error ? err.message : String(err);
        error.appendChild(title);
        error.appendChild(detail);
        container.appendChild(error);
      }
    };

    renderChart();
  }, [dsl, definitionId, definitionKind]);

  return (
    <div className="h-full w-full flex flex-col">
      <div className="h-10 border-b border-white/5 flex items-center px-4 justify-between bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-500" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">Definition Preview</span>
        </div>
      </div>
      <div className="flex-1 p-8 overflow-auto flex items-center justify-center" ref={containerRef}>
        {/* Mermaid renders here */}
      </div>
    </div>
  );
};

export default Visualizer;
