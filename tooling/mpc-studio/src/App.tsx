import { useState, useEffect } from 'react';
import { mpcEngine } from './engine/mpc-engine';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ManifestEditor from './components/ManifestEditor';
import Visualizer from './components/Visualizer';
import { StatusBadge } from './components/StatusBadge';

const DEFAULT_DSL = `@schema 1
@namespace "demo.crm"
@name "customer_flow"
@version "1.0.0"

def Workflow onboarding "Onboarding" {
    initial: "START"
    states: ["START", "QUALIFYING", "DONE"]
    transitions: [
        {"from": "START", "on": "begin", "to": "QUALIFYING"},
        {"from": "QUALIFYING", "on": "finish", "to": "DONE"}
    ]
}`;

function App() {
  const [dsl, setDsl] = useState(DEFAULT_DSL);
  const [result, setResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const validate = async () => {
      try {
        const res = await mpcEngine.parseAndValidate(dsl);
        setResult(res);
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    validate();
  }, [dsl]);

  return (
    <div className="flex flex-col h-screen w-full bg-[#0a0b10] text-[#f3f4f6] font-sans overflow-hidden">
      <Header />
      
      <div className="flex flex-1 overflow-hidden">
        <Sidebar dsl={dsl} result={result} />
        
        <main className="flex-1 flex overflow-hidden p-4 gap-4 bg-[#0a0b10]">
          <div className="flex-1 glass rounded-2xl overflow-hidden flex flex-col border border-white/10">
            <ManifestEditor dsl={dsl} onChange={setDsl} />
          </div>
          
          <div className="flex-1 flex flex-col gap-4 overflow-hidden">
            <div className="flex-1 glass rounded-2xl overflow-hidden border border-white/10 relative">
              <Visualizer dsl={dsl} />
            </div>
            
            <div className="h-48 glass rounded-2xl p-4 border border-white/10 overflow-auto">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">Validation Output</h3>
              {result?.errors?.length > 0 ? (
                <div className="space-y-2">
                  {result.errors.map((err: any, i: number) => (
                    <div key={i} className="text-sm text-red-400 font-mono">
                      [{err.code}] {err.message}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-emerald-400 font-mono">
                  ✓ Semantic & structural validation passed.
                </div>
              )}
            </div>
          </div>
        </main>
      </div>

      <footer className="h-8 glass-card border-t border-white/5 flex items-center px-4 justify-between text-[10px] text-gray-500 uppercase tracking-widest">
        <div className="flex items-center gap-4">
          <span>Engine: Pyodide 0.25.0</span>
          <span>Core: MPC 0.1.0</span>
        </div>
        <div className="flex items-center gap-4">
          <StatusBadge status={isLoading ? 'loading' : 'ready'} />
          <span>Namespace: {result?.namespace || 'none'}</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
