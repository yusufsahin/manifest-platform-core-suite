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
  const [isSaving, setIsSaving] = useState(false);
  const [fileHandle, setFileHandle] = useState<FileSystemFileHandle | null>(null);
  const [folderHandle, setFolderHandle] = useState<FileSystemDirectoryHandle | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [activeFileName, setActiveFileName] = useState('Main.manifest');

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
        handleFileSelect(manifestFiles[0].name);
      }
    } catch (err) {
      console.error('Failed to open folder', err);
    }
  };

  const handleFileSelect = async (fileName: string) => {
    if (!folderHandle) return;
    try {
      const handle = await folderHandle.getFileHandle(fileName);
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
      setResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-full bg-[#0a0b10] text-[#f3f4f6] font-sans overflow-hidden">
      <Header 
        onOpenFolder={handleOpenFolder} 
        onSave={handleSave} 
        onRun={handleRun} 
        isSaving={isSaving} 
      />
      
      <div className="flex flex-1 overflow-hidden">
        <Sidebar 
          dsl={dsl} 
          result={result} 
          files={files} 
          activeFile={activeFileName}
          onFileSelect={handleFileSelect}
        />
        
        <main className="flex-1 flex overflow-hidden p-4 gap-4 bg-[#0a0b10]">
          <div className="flex-1 glass rounded-2xl overflow-hidden flex flex-col border border-white/10">
            <ManifestEditor 
              dsl={dsl} 
              onChange={setDsl} 
              fileName={activeFileName}
            />
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
