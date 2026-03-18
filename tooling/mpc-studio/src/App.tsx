import { useState, useEffect, useRef } from 'react';
import { mpcEngine } from './engine/mpc-engine';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ManifestEditor from './components/ManifestEditor';
import Visualizer from './components/Visualizer';
import DebugPanel from './components/DebugPanel';
import DomainRegistry from './components/DomainRegistry';
import PolicySimulator from './components/PolicySimulator';
import UISchemaView from './components/UISchemaView';
import { StatusBadge } from './components/StatusBadge';
import ACLExplorer from './components/ACLExplorer';
import GovernanceDashboard from './components/GovernanceDashboard';
import RedactionPreview from './components/RedactionPreview';

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
  const [activeTab, setActiveTab ] = useState<'preview' | 'debug' | 'ui'>('preview');
  const [sidebarTab, setSidebarTab] = useState('editor');
  const [isEmbedded, setIsEmbedded] = useState(false);
  const validationTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('embedded') === 'true') {
      setIsEmbedded(true);
    }

    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'SET_DSL') {
        setDsl(event.data.dsl);
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  useEffect(() => {
    if (isEmbedded) {
      window.parent.postMessage({ type: 'UPDATE_DSL', dsl }, '*');
    }
  }, [dsl, isEmbedded]);

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

  const handleGenerateUISchema = async () => {
    return await mpcEngine.generateUISchema(dsl);
  };

  const handleSimulatePolicy = async (event: any) => {
    return await mpcEngine.evaluatePolicy(dsl, event);
  };

  const handleRedact = async (data: any) => {
    return await mpcEngine.redactData(dsl, data);
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
  const errorCount = validationErrors.filter((err: ValidationError) => err.severity === 'error').length;
  const warningCount = validationErrors.filter((err: ValidationError) => err.severity !== 'error').length;
  const hasValidationIssues = validationErrors.length > 0;

  return (
    <div className="flex flex-col h-screen w-full bg-[#0a0b10] text-[#f3f4f6] font-sans overflow-hidden">
      <Header 
        onOpenFolder={handleOpenFolder} 
        onSave={handleSave} 
        onRun={handleRun} 
        isSaving={isSaving} 
        debugMode={debugMode}
        onToggleDebug={() => setDebugMode(!debugMode)}
        isEmbedded={isEmbedded}
      />
      
      <div className="flex flex-1 overflow-hidden">
        <Sidebar 
          dsl={dsl} 
          result={result} 
          files={files} 
          activeFile={activeFileName}
          onOpenFolder={handleOpenFolder}
          onFileSelect={handleFileSelect}
          activeTab={sidebarTab} 
          onTabChange={setSidebarTab} 
          isEmbedded={isEmbedded}
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
              ) : sidebarTab === 'security' ? (
                <PolicySimulator onSimulate={handleSimulatePolicy} />
              ) : sidebarTab === 'redaction' ? (
                <RedactionPreview dsl={dsl} onRedact={handleRedact} />
              ) : sidebarTab === 'acl' ? (
                <ACLExplorer dsl={dsl} definitions={result?.status === 'success' ? (result.ast?.defs || []) : []} />
              ) : sidebarTab === 'governance' ? (
                <GovernanceDashboard />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500 text-xs italic">
                  Feature '{sidebarTab}' coming soon
                </div>
              )}
            </div>
          </div>
          
          <div className="flex-1 flex flex-col gap-4 overflow-hidden">
            <div className="flex-1 glass rounded-2xl overflow-hidden border border-white/10 relative flex flex-col">
              <div className="flex border-b border-slate-800 bg-slate-900/60 px-2 py-1 gap-1">
                <button 
                  onClick={() => setActiveTab('preview')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all border ${
                    activeTab === 'preview'
                      ? 'bg-blue-500/20 text-blue-200 border-blue-500/30'
                      : 'text-slate-500 border-transparent hover:text-slate-300 hover:bg-slate-800/60'
                  }`}
                >
                  Preview
                </button>
                <button 
                  onClick={() => setActiveTab('debug')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all border ${
                    activeTab === 'debug'
                      ? 'bg-blue-500/20 text-blue-200 border-blue-500/30'
                      : 'text-slate-500 border-transparent hover:text-slate-300 hover:bg-slate-800/60'
                  }`}
                >
                  Debugger
                </button>
                <button 
                  onClick={() => setActiveTab('ui')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all border ${
                    activeTab === 'ui'
                      ? 'bg-blue-500/20 text-blue-200 border-blue-500/30'
                      : 'text-slate-500 border-transparent hover:text-slate-300 hover:bg-slate-800/60'
                  }`}
                >
                  UI Schema
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                {activeTab === 'preview' ? (
                  <Visualizer dsl={dsl} />
                ) : activeTab === 'debug' ? (
                  <DebugPanel 
                    trace={debugResult?.trace || null} 
                    value={debugResult?.value} 
                    type={debugResult?.type || null}
                  />
                ) : (
                  <UISchemaView onGenerate={handleGenerateUISchema} />
                )}
              </div>
            </div>
            
            <div className="h-52 glass rounded-2xl p-4 border border-slate-700/70 overflow-auto">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Validation Output</h3>
                <div className="text-[11px] text-slate-400">
                  {hasValidationIssues ? `${errorCount} errors, ${warningCount} warnings` : 'No issues'}
                </div>
              </div>
              {hasValidationIssues ? (
                <div className="space-y-2">
                  {validationErrors.map((err: ValidationError, i: number) => (
                    <div
                      key={i}
                      className={`rounded-lg px-3 py-2 border font-mono text-xs ${
                        err.severity === 'error'
                          ? 'bg-red-500/8 border-red-500/30 text-red-300'
                          : 'bg-amber-500/8 border-amber-500/30 text-amber-300'
                      }`}
                    >
                      <div className="font-semibold mb-1">[{err.code}] {err.severity.toUpperCase()}</div>
                      <div>{err.message}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg px-3 py-2 border border-emerald-500/30 bg-emerald-500/8 text-emerald-300 text-sm font-mono">
                  Semantic and structural validation passed.
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
