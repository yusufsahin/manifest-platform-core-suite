import Editor from '@monaco-editor/react';

interface ManifestEditorProps {
  dsl: string;
  onChange: (value: string) => void;
  fileName: string;
}

const ManifestEditor = ({ dsl, onChange, fileName }: ManifestEditorProps) => {
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
          defaultLanguage="python" // Temporary until custom language
          theme="vs-dark"
          value={dsl}
          onChange={(value) => onChange(value || '')}
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
            monaco.editor.defineTheme('mpc-theme', {
              base: 'vs-dark',
              inherit: true,
              rules: [],
              colors: {
                'editor.background': '#12141c00', // Transparent
              }
            });
          }}
        />
      </div>
    </div>
  );
};

export default ManifestEditor;
