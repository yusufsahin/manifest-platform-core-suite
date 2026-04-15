import { useEffect, useRef } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { registerMpcDslLanguage } from '../engine/mpc-dsl-language';

interface ValidationError {
  code: string;
  message: string;
  severity: string;
  line?: number;
  col?: number;
  end_line?: number;
  end_col?: number;
}

interface ManifestEditorProps {
  dsl: string;
  onChange: (value: string) => void;
  fileName: string;
  errors?: ValidationError[];
}

const ManifestEditor = ({ dsl, onChange, fileName, errors = [] }: ManifestEditorProps) => {
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);

  useEffect(() => {
    if (editorRef.current && monacoRef.current) {
      const markers = errors
        .filter(err => err.line !== undefined)
        .map(err => ({
          startLineNumber: err.line!,
          startColumn: err.col! + 1, // Monaco is 1-based
          endLineNumber: err.end_line || err.line!,
          endColumn: (err.end_col || err.col!) + 1,
          message: `[${err.code}] ${err.message}`,
          severity: err.severity === 'error' 
            ? monacoRef.current.MarkerSeverity.Error 
            : monacoRef.current.MarkerSeverity.Warning,
        }));

      monacoRef.current.editor.setModelMarkers(
        editorRef.current.getModel(),
        'mpc',
        markers
      );
    }
  }, [errors]);

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
  };

  return (
    <div className="h-full w-full flex flex-col">
      <div className="h-10 border-b border-white/5 flex items-center px-4 justify-between bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-violet-500 shadow-sm shadow-violet-500/50" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-gray-300">{fileName}</span>
        </div>
        <span className="text-[10px] text-gray-600 font-mono">UTF-8</span>
      </div>
      <div className="flex-1">
        <Editor
          height="100%"
          defaultLanguage="mpc-dsl"
          theme="mpc-dark"
          value={dsl}
          onChange={(value) => onChange(value || '')}
          onMount={handleEditorDidMount}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "'JetBrains Mono', monospace",
            lineNumbers: 'on',
            roundedSelection: true,
            scrollBeyondLastLine: false,
            readOnly: false,
            automaticLayout: true,
            padding: { top: 20 },
          }}
          beforeMount={(monaco) => {
            registerMpcDslLanguage(monaco);
          }}
        />
      </div>
    </div>
  );
};

export default ManifestEditor;
