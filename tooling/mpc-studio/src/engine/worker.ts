import { loadPyodide, type PyodideInterface } from 'pyodide';

let pyodide: PyodideInterface | null = null;
let libraryLoaded = false;
let runtimeLock: Promise<void> = Promise.resolve();

const PYODIDE_CDN =
  (import.meta as any)?.env?.VITE_PYODIDE_CDN_URL ??
  'https://cdn.jsdelivr.net/pyodide/v0.29.3/full/';

interface WorkflowLimits {
  maxSteps: number;
  maxPayloadBytes: number;
  maxEventNameLength: number;
}

interface FormLimits {
  maxDslBytes: number;
  maxDataBytes: number;
  maxActorBytes: number;
}

function estimateBytes(value: unknown): number {
  try {
    return new TextEncoder().encode(JSON.stringify(value)).length;
  } catch {
    return Number.MAX_SAFE_INTEGER;
  }
}

function toWorkflowErrorCode(code?: string): string {
  const map: Record<string, string> = {
    E_WF_UNKNOWN_TRANSITION: 'INVALID_TRANSITION',
    E_WF_GUARD_FAIL: 'GUARD_FAILED',
    E_WF_AUTH_DENIED: 'AUTHZ_DENIED',
    E_WF_NO_INITIAL: 'NO_INITIAL_STATE',
    E_WF_INVALID_INITIAL: 'NO_INITIAL_STATE',
    E_WF_UNKNOWN_STATE: 'UNKNOWN_STATE',
  };
  if (!code) return 'WORKFLOW_EXECUTION_FAILED';
  return map[code] ?? code;
}

function remediationHintFor(errorCode: string): string {
  const hints: Record<string, string> = {
    INVALID_TRANSITION: 'Use one of the available transitions for the current state.',
    GUARD_FAILED: 'Provide missing context fields or adjust guard expression.',
    AUTHZ_DENIED: 'Grant required actor roles or update transition auth rules.',
    NO_INITIAL_STATE: 'Define a valid workflow initial state in DSL.',
    UNKNOWN_STATE: 'Ensure transition references existing states only.',
    WORKFLOW_PAYLOAD_TOO_LARGE: 'Reduce context payload size and retry.',
    STEP_LIMIT_EXCEEDED: 'Increase maxSteps limit or shorten the event queue.',
    EVENT_NAME_TOO_LONG: 'Use a shorter event name.',
  };
  return hints[errorCode] ?? 'Inspect transition, guard, and actor context.';
}

const DEFINITION_CONTRACT_VERSION = '2.0.0';

