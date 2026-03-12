import { loadPyodide, type PyodideInterface } from 'pyodide';

let pyodide: PyodideInterface | null = null;
let libraryLoaded = false;

async function initPyodide() {
  if (pyodide) return pyodide;
  
  pyodide = await loadPyodide({
    indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/'
  });
  
  await pyodide.runPythonAsync(`
    import sys
    import os
    import shutil
    
    # Setup working directory
    os.makedirs("/home/pyodide/mpc", exist_ok=True)
    sys.path.append("/home/pyodide")
  `);

  return pyodide;
}

async function loadMPCLibrary(py: PyodideInterface) {
  if (libraryLoaded) return;
  
  // In a real production app, we would fetch a zip or use a recursive fetcher.
  // For this standalone Studio, we'll implement a simple recursive module loader.
  
  const files = [
    '__init__.py',
    'kernel/__init__.py',
    'kernel/ast/__init__.py',
    'kernel/ast/models.py',
    'kernel/meta/__init__.py',
    'kernel/meta/models.py',
    'kernel/parser/__init__.py',
    'kernel/parser/base.py',
    'kernel/parser/dsl_frontend.py',
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

  for (const file of files) {
    try {
      const response = await fetch(`/mpc/${file}`);
      if (!response.ok) continue;
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
      console.error(`Failed to load ${file}`, e);
    }
  }
  
  libraryLoaded = true;
}

self.onmessage = async (e) => {
  const { type, payload, id } = e.data;
  
  try {
    const py = await initPyodide();
    await loadMPCLibrary(py);
    
    if (type === 'PARSE_AND_VALIDATE') {
      const dsl = payload;
      
      const result = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.tooling.validator.structural import validate_structural
from mpc.tooling.validator.semantic import validate_semantic
from mpc.kernel.meta.models import DomainMeta
from mpc.kernel.contracts.models import Error

def run_pipeline(dsl_text):
    try:
        # 1. Parse
        ast = parse(dsl_text)
        
        # 2. Structural Validation
        # Use a dummy meta for now if none provided
        meta = DomainMeta(name="studio_default", kinds={}, allowed_functions={})
        struct_errors = validate_structural(ast, meta)
        
        # 3. Semantic Validation
        sem_errors = validate_semantic(ast, meta)
        
        all_errors = struct_errors + sem_errors
        
        return {
            "status": "success",
            "namespace": ast.namespace,
            "ast_hash": "...", # Compute hash if needed
            "errors": [
                {"code": e.code, "message": e.message, "severity": e.severity}
                for e in all_errors
            ]
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "errors": [{"code": "E_PARSE", "message": str(e), "severity": "error"}]}

json.dumps(run_pipeline("""${dsl.replace(/"""/g, '\\"\\"\\"') }"""))
      `);
      
      self.postMessage({ id, type: 'RESULT', payload: JSON.parse(result) });
    }
  } catch (err: any) {
    self.postMessage({ id, type: 'ERROR', payload: err.message });
  }
};
