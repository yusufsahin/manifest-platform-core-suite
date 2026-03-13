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

function sanitizeNodeId(value: string): string {
  const cleaned = value.trim().replace(/[^A-Za-z0-9_]/g, '_');
  return cleaned.length > 0 ? cleaned : 'state_unknown';
}

function sanitizeEdgeLabel(value: string): string {
  // Keep labels readable while blocking Mermaid/HTML control characters.
  return value.trim().replace(/[^A-Za-z0-9 _-]/g, '_').slice(0, 80);
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

        containerRef.current.replaceChildren();

        if (workflowMatch && transitionsMatch.length > 0) {
          let graphDefinition = 'graph TD\n';
          transitionsMatch.forEach(m => {
            const from = sanitizeNodeId(m[1]);
            const on = sanitizeEdgeLabel(m[2]);
            const to = sanitizeNodeId(m[3]);
            graphDefinition += `    ${from} -- ${on} --> ${to}\n`;
          });

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
