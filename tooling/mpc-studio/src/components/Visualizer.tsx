import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

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

      // Extract Workflow for simple visualization
      // In reality, this would be computed by MPC Engine (from_ast_node -> to_mermaid)
      try {
        const workflowMatch = dsl.match(/states:\s*\[([^\]]+)\]/);
        const transitionsMatch = [...dsl.matchAll(/{"from":\s*"([^"]+)",\s*"on":\s*"([^"]+)",\s*"to":\s*"([^"]+)"}/g)];

        if (workflowMatch && transitionsMatch.length > 0) {
          let graphDefinition = 'graph TD\n';
          transitionsMatch.forEach(m => {
            graphDefinition += `    ${m[1]} -- ${m[2]} --> ${m[3]}\n`;
          });
          
          containerRef.current.innerHTML = `<div class="mermaid">${graphDefinition}</div>`;
          await mermaid.run({
            nodes: [containerRef.current.querySelector('.mermaid') as HTMLElement],
          });
        } else {
          containerRef.current.innerHTML = '<div class="flex items-center justify-center h-full text-gray-600 text-xs italic">No workflow definitions found to visualize.</div>';
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