function readEnvNumber(name: string, fallback: number): number {
  try {
    const raw = (import.meta as any)?.env?.[name];
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function readEnvBool(name: string, fallback: boolean): boolean {
  try {
    const raw = (import.meta as any)?.env?.[name];
    if (raw === undefined || raw === '') return fallback;
    const s = String(raw).toLowerCase().trim();
    if (['1', 'true', 'yes', 'on'].includes(s)) return true;
    if (['0', 'false', 'no', 'off'].includes(s)) return false;
    return fallback;
  } catch {
    return fallback;
  }
}

function getFormLimits(): FormLimits {
  return {
    maxDslBytes: readEnvNumber('VITE_MPC_FORM_MAX_DSL_BYTES', 256_000),
    maxDataBytes: readEnvNumber('VITE_MPC_FORM_MAX_DATA_BYTES', 64_000),
    maxActorBytes: readEnvNumber('VITE_MPC_FORM_MAX_ACTOR_BYTES', 32_000),
  };
}

type EnvelopeDiagnostic = {
  code: string;
  message: string;
  severity: 'info' | 'warning' | 'error';
};

function nowIso(): string {
  return new Date().toISOString();
}

function postEnvelope(id: string, type: string, requestId: string, payload: unknown, startedAt: number, diagnostics: EnvelopeDiagnostic[] = []) {
  self.postMessage({
    id,
    type: 'RESULT',
    payload: {
      contractVersion: DEFINITION_CONTRACT_VERSION,
      requestId,
      timestamp: nowIso(),
      type,
      payload,
      diagnostics,
      durationMs: Date.now() - startedAt,
    },
  });
}

async function initPyodide() {
  if (pyodide) return pyodide;
  
  pyodide = await loadPyodide({
    indexURL: PYODIDE_CDN,
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
    await micropip.install(['lark', 'pyyaml'])
  `);

  return pyodide;
}

function safeDeleteGlobal(py: PyodideInterface, name: string) {
  try {
    py.globals.delete(name);
  } catch {
    // Ignore cleanup failures to avoid masking primary runtime errors.
  }
}

/** Fallback when `/mpc/manifest.json` is missing or filtering yields nothing. */
const FALLBACK_REQUIRED_FILES: string[] = [
  '__init__.py',
  'kernel/__init__.py',
  'kernel/ast/__init__.py',
  'kernel/ast/models.py',
  'kernel/ast/normalizer.py',
  'kernel/canonical/__init__.py',
  'kernel/canonical/hash.py',
  'kernel/canonical/ordering.py',
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
  'tooling/uischema/__init__.py',
  'tooling/uischema/generator.py',
  'features/__init__.py',
  'features/expr/__init__.py',
  'features/expr/engine.py',
  'features/expr/ir.py',
  'features/expr/compiler.py',
  'features/acl/__init__.py',
  'features/acl/engine.py',
  'features/workflow/__init__.py',
  'features/workflow/fsm.py',
  'features/form/__init__.py',
  'features/form/engine.py',
  'features/form/kinds.py',
];

function shouldIncludeRuntimePy(relPath: string): boolean {
  if (!relPath.endsWith('.py')) return false;
  if (relPath.includes('__pycache__')) return false;
  const patterns = [
    /^__init__\.py$/,
    /^kernel\//,
    /^tooling\/__init__\.py$/,
    /^tooling\/validator\//,
    /^tooling\/uischema\//,
    /^features\/__init__\.py$/,
    /^features\/(workflow|form|expr|acl)\//,
  ];
  return patterns.some((re) => re.test(relPath));
}

/** Lark grammar is required by the DSL parser; not a .py file. */
function shouldIncludeRuntimeFile(relPath: string): boolean {
  if (relPath.includes('__pycache__')) return false;
  if (relPath === 'kernel/parser/grammar.lark') return true;
  return shouldIncludeRuntimePy(relPath);
}

async function resolveRuntimeFileList(): Promise<string[]> {
  try {
    const response = await fetch('/mpc/manifest.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const manifest: unknown = await response.json();
    if (!Array.isArray(manifest)) throw new Error('manifest.json must be a JSON array');
    const filtered = manifest
      .filter((p): p is string => typeof p === 'string' && shouldIncludeRuntimeFile(p))
      .sort((a, b) => a.localeCompare(b));
    if (filtered.length === 0) throw new Error('filtered manifest is empty');
    return filtered;
  } catch {
    return FALLBACK_REQUIRED_FILES.slice();
  }
}

async function loadMPCLibrary(py: PyodideInterface) {
  if (libraryLoaded) return;

  const requiredFiles = await resolveRuntimeFileList();

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

  // The source-level mpc/__init__.py can import enterprise packages that are not
  // loaded in Studio's lightweight runtime bundle. Keep a minimal package init
  // so imports like `from mpc.kernel.parser import parse` remain stable.
  py.FS.writeFile(
    '/home/pyodide/mpc/__init__.py',
    '__version__ = "0.1.0"\n__all__ = ["kernel", "features", "tooling"]\n',
  );

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
  const waitForPrevious = runtimeLock;
  let releaseLock!: () => void;
  runtimeLock = new Promise<void>((resolve) => {
    releaseLock = resolve;
  });
  await waitForPrevious;

  const { type, payload, id } = e.data;
  const startedAt = Date.now();
  const requestId = typeof id === 'string' && id.length > 0 ? id : crypto.randomUUID();
  
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
from mpc.kernel.canonical.hash import stable_hash

def to_dict(node):
    return {
        "kind": node.kind,
        "id": node.id,
        "name": node.name,
        # ASTNode.properties is MappingProxyType in canonical AST; convert for JSON.
        "properties": dict(getattr(node, "properties", {}) or {}),
    }

def hash_ast(ast):
    payload = {
        "schema_version": ast.schema_version,
        "namespace": ast.namespace,
        "name": ast.name,
        "manifest_version": ast.manifest_version,
        "defs": [to_dict(d) for d in ast.defs],
    }
    return stable_hash(payload)

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
            "manifest_version": ast.manifest_version,
            "ast_hash": hash_ast(ast),
            "ast": { "defs": [to_dict(d) for d in ast.defs] },
            "errors": [
                {
                    "code": e.code, 
                    "message": e.message, 
                    "severity": e.severity,
                    "line": e.source.line if e.source else None,
                    "col": e.source.col if e.source else None,
                    "end_line": e.source.span.line2 if e.source and getattr(e.source, "span", None) else None,
                    "end_col": e.source.span.col2 if e.source and getattr(e.source, "span", None) else None,
                }
                for e in all_errors
            ]
        }
    except Exception as e:
        # Check if e has source info (MPCError)
        err_data = {"code": getattr(e, "code", "E_PARSE_SYNTAX"), "message": str(e), "severity": "error"}
        if hasattr(e, "source") and e.source:
             source_span = getattr(e.source, "span", None)
             err_data.update({
                "line": e.source.line,
                "col": e.source.col,
                "end_line": getattr(source_span, "line2", e.source.line),
                "end_col": getattr(source_span, "col2", e.source.col)
             })
        return {
            "status": "error",
            "message": str(e),
            "errors": [err_data]
        }

json.dumps(run_pipeline(MPC_INPUT_DSL))
      `);
      } finally {
        safeDeleteGlobal(py, 'MPC_INPUT_DSL');
      }

      self.postMessage({ id, type: 'RESULT', payload: JSON.parse(result) });
    } else if (type === 'LIST_DEFINITIONS') {
      const payloadData = payload as { dsl: string };
      py.globals.set('MPC_INPUT_DSL', payloadData.dsl);
      try {
        const raw = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse

ast = parse(MPC_INPUT_DSL)
items = []
for idx, node in enumerate(ast.defs):
    node_id = str(getattr(node, "id", "") or "").strip() or f"definition_{idx + 1}"
    node_name = str(getattr(node, "name", "") or "").strip() or node_id
    node_kind = str(getattr(node, "kind", "") or "").strip() or "Unknown"
    node_version = "1.0.0"
    props = getattr(node, "properties", None)
    if isinstance(props, dict):
        version = props.get("version")
        if isinstance(version, str) and version.strip():
            node_version = version.strip()
    items.append({
        "id": node_id,
        "name": node_name,
        "kind": node_kind,
        "version": node_version
    })

json.dumps({"items": items})
        `);
        const parsed = JSON.parse(raw as string) as {
          items: Array<{ id: string; name: string; kind: string; version: string }>;
        };
        const items = parsed.items.map((item) => {
          const capabilities = (() => {
            if (item.kind === 'Workflow') return ['preview_mermaid', 'simulate_workflow', 'diagnostics'];
            if (item.kind === 'Policy') return ['preview_json', 'simulate_policy', 'diagnostics'];
            if (item.kind === 'ACL' || item.kind === 'AccessControl') return ['preview_json', 'simulate_acl', 'diagnostics'];
            if (item.kind === 'FormDef') return ['preview_json', 'diagnostics'];
            if (item.kind === 'Overlay' || item.kind === 'OverlayRule' || item.kind === 'Projection' || item.kind === 'ViewOverlay') {
              return ['preview_json', 'diagnostics'];
            }
            return ['preview_json', 'inspector', 'diagnostics'];
          })();
          const diagnostics: EnvelopeDiagnostic[] = item.kind === 'Workflow' || item.kind === 'Policy' || item.kind === 'ACL' || item.kind === 'AccessControl' || item.kind === 'Overlay' || item.kind === 'OverlayRule' || item.kind === 'Projection' || item.kind === 'ViewOverlay'
            ? []
            : [{ code: 'UNKNOWN_KIND_FALLBACK', message: `Kind '${item.kind}' is routed to generic inspector fallback.`, severity: 'warning' }];
          return {
            id: item.id,
            name: item.name,
            kind: item.kind,
            version: item.version,
            capabilities,
            diagnostics,
          };
        });
        postEnvelope(id, type, requestId, { items }, startedAt);
      } finally {
        safeDeleteGlobal(py, 'MPC_INPUT_DSL');
      }
    } else if (type === 'PREVIEW_DEFINITION') {
      const payloadData = payload as { dsl: string; definitionId?: string; kindHint?: string };
      py.globals.set('MPC_INPUT_DSL', payloadData.dsl);
      py.globals.set('MPC_DEFINITION_ID', payloadData.definitionId ?? null);
      py.globals.set('MPC_KIND_HINT', payloadData.kindHint ?? null);
      try {
        const raw = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.workflow import WorkflowEngine

ast = parse(MPC_INPUT_DSL)

def _pick_node(ast_obj, definition_id=None, kind_hint=None):
    target = str(definition_id).strip().lower() if definition_id else ""
    hint = str(kind_hint).strip().lower() if kind_hint else ""
    for node in ast_obj.defs:
        node_id = str(getattr(node, "id", "") or "").strip()
        node_name = str(getattr(node, "name", "") or "").strip()
        node_kind = str(getattr(node, "kind", "") or "").strip()
        if target and node_id.lower() != target and node_name.lower() != target:
            continue
        if hint and node_kind.lower() != hint:
            continue
        return node
    for node in ast_obj.defs:
        node_kind = str(getattr(node, "kind", "") or "").strip()
        if hint and node_kind.lower() == hint:
            return node
    return ast_obj.defs[0] if ast_obj.defs else None

node = _pick_node(ast, MPC_DEFINITION_ID, MPC_KIND_HINT)
if node is None:
    result_json = json.dumps({
        "kind": "Unknown",
        "definitionId": str(MPC_DEFINITION_ID or ""),
        "renderer": "text",
        "content": "No definitions found in manifest.",
        "diagnostics": [{"code": "NO_DEFINITION_FOUND", "message": "No definitions found in manifest.", "severity": "warning"}]
    })
else:
    node_kind = str(getattr(node, "kind", "") or "").strip() or "Unknown"
    node_id = str(getattr(node, "id", "") or "").strip()
    if node_kind == "Workflow":
        try:
            engine = WorkflowEngine.from_ast_node(node)
            mermaid = engine.to_mermaid() if engine else ""
            result_json = json.dumps({
                "kind": node_kind,
                "definitionId": node_id,
                "renderer": "mermaid",
                "content": mermaid,
                "diagnostics": []
            })
        except Exception as error:
            result_json = json.dumps({
                "kind": node_kind,
                "definitionId": node_id,
                "renderer": "text",
                "content": str(error),
                "diagnostics": [{"code": "WORKFLOW_PREVIEW_FAILED", "message": str(error), "severity": "error"}]
            })
    else:
        props = getattr(node, "properties", None)
        result_json = json.dumps({
            "kind": node_kind,
            "definitionId": node_id,
            "renderer": "json",
            "content": json.dumps(dict(props) if props is not None else {}, indent=2),
            "diagnostics": []
        })
result_json
        `);
        postEnvelope(id, type, requestId, JSON.parse(raw as string), startedAt);
      } finally {
        safeDeleteGlobal(py, 'MPC_INPUT_DSL');
        safeDeleteGlobal(py, 'MPC_DEFINITION_ID');
        safeDeleteGlobal(py, 'MPC_KIND_HINT');
      }
    } else if (type === 'SIMULATE_DEFINITION') {
      const payloadData = payload as { dsl: string; definitionId?: string; kindHint?: string; input?: unknown };
      const input = payloadData.input ?? {};
      const normalizedKind = String(payloadData.kindHint ?? '').trim();
      if (normalizedKind === 'ACL' || normalizedKind === 'AccessControl') {
        const role = String((input as { role?: string }).role ?? '').toLowerCase().trim();
        const action = String((input as { action?: string }).action ?? '').toLowerCase().trim();
        const privilegedRoles = new Set(['admin', 'owner', 'security_admin']);
        const readonlyActions = new Set(['read', 'list', 'view', 'inspect']);
        const allowed = privilegedRoles.has(role) || readonlyActions.has(action);
        postEnvelope(
          id,
          type,
          requestId,
          {
            kind: normalizedKind || 'ACL',
            definitionId: payloadData.definitionId,
            status: 'success',
            output: { allowed, reason: allowed ? 'Allowed by default ACL policy.' : 'Denied by default ACL policy.' },
            diagnostics: [],
          },
          startedAt,
        );
      } else if (normalizedKind === 'Policy') {
        py.globals.set('DSL', payloadData.dsl);
        py.globals.set('EVENT', JSON.stringify(input));
        try {
          const result = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.policy import PolicyEngine
from mpc.kernel.meta.models import DomainMeta, KindDef

ast = parse(DSL)
meta = DomainMeta(kinds=[KindDef(name="Policy")])
engine = PolicyEngine(ast=ast, meta=meta)
res = engine.evaluate(json.loads(EVENT))

json.dumps({
    "allow": res.allow,
    "reasons": [{"code": r.code, "summary": r.summary} for r in res.reasons],
    "intents": [{"kind": i.kind, "target": i.target} for i in res.intents]
})
          `);
          postEnvelope(
            id,
            type,
            requestId,
            {
              kind: 'Policy',
              definitionId: payloadData.definitionId,
              status: 'success',
              output: JSON.parse(result as string),
              diagnostics: [],
            },
            startedAt,
          );
        } finally {
          safeDeleteGlobal(py, 'DSL');
          safeDeleteGlobal(py, 'EVENT');
        }
      } else if (normalizedKind === 'Workflow') {
        const event = String((input as { event?: string }).event ?? 'begin');
        const context = (input as { context?: unknown }).context ?? {};
        const actorId = String((input as { actorId?: string }).actorId ?? 'operator-1');
        const actorRoles = Array.isArray((input as { actorRoles?: unknown[] }).actorRoles)
          ? ((input as { actorRoles?: unknown[] }).actorRoles ?? []).map((role) => String(role))
          : ['operator'];
        py.globals.set('WF_DSL', payloadData.dsl);
        py.globals.set('WF_EVENT', event);
        py.globals.set('WF_CONTEXT', JSON.stringify(context));
        py.globals.set('WF_CURRENT', null);
        py.globals.set('WF_INITIAL', null);
        py.globals.set('WF_ACTOR_ID', actorId);
        py.globals.set('WF_ACTOR_ROLES', JSON.stringify(actorRoles));
        py.globals.set('WF_WORKFLOW_ID', payloadData.definitionId ?? null);
        try {
          const raw = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.workflow import WorkflowEngine
ast = parse(WF_DSL)
def _pick_workflow_engine(ast_obj, workflow_id=None):
    target = str(workflow_id).strip() if workflow_id else ""
    if target:
        target_lower = target.lower()
        for node in ast_obj.defs:
            node_id = str(getattr(node, "id", "") or "").strip()
            node_name = str(getattr(node, "name", "") or "").strip()
            if node_id.lower() != target_lower and node_name.lower() != target_lower:
                continue
            try:
                engine = WorkflowEngine.from_ast_node(node)
                if getattr(engine, "states", None) and getattr(engine, "transitions", None):
                    return engine
            except Exception:
                continue
    for node in ast_obj.defs:
        try:
            engine = WorkflowEngine.from_ast_node(node)
            if getattr(engine, "states", None) and getattr(engine, "transitions", None):
                return engine
        except Exception:
            continue
    return None
engine = _pick_workflow_engine(ast, WF_WORKFLOW_ID)
if engine is None:
    result_json = json.dumps({"allow": False, "errorCode": "NO_WORKFLOW_DEF", "message": "No Workflow definition found in manifest."})
else:
    result = engine.fire(WF_EVENT, actor_roles=json.loads(WF_ACTOR_ROLES), actor_id=WF_ACTOR_ID, context=json.loads(WF_CONTEXT))
    wf_errors = [{"code": e.code, "message": e.message} for e in result.errors]
    result_json = json.dumps({
      "allow": bool(result.decision.allow),
      "newState": result.new_state,
      "errors": wf_errors,
      "trace": result.trace
    })
result_json
          `);
          const parsed = JSON.parse(raw as string);
          const diagnostics: EnvelopeDiagnostic[] = parsed.errorCode
            ? [{ code: parsed.errorCode, message: parsed.message ?? parsed.errorCode, severity: 'error' }]
            : [];
          postEnvelope(
            id,
            type,
            requestId,
            {
              kind: 'Workflow',
              definitionId: payloadData.definitionId,
              status: diagnostics.length > 0 ? 'error' : 'success',
              output: parsed,
              diagnostics,
            },
            startedAt,
            diagnostics,
          );
        } finally {
          safeDeleteGlobal(py, 'WF_DSL');
          safeDeleteGlobal(py, 'WF_EVENT');
          safeDeleteGlobal(py, 'WF_CONTEXT');
          safeDeleteGlobal(py, 'WF_CURRENT');
          safeDeleteGlobal(py, 'WF_INITIAL');
          safeDeleteGlobal(py, 'WF_ACTOR_ID');
          safeDeleteGlobal(py, 'WF_ACTOR_ROLES');
          safeDeleteGlobal(py, 'WF_WORKFLOW_ID');
        }
      } else {
        postEnvelope(
          id,
          type,
          requestId,
          {
            kind: normalizedKind || 'Unknown',
            definitionId: payloadData.definitionId,
            status: 'error',
            output: null,
            diagnostics: [{ code: 'SIMULATOR_UNSUPPORTED_KIND', message: 'No simulator adapter for selected kind.', severity: 'warning' }],
          },
          startedAt,
          [{ code: 'SIMULATOR_UNSUPPORTED_KIND', message: 'No simulator adapter for selected kind.', severity: 'warning' }],
        );
      }
    } else if (type === 'MERMAID_EXPORT') {
      const payloadData =
        typeof payload === 'string' ? { dsl: payload, workflowId: null } : (payload as { dsl: string; workflowId?: string | null });
      py.globals.set('MPC_INPUT_DSL', payloadData.dsl);
      py.globals.set('MPC_WORKFLOW_ID', payloadData.workflowId ?? null);
      try {
        const mermaid = await py.runPythonAsync(`
from mpc.kernel.parser import parse
from mpc.features.workflow import WorkflowEngine
ast = parse(MPC_INPUT_DSL)
def _pick_workflow_engine(ast_obj, workflow_id=None):
    target = str(workflow_id).strip() if workflow_id else ""
    if target:
        target_lower = target.lower()
        for node in ast_obj.defs:
            node_id = str(getattr(node, "id", "") or "").strip()
            node_name = str(getattr(node, "name", "") or "").strip()
            if node_id.lower() != target_lower and node_name.lower() != target_lower:
                continue
            try:
                engine = WorkflowEngine.from_ast_node(node)
                if getattr(engine, "states", None) and getattr(engine, "transitions", None):
                    return engine
            except Exception:
                continue
    for node in ast_obj.defs:
        try:
            engine = WorkflowEngine.from_ast_node(node)
            if getattr(engine, "states", None) and getattr(engine, "transitions", None):
                return engine
        except Exception:
            continue
    return None

engine = _pick_workflow_engine(ast, MPC_WORKFLOW_ID)
engine.to_mermaid() if engine else ""
`);
        self.postMessage({ id, type: 'MERMAID_RESULT', payload: mermaid });
      } finally {
        safeDeleteGlobal(py, 'MPC_INPUT_DSL');
        safeDeleteGlobal(py, 'MPC_WORKFLOW_ID');
      }
    } else if (type === 'LIST_WORKFLOWS') {
      const payloadData = payload as { dsl: string };
      py.globals.set('MPC_INPUT_DSL', payloadData.dsl);
      try {
        const workflows = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.workflow import WorkflowEngine

ast = parse(MPC_INPUT_DSL)
items = []
for idx, node in enumerate(ast.defs):
    try:
        engine = WorkflowEngine.from_ast_node(node)
        if not getattr(engine, "states", None) or not getattr(engine, "transitions", None):
            continue
    except Exception:
        continue
    node_id = str(getattr(node, "id", "") or "").strip() or f"workflow_{idx + 1}"
    node_name = str(getattr(node, "name", "") or "").strip() or node_id
    node_kind = str(getattr(node, "kind", "") or "").strip() or "Workflow"
    items.append({"id": node_id, "name": node_name, "kind": node_kind})

json.dumps({"items": items})
        `);
        self.postMessage({ id, type: 'RESULT', payload: JSON.parse(workflows) });
      } finally {
        safeDeleteGlobal(py, 'MPC_INPUT_DSL');
      }
    } else if (type === 'EVALUATE_EXPR') {
      const { expr, context, enable_trace } = payload;
      py.globals.set('EXPR', expr);
      py.globals.set('CTX', JSON.stringify(context || {}));
      
      try {
        const result = await py.runPythonAsync(`
import json
from mpc.features.expr import ExprEngine
from mpc.kernel.meta.models import DomainMeta, FunctionDef

# permissive meta for eval
meta = DomainMeta(allowed_functions=[
    FunctionDef(name="len", args=["string|array"], returns="int"),
    FunctionDef(name="now", returns="string"),
    FunctionDef(name="concat", args=["any", "any"], returns="string"),
])
engine = ExprEngine(meta=meta)
ctx = json.loads(CTX)
res = engine.evaluate(EXPR, context=ctx, enable_trace=${enable_trace ? 'True' : 'False'})

json.dumps({
    "value": res.value,
    "type": res.type,
    "trace": res.trace if hasattr(res, 'trace') else None
})
`);
        self.postMessage({ id, type: 'EVAL_RESULT', payload: JSON.parse(result) });
      } finally {
        safeDeleteGlobal(py, 'EXPR');
        safeDeleteGlobal(py, 'CTX');
      }
    } else if (type === 'EVALUATE_POLICY') {
      const { event, dsl } = payload;
      py.globals.set('DSL', dsl);
      py.globals.set('EVENT', JSON.stringify(event));
      
      try {
        const result = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.policy import PolicyEngine
from mpc.kernel.meta.models import DomainMeta, KindDef

ast = parse(DSL)
meta = DomainMeta(kinds=[KindDef(name="Policy")]) # simplified meta
engine = PolicyEngine(ast=ast, meta=meta)
res = engine.evaluate(json.loads(EVENT))

json.dumps({
    "allow": res.allow,
    "reasons": [{"code": r.code, "summary": r.summary} for r in res.reasons],
    "intents": [{"kind": i.kind, "target": i.target} for i in res.intents]
})
`);
        self.postMessage({ id, type: 'POLICY_RESULT', payload: JSON.parse(result) });
      } finally {
        safeDeleteGlobal(py, 'DSL');
        safeDeleteGlobal(py, 'EVENT');
      }
    } else if (type === 'REDACT_DATA') {
      const { data } = payload as { data: unknown };
      const redactValue = (value: unknown): unknown => {
        if (typeof value === 'string') {
          return value
            .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[REDACTED_EMAIL]')
            .replace(/\+?\d[\d\-\s().]{7,}\d/g, '[REDACTED_PHONE]')
            .replace(/\b(?:sk|pk|token|secret|apikey|api_key)[-_]?[A-Z0-9]{6,}\b/gi, '[REDACTED_TOKEN]');
        }
        if (Array.isArray(value)) {
          return value.map((item) => redactValue(item));
        }
        if (value && typeof value === 'object') {
          return Object.fromEntries(
            Object.entries(value as Record<string, unknown>).map(([key, nested]) => {
              const lowered = key.toLowerCase();
              if (/(password|secret|token|apikey|api_key|ssn|salary)/.test(lowered)) {
                return [key, '[REDACTED]'];
              }
              return [key, redactValue(nested)];
            }),
          );
        }
        return value;
      };
      self.postMessage({ id, type: 'RESULT', payload: { data: redactValue(data) } });
    } else if (type === 'SIMULATE_ACL') {
      const { role, action } = payload as { role?: string; action?: string };
      const normalizedRole = String(role ?? '').toLowerCase().trim();
      const normalizedAction = String(action ?? '').toLowerCase().trim();
      const privilegedRoles = new Set(['admin', 'owner', 'security_admin']);
      const readonlyActions = new Set(['read', 'list', 'view', 'inspect']);
      const allowed = privilegedRoles.has(normalizedRole) || readonlyActions.has(normalizedAction);
      self.postMessage({
        id,
        type: 'RESULT',
        payload: {
          allowed,
          reason: allowed ? 'Allowed by default ACL policy.' : 'Denied by default ACL policy.',
        },
      });
    } else if (type === 'WORKFLOW_STEP') {
      const {
        dsl,
        workflowId,
        event,
        context,
        currentState,
        initialState,
        actorId,
        actorRoles,
        limits,
      } = payload as {
        dsl: string;
        workflowId?: string;
        event: string;
        context?: Record<string, unknown>;
        currentState?: string;
        initialState?: string;
        actorId: string;
        actorRoles: string[];
        tenantId: string;
        limits: WorkflowLimits;
      };

      const effectiveLimits = limits ?? { maxSteps: 100, maxPayloadBytes: 16_384, maxEventNameLength: 128 };
      const payloadBytes = estimateBytes(context ?? {});
      if (payloadBytes > effectiveLimits.maxPayloadBytes) {
        self.postMessage({
          id,
          type: 'RESULT',
          payload: {
            initialState: initialState ?? '',
            currentState: currentState ?? '',
            step: {
              stepId: crypto.randomUUID(),
              event,
              from: currentState ?? '',
              to: currentState ?? '',
              allow: false,
              guardResult: 'not_applicable',
              reasons: [{ code: 'WORKFLOW_PAYLOAD_TOO_LARGE', summary: 'Context payload exceeds configured limit.' }],
              errors: [{ code: 'WORKFLOW_PAYLOAD_TOO_LARGE', message: 'Context payload exceeds configured limit.' }],
              actionsExecuted: [],
              errorCode: 'WORKFLOW_PAYLOAD_TOO_LARGE',
              remediationHint: remediationHintFor('WORKFLOW_PAYLOAD_TOO_LARGE'),
              timestamp: new Date().toISOString(),
            },
            availableTransitions: [],
          },
        });
        return;
      }
      if ((event || '').length > effectiveLimits.maxEventNameLength) {
        self.postMessage({
          id,
          type: 'RESULT',
          payload: {
            initialState: initialState ?? '',
            currentState: currentState ?? '',
            step: {
              stepId: crypto.randomUUID(),
              event,
              from: currentState ?? '',
              to: currentState ?? '',
              allow: false,
              guardResult: 'not_applicable',
              reasons: [{ code: 'EVENT_NAME_TOO_LONG', summary: 'Event name exceeds configured length limit.' }],
              errors: [{ code: 'EVENT_NAME_TOO_LONG', message: 'Event name exceeds configured length limit.' }],
              actionsExecuted: [],
              errorCode: 'EVENT_NAME_TOO_LONG',
              remediationHint: remediationHintFor('EVENT_NAME_TOO_LONG'),
              timestamp: new Date().toISOString(),
            },
            availableTransitions: [],
          },
        });
        return;
      }

      py.globals.set('WF_DSL', dsl);
      py.globals.set('WF_EVENT', event);
      py.globals.set('WF_CONTEXT', JSON.stringify(context || {}));
      py.globals.set('WF_CURRENT', currentState ?? null);
      py.globals.set('WF_INITIAL', initialState ?? null);
      py.globals.set('WF_ACTOR_ID', actorId ?? '');
      py.globals.set('WF_ACTOR_ROLES', JSON.stringify(actorRoles || []));
      py.globals.set('WF_WORKFLOW_ID', workflowId ?? null);

      try {
        let parsed:
          | {
              initialState: string;
              currentState: string;
              step: {
                stepId: string;
                event: string;
                from: string;
                to: string;
                allow: boolean;
                guardResult: 'pass' | 'fail' | 'not_applicable';
                reasons: Array<{ code: string; summary?: string }>;
                errors: Array<{ code: string; message: string }>;
                actionsExecuted: string[];
                errorCode?: string;
                remediationHint?: string;
                timestamp?: string;
              };
              availableTransitions: Array<{ from: string; event: string; to: string; guard?: string | null }>;
            };
        try {
          const result = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.workflow import WorkflowEngine

ast = parse(WF_DSL)
def _pick_workflow_engine(ast_obj, workflow_id=None):
    target = str(workflow_id).strip() if workflow_id else ""
    if target:
        target_lower = target.lower()
        for node in ast_obj.defs:
            node_id = str(getattr(node, "id", "") or "").strip()
            node_name = str(getattr(node, "name", "") or "").strip()
            if node_id.lower() != target_lower and node_name.lower() != target_lower:
                continue
            try:
                engine = WorkflowEngine.from_ast_node(node)
                if getattr(engine, "states", None) and getattr(engine, "transitions", None):
                    return engine
            except Exception:
                continue
    for node in ast_obj.defs:
        try:
            engine = WorkflowEngine.from_ast_node(node)
            if getattr(engine, "states", None) and getattr(engine, "transitions", None):
                return engine
        except Exception:
            continue
    return None

engine = _pick_workflow_engine(ast, WF_WORKFLOW_ID)
if engine is None:
    json.dumps({
        "initialState": "",
        "currentState": "",
        "step": {
            "stepId": "wf-step-missing",
            "event": WF_EVENT,
            "from": "",
            "to": "",
            "allow": False,
            "guardResult": "not_applicable",
            "reasons": [{"code": "NO_WORKFLOW_DEF", "summary": "No Workflow definition found in manifest."}],
            "errors": [{"code": "NO_WORKFLOW_DEF", "message": "No Workflow definition found in manifest."}],
            "actionsExecuted": [],
            "errorCode": "NO_WORKFLOW_DEF"
        },
        "availableTransitions": []
    })
else:
    initial = WF_INITIAL or engine.initial_state
    if WF_CURRENT:
        engine.restore_state({"current_state": WF_CURRENT, "is_active": True})
    actor_roles = json.loads(WF_ACTOR_ROLES)
    result = engine.fire(
        WF_EVENT,
        actor_roles=actor_roles,
        actor_id=WF_ACTOR_ID,
        context=json.loads(WF_CONTEXT),
    )
    wf_errors = [{"code": e.code, "message": e.message} for e in result.errors]
    wf_reasons = [{"code": r.code, "summary": r.summary} for r in result.decision.reasons]
    err_code = wf_errors[0]["code"] if wf_errors else None
    guard_result = "not_applicable"
    if any(r.get("code") == "R_WF_GUARD_PASS" for r in wf_reasons):
        guard_result = "pass"
    elif any(r.get("code") == "R_WF_GUARD_FAIL" for r in wf_reasons):
        guard_result = "fail"

    transitions = [{
        "from": t.from_state,
        "event": t.on,
        "to": t.to_state,
        "guard": t.guard
    } for t in engine.available_transitions(actor_roles=actor_roles)]

    json.dumps({
        "initialState": initial,
        "currentState": result.new_state,
        "step": {
            "stepId": f"wf-step-{len(result.trace)}-{WF_EVENT}",
            "event": WF_EVENT,
            "from": WF_CURRENT or initial,
            "to": result.new_state,
            "allow": bool(result.decision.allow),
            "guardResult": guard_result,
            "reasons": wf_reasons,
            "errors": wf_errors,
            "actionsExecuted": result.actions_executed,
            "errorCode": err_code,
            "trace": result.trace
        },
        "availableTransitions": transitions
    })
`);
          parsed = JSON.parse(result as string) as typeof parsed;
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          parsed = {
            initialState: initialState ?? currentState ?? '',
            currentState: currentState ?? initialState ?? '',
            step: {
              stepId: crypto.randomUUID(),
              event,
              from: currentState ?? initialState ?? '',
              to: currentState ?? initialState ?? '',
              allow: false,
              guardResult: 'not_applicable',
              reasons: [{ code: 'WORKFLOW_EXECUTION_FAILED', summary: message }],
              errors: [{ code: 'WORKFLOW_EXECUTION_FAILED', message }],
              actionsExecuted: [],
              errorCode: 'WORKFLOW_EXECUTION_FAILED',
            },
            availableTransitions: [],
          };
        }

        const normalizedCode = toWorkflowErrorCode(parsed.step.errorCode);
        parsed.step.errorCode = normalizedCode === 'WORKFLOW_EXECUTION_FAILED' && parsed.step.allow ? undefined : normalizedCode;
        parsed.step.remediationHint = parsed.step.errorCode ? remediationHintFor(parsed.step.errorCode) : undefined;
        parsed.step.timestamp = new Date().toISOString();
        self.postMessage({ id, type: 'RESULT', payload: parsed });
      } finally {
        safeDeleteGlobal(py, 'WF_DSL');
        safeDeleteGlobal(py, 'WF_EVENT');
        safeDeleteGlobal(py, 'WF_CONTEXT');
        safeDeleteGlobal(py, 'WF_CURRENT');
        safeDeleteGlobal(py, 'WF_INITIAL');
        safeDeleteGlobal(py, 'WF_ACTOR_ID');
        safeDeleteGlobal(py, 'WF_ACTOR_ROLES');
        safeDeleteGlobal(py, 'WF_WORKFLOW_ID');
      }
    } else if (type === 'WORKFLOW_RUN') {
      const {
        dsl,
        workflowId,
        events,
        initialState,
        actorId,
        actorRoles,
        limits,
      } = payload as {
        dsl: string;
        workflowId?: string;
        events: Array<{ event: string; context?: Record<string, unknown> }>;
        initialState?: string;
        actorId: string;
        actorRoles: string[];
        tenantId: string;
        limits: WorkflowLimits;
      };

      const effectiveLimits = limits ?? { maxSteps: 100, maxPayloadBytes: 16_384, maxEventNameLength: 128 };
      if ((events || []).length > effectiveLimits.maxSteps) {
        self.postMessage({
          id,
          type: 'RESULT',
          payload: {
            initialState: initialState ?? '',
            currentState: initialState ?? '',
            steps: [
              {
                stepId: crypto.randomUUID(),
                event: 'run',
                from: initialState ?? '',
                to: initialState ?? '',
                allow: false,
                guardResult: 'not_applicable',
                reasons: [{ code: 'STEP_LIMIT_EXCEEDED', summary: 'Event queue length exceeds configured maxSteps.' }],
                errors: [{ code: 'STEP_LIMIT_EXCEEDED', message: 'Event queue length exceeds configured maxSteps.' }],
                actionsExecuted: [],
                errorCode: 'STEP_LIMIT_EXCEEDED',
                remediationHint: remediationHintFor('STEP_LIMIT_EXCEEDED'),
                timestamp: new Date().toISOString(),
              },
            ],
            availableTransitions: [],
          },
        });
        return;
      }

      let current = initialState;
      const steps: Array<Record<string, unknown>> = [];
      let discoveredInitial = initialState ?? '';
      let lastTransitions: Array<{ from: string; event: string; to: string; guard?: string | null }> = [];

      for (const item of events || []) {
        const payloadBytes = estimateBytes(item.context ?? {});
        if (payloadBytes > effectiveLimits.maxPayloadBytes) {
          steps.push({
            stepId: crypto.randomUUID(),
            event: item.event,
            from: current ?? discoveredInitial,
            to: current ?? discoveredInitial,
            allow: false,
            guardResult: 'not_applicable',
            reasons: [{ code: 'WORKFLOW_PAYLOAD_TOO_LARGE', summary: 'Context payload exceeds configured limit.' }],
            errors: [{ code: 'WORKFLOW_PAYLOAD_TOO_LARGE', message: 'Context payload exceeds configured limit.' }],
            actionsExecuted: [],
            errorCode: 'WORKFLOW_PAYLOAD_TOO_LARGE',
            remediationHint: remediationHintFor('WORKFLOW_PAYLOAD_TOO_LARGE'),
            timestamp: new Date().toISOString(),
          });
          break;
        }
        if ((item.event || '').length > effectiveLimits.maxEventNameLength) {
          steps.push({
            stepId: crypto.randomUUID(),
            event: item.event,
            from: current ?? discoveredInitial,
            to: current ?? discoveredInitial,
            allow: false,
            guardResult: 'not_applicable',
            reasons: [{ code: 'EVENT_NAME_TOO_LONG', summary: 'Event name exceeds configured length limit.' }],
            errors: [{ code: 'EVENT_NAME_TOO_LONG', message: 'Event name exceeds configured length limit.' }],
            actionsExecuted: [],
            errorCode: 'EVENT_NAME_TOO_LONG',
            remediationHint: remediationHintFor('EVENT_NAME_TOO_LONG'),
            timestamp: new Date().toISOString(),
          });
          break;
        }
        const stepResult = await (async () => {
          py.globals.set('WF_DSL', dsl);
          py.globals.set('WF_EVENT', item.event);
          py.globals.set('WF_CONTEXT', JSON.stringify(item.context || {}));
          py.globals.set('WF_CURRENT', current ?? null);
          py.globals.set('WF_INITIAL', discoveredInitial || null);
          py.globals.set('WF_ACTOR_ID', actorId ?? '');
          py.globals.set('WF_ACTOR_ROLES', JSON.stringify(actorRoles || []));
          py.globals.set('WF_WORKFLOW_ID', workflowId ?? null);
          try {
            try {
              const result = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.workflow import WorkflowEngine
ast = parse(WF_DSL)
def _pick_workflow_engine(ast_obj, workflow_id=None):
    target = str(workflow_id).strip() if workflow_id else ""
    if target:
        target_lower = target.lower()
        for node in ast_obj.defs:
            node_id = str(getattr(node, "id", "") or "").strip()
            node_name = str(getattr(node, "name", "") or "").strip()
            if node_id.lower() != target_lower and node_name.lower() != target_lower:
                continue
            try:
                engine = WorkflowEngine.from_ast_node(node)
                if getattr(engine, "states", None) and getattr(engine, "transitions", None):
                    return engine
            except Exception:
                continue
    for node in ast_obj.defs:
        try:
            engine = WorkflowEngine.from_ast_node(node)
            if getattr(engine, "states", None) and getattr(engine, "transitions", None):
                return engine
        except Exception:
            continue
    return None

engine = _pick_workflow_engine(ast, WF_WORKFLOW_ID)
if engine is None:
    json.dumps({"initialState": "", "currentState": "", "step": {"stepId": "wf-step-missing", "event": WF_EVENT, "from": "", "to": "", "allow": False, "guardResult": "not_applicable", "reasons": [{"code": "NO_WORKFLOW_DEF", "summary": "No Workflow definition found in manifest."}], "errors": [{"code": "NO_WORKFLOW_DEF", "message": "No Workflow definition found in manifest."}], "actionsExecuted": [], "errorCode": "NO_WORKFLOW_DEF"}, "availableTransitions": []})
else:
    initial = WF_INITIAL or engine.initial_state
    if WF_CURRENT:
        engine.restore_state({"current_state": WF_CURRENT, "is_active": True})
    actor_roles = json.loads(WF_ACTOR_ROLES)
    result = engine.fire(WF_EVENT, actor_roles=actor_roles, actor_id=WF_ACTOR_ID, context=json.loads(WF_CONTEXT))
    wf_errors = [{"code": e.code, "message": e.message} for e in result.errors]
    wf_reasons = [{"code": r.code, "summary": r.summary} for r in result.decision.reasons]
    err_code = wf_errors[0]["code"] if wf_errors else None
    guard_result = "not_applicable"
    if any(r.get("code") == "R_WF_GUARD_PASS" for r in wf_reasons): guard_result = "pass"
    elif any(r.get("code") == "R_WF_GUARD_FAIL" for r in wf_reasons): guard_result = "fail"
    transitions = [{"from": t.from_state, "event": t.on, "to": t.to_state, "guard": t.guard} for t in engine.available_transitions(actor_roles=actor_roles)]
    json.dumps({"initialState": initial, "currentState": result.new_state, "step": {"stepId": f"wf-step-{len(result.trace)}-{WF_EVENT}", "event": WF_EVENT, "from": WF_CURRENT or initial, "to": result.new_state, "allow": bool(result.decision.allow), "guardResult": guard_result, "reasons": wf_reasons, "errors": wf_errors, "actionsExecuted": result.actions_executed, "errorCode": err_code, "trace": result.trace}, "availableTransitions": transitions})
`);
              return JSON.parse(result as string) as {
                initialState: string;
                currentState: string;
                step: Record<string, unknown>;
                availableTransitions: Array<{ from: string; event: string; to: string; guard?: string | null }>;
              };
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              return {
                initialState: discoveredInitial || current || '',
                currentState: current || discoveredInitial || '',
                step: {
                  stepId: crypto.randomUUID(),
                  event: item.event,
                  from: current || discoveredInitial || '',
                  to: current || discoveredInitial || '',
                  allow: false,
                  guardResult: 'not_applicable',
                  reasons: [{ code: 'WORKFLOW_EXECUTION_FAILED', summary: message }],
                  errors: [{ code: 'WORKFLOW_EXECUTION_FAILED', message }],
                  actionsExecuted: [],
                  errorCode: 'WORKFLOW_EXECUTION_FAILED',
                },
                availableTransitions: [],
              };
            }
          } finally {
            safeDeleteGlobal(py, 'WF_DSL');
            safeDeleteGlobal(py, 'WF_EVENT');
            safeDeleteGlobal(py, 'WF_CONTEXT');
            safeDeleteGlobal(py, 'WF_CURRENT');
            safeDeleteGlobal(py, 'WF_INITIAL');
            safeDeleteGlobal(py, 'WF_ACTOR_ID');
            safeDeleteGlobal(py, 'WF_ACTOR_ROLES');
            safeDeleteGlobal(py, 'WF_WORKFLOW_ID');
          }
        })();

        discoveredInitial = stepResult.initialState || discoveredInitial;
        current = stepResult.currentState;
        lastTransitions = stepResult.availableTransitions || [];
        const rawCode = String((stepResult.step as { errorCode?: string }).errorCode || '');
        const normalizedCode = rawCode ? toWorkflowErrorCode(rawCode) : undefined;
        steps.push({
          ...(stepResult.step as Record<string, unknown>),
          errorCode: normalizedCode,
          remediationHint: normalizedCode ? remediationHintFor(normalizedCode) : undefined,
          timestamp: new Date().toISOString(),
        });
        if (normalizedCode) {
          break;
        }
      }

      self.postMessage({
        id,
        type: 'RESULT',
        payload: {
          initialState: discoveredInitial,
          currentState: current ?? discoveredInitial,
          steps,
          availableTransitions: lastTransitions,
        },
      });
    } else if (type === 'GENERATE_UISCHEMA') {
      const { dsl } = payload;
      py.globals.set('DSL', dsl);
      
      try {
        const result = await py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.tooling.uischema.generator import generate_ui_schema
from mpc.kernel.meta.models import DomainMeta, KindDef

ast = parse(DSL)
# build meta from kinds present in AST for simplicity
kind_names = list(set(d.kind for d in ast.defs))
meta = DomainMeta(kinds=[KindDef(name=n) for n in kind_names])
res = generate_ui_schema(ast, meta)

json.dumps({
    "schemas": res.schemas,
    "warnings": res.warnings
})
`);
        self.postMessage({ id, type: 'UISCHEMA_RESULT', payload: JSON.parse(result) });
      } finally {
        safeDeleteGlobal(py, 'DSL');
      }
    } else if (type === 'GENERATE_FORM_PACKAGE') {
      const {
        dsl,
        formId,
        data,
        actorRoles,
        actorAttrs,
      } = payload as {
        dsl: string;
        formId: string;
        data?: Record<string, unknown>;
        actorRoles?: string[];
        actorAttrs?: Record<string, unknown>;
      };

      const formLimits = getFormLimits();
      const dslBytes = estimateBytes(dsl ?? '');
      const dataBytes = estimateBytes(data ?? {});
      const actorBytes = estimateBytes({ actorRoles: actorRoles ?? [], actorAttrs: actorAttrs ?? {} });
      const limitDiagnostics: EnvelopeDiagnostic[] = [];
      if (dslBytes > formLimits.maxDslBytes) {
        limitDiagnostics.push({
          code: 'E_FORM_DSL_TOO_LARGE',
          message: `DSL payload exceeds maxDslBytes (${dslBytes} > ${formLimits.maxDslBytes}).`,
          severity: 'error',
        });
      }
      if (dataBytes > formLimits.maxDataBytes) {
        limitDiagnostics.push({
          code: 'E_FORM_DATA_TOO_LARGE',
          message: `Form data exceeds maxDataBytes (${dataBytes} > ${formLimits.maxDataBytes}).`,
          severity: 'error',
        });
      }
      if (actorBytes > formLimits.maxActorBytes) {
        limitDiagnostics.push({
          code: 'E_FORM_ACTOR_TOO_LARGE',
          message: `Actor context exceeds maxActorBytes (${actorBytes} > ${formLimits.maxActorBytes}).`,
          severity: 'error',
        });
      }
      if (limitDiagnostics.length > 0) {
        postEnvelope(
          id,
          'FORM_PACKAGE',
          requestId,
          {
            jsonSchema: {},
            uiSchema: {},
            fieldState: [],
            validation: {
              valid: false,
              errors: [
                {
                  field_id: '__limits__',
                  message: 'Input limits exceeded. Reduce DSL/data payload size and retry.',
                  expr: null,
                },
              ],
            },
          },
          startedAt,
          limitDiagnostics,
        );
        return;
      }

      py.globals.set('_form_dsl_input', dsl);
      py.globals.set('_form_id', formId);
      py.globals.set('_form_data', JSON.stringify(data ?? {}));
      py.globals.set('_actor_roles', JSON.stringify(actorRoles ?? []));
      py.globals.set('_actor_attrs', JSON.stringify(actorAttrs ?? {}));
      py.globals.set('_form_fail_open', readEnvBool('VITE_MPC_FORM_FAIL_OPEN', true));

      const emptyFormPackage = {
        jsonSchema: {} as Record<string, unknown>,
        uiSchema: {} as Record<string, unknown>,
        fieldState: [] as unknown[],
        validation: {
          valid: false,
          errors: [
            {
              field_id: '__form__',
              message: 'Form package generation failed.',
              expr: null as string | null,
            },
          ],
        },
      };

      try {
        const timeoutMs = readEnvNumber('VITE_MPC_FORM_PACKAGE_TIMEOUT_MS', 30_000);
        const raw = await Promise.race([
          py.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.form.engine import FormEngine
from mpc.features.form.kinds import FORM_KINDS
from mpc.kernel.meta.models import DomainMeta

ast = parse(_form_dsl_input)
meta = DomainMeta(kinds=FORM_KINDS)
engine = FormEngine(ast=ast, meta=meta)
package = engine.get_form_package(
    _form_id,
    json.loads(_form_data),
    actor_roles=json.loads(_actor_roles),
    actor_attrs=json.loads(_actor_attrs),
    fail_open=_form_fail_open,
)

json.dumps({
  "jsonSchema": package.jsonSchema,
  "uiSchema": package.uiSchema,
  "fieldState": package.fieldState,
  "validation": package.validation,
})
          `),
          new Promise<string>((_, reject) => {
            setTimeout(() => reject(new Error('E_FORM_TIMEOUT')), timeoutMs);
          }),
        ]);
        postEnvelope(id, 'FORM_PACKAGE', requestId, JSON.parse(raw as string), startedAt);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg === 'E_FORM_TIMEOUT') {
          postEnvelope(id, 'FORM_PACKAGE', requestId, emptyFormPackage, startedAt, [
            {
              code: 'E_FORM_TIMEOUT',
              message: `Form package generation exceeded timeout (${readEnvNumber('VITE_MPC_FORM_PACKAGE_TIMEOUT_MS', 30_000)} ms).`,
              severity: 'error',
            },
          ]);
        } else {
          const detail = msg.length > 2000 ? `${msg.slice(0, 2000)}…` : msg;
          postEnvelope(
            id,
            'FORM_PACKAGE',
            requestId,
            {
              ...emptyFormPackage,
              validation: {
                valid: false,
                errors: [{ field_id: '__form__', message: detail, expr: null }],
              },
            },
            startedAt,
            [{ code: 'E_FORM_EXPR_FAILED', message: detail, severity: 'error' }],
          );
        }
      } finally {
        safeDeleteGlobal(py, '_form_dsl_input');
        safeDeleteGlobal(py, '_form_id');
        safeDeleteGlobal(py, '_form_data');
        safeDeleteGlobal(py, '_actor_roles');
        safeDeleteGlobal(py, '_actor_attrs');
        safeDeleteGlobal(py, '_form_fail_open');
      }
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    self.postMessage({ id, type: 'ERROR', payload: message });
  } finally {
    releaseLock();
  }
};
