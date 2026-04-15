/**
 * Monaco Editor language support for MPC DSL.
 * Lightweight tokenizer + autocomplete + hover help.
 */
export function registerMpcDslLanguage(monaco: any): void {
  const existing = monaco.languages.getLanguages().find((l: any) => l.id === 'mpc-dsl');
  if (existing) return;

  monaco.languages.register({ id: 'mpc-dsl', extensions: ['.manifest', '.mpc'] });

  monaco.languages.setMonarchTokensProvider('mpc-dsl', {
    defaultToken: '',
    tokenPostfix: '.mpc',
    keywords: ['def', 'true', 'false', 'null'],
    tokenizer: {
      root: [
        [/\/\/.*$/, 'comment'],
        [/@(schema|namespace|name|version)\b/, 'keyword.directive'],
        [/\bdef\b/, 'keyword.def'],
        [/\b(true|false|null)\b/, 'constant.language'],
        [/"([^"\\]|\\.)*"/, 'string'],
        [/-?\d+\.\d+/, 'number.float'],
        [/-?\d+/, 'number'],
        [/[{}]/, 'delimiter.curly'],
        [/[\\[\\]]/, 'delimiter.bracket'],
        [/:/, 'delimiter.colon'],
        [/,/, 'delimiter.comma'],
        [/[a-zA-Z_][a-zA-Z0-9_.-]*/, { cases: { '@keywords': 'keyword', '@default': 'identifier' } }],
        [/\s+/, 'white'],
      ],
    },
  });

  monaco.editor.defineTheme('mpc-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'keyword.directive', foreground: 'C792EA', fontStyle: 'bold' },
      { token: 'keyword.def', foreground: '82AAFF', fontStyle: 'bold' },
      { token: 'constant.language', foreground: 'F78C6C' },
      { token: 'string', foreground: 'C3E88D' },
      { token: 'number', foreground: 'F78C6C' },
      { token: 'number.float', foreground: 'F78C6C' },
      { token: 'comment', foreground: '546E7A', fontStyle: 'italic' },
      { token: 'delimiter.colon', foreground: '89DDFF' },
      { token: 'identifier', foreground: 'EEFFFF' },
    ],
    colors: {
      'editor.background': '#12141c00',
    },
  });

  monaco.languages.registerCompletionItemProvider('mpc-dsl', {
    triggerCharacters: ['@', ' ', '\n'],
    provideCompletionItems(model: any, position: any) {
      const word = model.getWordUntilPosition(position);
      const lineContent = model.getLineContent(position.lineNumber);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };

      const suggestions: any[] = [];

      const directives = [
        { label: '@schema', detail: 'Schema version (integer)', insert: '@schema 1' },
        { label: '@namespace', detail: 'Manifest namespace', insert: '@namespace "${1:acme}"' },
        { label: '@name', detail: 'Manifest name', insert: '@name "${1:my-rules}"' },
        { label: '@version', detail: 'Semantic version', insert: '@version "${1:1.0.0}"' },
      ];

      for (const d of directives) {
        suggestions.push({
          label: d.label,
          kind: monaco.languages.CompletionItemKind.Keyword,
          detail: d.detail,
          insertText: d.insert,
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          range,
        });
      }

      const snippets = [
        { kind: 'Policy', snippet: 'def Policy ${1:id} "${2:Name}" {\n\teffect: "${3:allow}"\n\tpriority: ${4:10}\n\t$0\n}' },
        { kind: 'Workflow', snippet: 'def Workflow ${1:id} "${2:Name}" {\n\tinitial: "${3:START}"\n\tstates: ["${3:START}", "${4:DONE}"]\n\ttransitions: []\n\t$0\n}' },
        { kind: 'ACL', snippet: 'def ACL ${1:id} "${2:Name}" {\n\taction: "${3:read}"\n\tresource: "${4:*}"\n\troles: ["${5:admin}"]\n\teffect: "${6:allow}"\n\t$0\n}' },
        { kind: 'FormDef', snippet: 'def FormDef ${1:form_id} "${2:Form}" {\n\tworkflowState: "${3:draft}"\n\tworkflowTrigger: "${4:submit}"\n\tdef FieldDef ${5:field_id} "${6:Label}" {\n\t\ttype: "${7:string}"\n\t\trequired: ${8:true}\n\t}\n\t$0\n}' },
        { kind: 'FieldDef', snippet: 'def FieldDef ${1:field_id} "${2:Label}" {\n\ttype: "${3|string,number,boolean,select,multiselect,date,textarea,hidden|}"\n\trequired: ${4:false}\n\t$0\n}' },
      ];

      for (const s of snippets) {
        suggestions.push({
          label: `def ${s.kind}`,
          kind: monaco.languages.CompletionItemKind.Snippet,
          detail: `${s.kind} definition`,
          insertText: s.snippet,
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          range,
        });
      }

      if (lineContent.includes('type:')) {
        for (const t of ['string', 'number', 'boolean', 'select', 'multiselect', 'date', 'textarea', 'hidden']) {
          suggestions.push({
            label: `"${t}"`,
            kind: monaco.languages.CompletionItemKind.EnumMember,
            insertText: `"${t}"`,
            range,
          });
        }
      }

      return { suggestions };
    },
  });

  const kindDocs: Record<string, string> = {
    Policy: '**Policy** — Rule definition.',
    Workflow: '**Workflow** — FSM definition.',
    ACL: '**ACL** — Access control definition.',
    FormDef: '**FormDef** — Form definition.',
    FieldDef: '**FieldDef** — Field definition.',
  };

  monaco.languages.registerHoverProvider('mpc-dsl', {
    provideHover(model: any, position: any) {
      const word = model.getWordAtPosition(position);
      if (!word) return null;
      const doc = kindDocs[word.word];
      if (!doc) return null;
      return {
        range: new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn),
        contents: [{ value: doc }],
      };
    },
  });
}

