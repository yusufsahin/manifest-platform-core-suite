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
}


const Visualizer = ({ dsl }: VisualizerProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const renderChart = async () => {
      if (!containerRef.current) return;

      try {
        const graphDefinition = await mpcEngine.getMermaid(dsl);
        
        containerRef.current.replaceChildren();

        if (graphDefinition && graphDefinition.trim().length > 0) {
          const mermaidNode = document.createElement('div');
          mermaidNode.className = 'mermaid';
          mermaidNode.textContent = graphDefinition;
          containerRef.current.appendChild(mermaidNode);
          await mermaid.run({
            nodes: [mermaidNode],
          });
        } else {
          const empty = document.createElement('div');
          empty.className = 'flex items-center justify-center h-full text-gray-600 text-xs italic';
          empty.textContent = 'No workflow definitions found to visualize.';
          containerRef.current.appendChild(empty);
        }
      } catch (err) {
        console.error('Mermaid error:', err);
      }
    };

    renderChart();
  }, [dsl]);

  return (
    <div className="h-full w-full flex flex-col">
      <div className="h-10 border-b border-white/5 flex items-center px-4 justify-between bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-500" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">Workflow Preview</span>
        </div>
      </div>
      <div className="flex-1 p-8 overflow-auto flex items-center justify-center" ref={containerRef}>
        {/* Mermaid renders here */}
      </div>
    </div>
  );
};

export default Visualizer;
