import { useState, useEffect, useRef } from 'react';
import { mpcEngine } from './engine/mpc-engine';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ManifestEditor from './components/ManifestEditor';
import Visualizer from './components/Visualizer';
import DebugPanel from './components/DebugPanel';
import DomainRegistry from './components/DomainRegistry';
import { StatusBadge } from './components/StatusBadge';

const VALIDATION_DEBOUNCE_MS = 350;

interface ValidationError {
  code: string;
  message: string;
  severity: string;
  line?: number;
  col?: number;
  end_line?: number;
  end_col?: number;
}

interface ValidationResult {
  status: string;
  namespace?: string;
  ast_hash?: string;
  errors: ValidationError[];
  ast?: {
    defs: Array<{ kind: string; id: string; name?: string; properties: any }>;
  };
}

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
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [fileHandle, setFileHandle] = useState<FileSystemFileHandle | null>(null);
  const [folderHandle, setFolderHandle] = useState<FileSystemDirectoryHandle | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [activeFileName, setActiveFileName] = useState('Main.manifest');
  const [debugMode, setDebugMode] = useState(false);
  const [debugResult, setDebugResult] = useState<{ value: any; type: string | null; trace: any[] | null } | null>(null);
  const [activeTab, setActiveTab ] = useState<'preview' | 'debug'>('preview');
  const [sidebarTab, setSidebarTab] = useState('editor');
  const validationTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    if (validationTimeoutRef.current !== null) {
      window.clearTimeout(validationTimeoutRef.current);
    }

    validationTimeoutRef.current = window.setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await mpcEngine.parseAndValidate(dsl) as ValidationResult;
        setResult(res);

        if (debugMode && res.status === 'success') {
           // Auto-run a sample eval for now to show trace
           const evalRes = await mpcEngine.evaluateExpr('concat("User: ", data.user)', { data: { user: 'yusuf' } }, true);
           setDebugResult(evalRes);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }, VALIDATION_DEBOUNCE_MS);

    return () => {
      if (validationTimeoutRef.current !== null) {
        window.clearTimeout(validationTimeoutRef.current);
      }
    };
  }, [dsl]);

  const handleOpenFolder = async () => {
    try {
      const handle = await window.showDirectoryPicker();
      setFolderHandle(handle);
      const manifestFiles: File[] = [];
      for await (const entry of handle.values()) {
        if (entry.kind === 'file' && (entry.name.endsWith('.manifest') || entry.name.endsWith('.yaml') || entry.name.endsWith('.dsl'))) {
          const file = await (entry as FileSystemFileHandle).getFile();
          manifestFiles.push(file);
        }
      }
      setFiles(manifestFiles);
      if (manifestFiles.length > 0) {
        await handleFileSelect(manifestFiles[0].name, handle);
      }
    } catch (err) {
      console.error('Failed to open folder', err);
    }
  };

  const handleFileSelect = async (
    fileName: string,
    selectedFolderHandle?: FileSystemDirectoryHandle,
  ) => {
    const sourceFolder = selectedFolderHandle ?? folderHandle;
    if (!sourceFolder) return;

    try {
      const handle = await sourceFolder.getFileHandle(fileName);
      setFileHandle(handle);
      const file = await handle.getFile();
      const content = await file.text();
      setDsl(content);
      setActiveFileName(fileName);
    } catch (err) {
      console.error('Failed to select file', err);
    }
  };

  const handleSave = async () => {
    if (!fileHandle) {
      // Fallback to download or save as if no handle
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName: activeFileName,
          types: [{ description: 'Manifest File', accept: { 'text/plain': ['.manifest', '.dsl', '.yaml'] } }]
        });
        setFileHandle(handle);
        setActiveFileName(handle.name);
        const writable = await handle.createWritable();
        await writable.write(dsl);
        await writable.close();
      } catch (err) {
        console.error('Save cancelled or failed', err);
      }
      return;
    }

    setIsSaving(true);
    try {
      const writable = await fileHandle.createWritable();
      await writable.write(dsl);
      await writable.close();
    } catch (err) {
      console.error('Failed to save file', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRun = async () => {
    setIsLoading(true);
    try {
      const res = await mpcEngine.parseAndValidate(dsl);
      setResult(res as ValidationResult | null);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const validationErrors = result?.errors ?? [];

  return (
    <div className="flex flex-col h-screen w-full bg-[#0a0b10] text-[#f3f4f6] font-sans overflow-hidden">
      <Header 
        onOpenFolder={handleOpenFolder} 
        onSave={handleSave} 
        onRun={handleRun} 
        isSaving={isSaving} 
        debugMode={debugMode}
        onToggleDebug={() => setDebugMode(!debugMode)}
      />
      
      <div className="flex flex-1 overflow-hidden">
        <Sidebar 
          dsl={dsl} 
          result={result} 
          files={files} 
          activeFile={activeFileName}
          onFileSelect={handleFileSelect}
          activeTab={sidebarTab} 
          onTabChange={setSidebarTab} 
        />
        
        <main className="flex-1 flex gap-4 p-4 overflow-hidden">
          <div className="w-[45%] flex flex-col gap-4 overflow-hidden">
            <div className="flex-1 glass rounded-2xl overflow-hidden border border-white/10 relative">
              {sidebarTab === 'editor' ? (
                <ManifestEditor 
                  dsl={dsl} 
                  onChange={setDsl}
                  fileName={activeFileName}
                  errors={result?.status === 'error' ? (result.errors as any[]) : []}
                />
              ) : sidebarTab === 'registry' ? (
                <DomainRegistry 
                  definitions={result?.status === 'success' ? (result.ast?.defs || []) : []}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500 text-xs italic">
                  Feature '{sidebarTab}' coming soon
                </div>
              )}
            </div>
          </div>
          
          <div className="flex-1 flex flex-col gap-4 overflow-hidden">
            <div className="flex-1 glass rounded-2xl overflow-hidden border border-white/10 relative flex flex-col">
              <div className="flex border-b border-white/5 bg-white/[0.02] p-1 gap-1">
                <button 
                  onClick={() => setActiveTab('preview')}
                  className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                    activeTab === 'preview' ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  Preview
                </button>
                <button 
                  onClick={() => setActiveTab('debug')}
                  className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                    activeTab === 'debug' ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  Debugger
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                {activeTab === 'preview' ? (
                  <Visualizer dsl={dsl} />
                ) : (
                  <DebugPanel 
                    trace={debugResult?.trace || null} 
                    value={debugResult?.value} 
                    type={debugResult?.type || null}
                  />
                )}
              </div>
            </div>
            
            <div className="h-48 glass rounded-2xl p-4 border border-white/10 overflow-auto">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">Validation Output</h3>
              {validationErrors.length > 0 ? (
                <div className="space-y-2">
                  {validationErrors.map((err: ValidationError, i: number) => (
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
          <span>Engine: Pyodide 0.29.3</span>
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
