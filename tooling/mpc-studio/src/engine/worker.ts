import { loadPyodide, type PyodideInterface } from 'pyodide';

let pyodide: PyodideInterface | null = null;
let libraryLoaded = false;

async function initPyodide() {
  if (pyodide) return pyodide;
  
  pyodide = await loadPyodide({
    indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.29.3/full/'
  });
  
  await pyodide.runPythonAsync(`
    import sys
    import os
    import shutil
    
    # Setup working directory
    os.makedirs("/home/pyodide/mpc", exist_ok=True)
    sys.path.append("/home/pyodide")
  `);

  // lark is required by the MPC DSL parser; load it from the Pyodide package index.
  // lark is a pure-Python package available via micropip (bundled with Pyodide).
  await pyodide.loadPackage('micropip');
  await pyodide.runPythonAsync(`
    import micropip
    await micropip.install('lark')
  `);

  return pyodide;
}

async function loadMPCLibrary(py: PyodideInterface) {
  if (libraryLoaded) return;
  
  // In a real production app, we would fetch a zip or use a recursive fetcher.
  // For this standalone Studio, we'll implement a simple recursive module loader.
  
  const requiredFiles = [
    '__init__.py',
    'kernel/__init__.py',
    'kernel/ast/__init__.py',
    'kernel/ast/models.py',
    'kernel/ast/normalizer.py',
    'kernel/canonical/__init__.py',
    'kernel/canonical/hash.py',
    'kernel/canonical/serializer.py',
    'kernel/contracts/serialization.py',
    'kernel/errors/__init__.py',
    'kernel/errors/exceptions.py',
    'kernel/errors/registry.py',
    'kernel/meta/__init__.py',
    'kernel/meta/diff.py',
    'kernel/meta/models.py',
    'kernel/parser/__init__.py',
    'kernel/parser/base.py',
    'kernel/parser/dsl_frontend.py',
    'kernel/parser/grammar.lark',
    'kernel/parser/json_frontend.py',
    'kernel/parser/yaml_frontend.py',
    'kernel/contracts/__init__.py',
    'kernel/contracts/models.py',
    'tooling/__init__.py',
    'tooling/validator/__init__.py',
    'tooling/validator/structural.py',
    'tooling/validator/semantic.py',
    'features/__init__.py',
    'features/workflow/__init__.py',
    'features/workflow/fsm.py',
  ];

  const failed: string[] = [];

  for (const file of requiredFiles) {
    try {
      const response = await fetch(`/mpc/${file}`);
      if (!response.ok) {
        failed.push(`${file} (HTTP ${response.status})`);
        continue;
      }
      const content = await response.text();
      
      const parts = file.split('/');
      if (parts.length > 1) {
        let currentDir = "/home/pyodide/mpc";
        for (let i = 0; i < parts.length - 1; i++) {
          currentDir += "/" + parts[i];
          py.FS.mkdirTree(currentDir);
        }
      }
      
      py.FS.writeFile(`/home/pyodide/mpc/${file}`, content);
    } catch (e) {
      failed.push(`${file} (${String(e)})`);
    }
  }

  if (failed.length > 0) {
    throw new Error(`Failed to load required MPC files: ${failed.join(', ')}`);
  }

  await py.runPythonAsync(`
import mpc
from mpc.kernel.parser import parse
from mpc.tooling.validator.structural import validate_structural
from mpc.tooling.validator.semantic import validate_semantic
from mpc.kernel.meta.models import DomainMeta, KindDef
`);
  
  libraryLoaded = true;
}

self.onmessage = async (e) => {
  const { type, payload, id } = e.data;
  
  try {
    const py = await initPyodide();
    await loadMPCLibrary(py);
    
    if (type === 'PARSE_AND_VALIDATE') {
      const dsl = payload;

      py.globals.set('MPC_INPUT_DSL', dsl);
      let result: string;
      try {
        result = await py.runPythonAsync(`
import json
import hashlib
from mpc.kernel.parser import parse
from mpc.tooling.validator.structural import validate_structural
from mpc.tooling.validator.semantic import validate_semantic
from mpc.kernel.meta.models import DomainMeta, KindDef

def run_pipeline(dsl_text):
    try:
        # 1. Parse
        ast = parse(dsl_text)
        
        # 2. Structural Validation
        # Build permissive kinds from AST to avoid false unknown-kind noise in Studio preview.
        kind_names = sorted({node.kind for node in ast.defs if isinstance(node.kind, str)})
        meta = DomainMeta(kinds=[KindDef(name=name) for name in kind_names])
        struct_errors = validate_structural(ast, meta)
        
        # 3. Semantic Validation
        sem_errors = validate_semantic(ast)
        
        all_errors = struct_errors + sem_errors
        
        return {
            "status": "success",
            "namespace": ast.namespace,
            "ast_hash": hashlib.sha256(dsl_text.encode("utf-8")).hexdigest()[:16],
            "errors": [
                {"code": e.code, "message": e.message, "severity": e.severity}
                for e in all_errors
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "errors": [{"code": "E_PARSE_SYNTAX", "message": str(e), "severity": "error"}]
        }

json.dumps(run_pipeline(MPC_INPUT_DSL))
      `);
      } finally {
        py.globals.delete('MPC_INPUT_DSL');
      }

      self.postMessage({ id, type: 'RESULT', payload: JSON.parse(result) });
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    self.postMessage({ id, type: 'ERROR', payload: message });
  }
};
