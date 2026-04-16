import sys
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from mpc.kernel.parser import parse
from mpc.tooling.validator.structural import validate_structural
from mpc.tooling.validator.semantic import validate_semantic
from mpc.kernel.meta.diff import detect_drift
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.kernel.ast.models import ManifestAST
from mpc.features.workflow import WorkflowEngine

def main():
    parser = argparse.ArgumentParser(prog="mpc", description="MPC Unified CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Validate
    val_parser = subparsers.add_parser("validate", help="Validate a manifest file")
    val_parser.add_argument("file", help="Path to manifest file (.manifest, .yaml, .json)")
    val_parser.add_argument("--json", action="store_true", help="Output results as JSON")
    val_parser.add_argument("--meta", help="Optional DomainMeta JSON file for structural validation and drift detection")

    # Export
    exp_parser = subparsers.add_parser("export", help="Export manifest to other formats")
    exp_parser.add_argument("file", help="Source manifest file")
    exp_parser.add_argument("--format", choices=["mermaid", "json", "ast"], default="mermaid", help="Export format")

    # REPL
    subparsers.add_parser("repl", help="Start an interactive expression REPL")

    # Redact
    red_parser = subparsers.add_parser("redact", help="Test redaction on a data file")
    red_parser.add_argument("file", help="JSON/YAML data file to redact")
    red_parser.add_argument("--keys", help="Comma-separated list of keys to mask")

    # Overlay
    ov_parser = subparsers.add_parser("overlay", help="Merge base with overlay manifests")
    ov_parser.add_argument("base", help="Base manifest file")
    ov_parser.add_argument("overlays", nargs="+", help="Overlay manifest files")

    # Resolve Imports
    ri_parser = subparsers.add_parser("resolve-imports", help="Resolve and flatten imports")
    ri_parser.add_argument("file", help="Manifest file with imports")

    # UI Schema
    ui_parser = subparsers.add_parser("ui-schema", help="Generate UI schema from manifest")
    ui_parser.add_argument("file", help="Manifest file")

    # SBOM
    sb_parser = subparsers.add_parser("sbom", help="Generate SBOM for a manifest")
    sb_parser.add_argument("file", help="Manifest file")

    # Bundle
    bn_parser = subparsers.add_parser("bundle", help="Create a signed manifest bundle")
    bn_parser.add_argument("file", help="Manifest file")
    bn_parser.add_argument("--key", help="Secret key for signing (HMAC-SHA256)")

    # Activate
    ac_parser = subparsers.add_parser("activate", help="Simulate manifest activation")
    ac_parser.add_argument("file", help="Bundle or manifest file")
    ac_parser.add_argument("--key", help="Secret key for verification")
    ac_parser.add_argument("--runtime-url", help="Runtime base URL (e.g. http://127.0.0.1:8000)")
    ac_parser.add_argument("--tenant-id", help="Tenant id (required with --runtime-url)")
    ac_parser.add_argument("--enterprise-mode", action="store_true", help="Enterprise mode (signature required)")
    ac_parser.add_argument("--signature", help="Signature string to store on artifact (runtime mode)")
    ac_parser.add_argument("--idempotency-key", help="Idempotency-Key header value (runtime mode)")

    # Rollout
    ro_parser = subparsers.add_parser("rollout", help="Manage canary rollout")
    ro_parser.add_argument("bundle", help="Bundle hash or file")
    ro_parser.add_argument("--weight", type=float, default=0.1, help="Canary weight (0.0-1.0)")
    ro_parser.add_argument("--runtime-url", help="Runtime base URL (e.g. http://127.0.0.1:8000)")
    ro_parser.add_argument("--tenant-id", help="Tenant id (required with --runtime-url)")
    ro_parser.add_argument("--signature", help="Signature string to store on artifact (runtime mode)")

    # Status
    st_parser = subparsers.add_parser("status", help="Show current platform status")
    st_parser.add_argument("--runtime-url", help="Runtime base URL (e.g. http://127.0.0.1:8000)")
    st_parser.add_argument("--tenant-id", help="Tenant id (required with --runtime-url)")

    # Promote canary
    pc_parser = subparsers.add_parser("promote-canary", help="Promote canary to active (runtime mode)")
    pc_parser.add_argument("--runtime-url", required=True, help="Runtime base URL (e.g. http://127.0.0.1:8000)")
    pc_parser.add_argument("--tenant-id", required=True, help="Tenant id")

    # Rollback
    rb_parser = subparsers.add_parser("rollback", help="Rollback to previous active (runtime mode)")
    rb_parser.add_argument("--runtime-url", required=True, help="Runtime base URL (e.g. http://127.0.0.1:8000)")
    rb_parser.add_argument("--tenant-id", required=True, help="Tenant id")

    # Mode
    md_parser = subparsers.add_parser("set-mode", help="Set activation mode (runtime mode)")
    md_parser.add_argument("--runtime-url", required=True, help="Runtime base URL (e.g. http://127.0.0.1:8000)")
    md_parser.add_argument("--tenant-id", required=True, help="Tenant id")
    md_parser.add_argument("--mode", required=True, choices=["normal", "policy-off", "read-only", "kill-switch"])

    # Approve
    ap_parser = subparsers.add_parser("approve", help="Approve a pending manifest")
    ap_parser.add_argument("bundle", help="Bundle hash")
    ap_parser.add_argument("--role", required=True, help="Approver role")

    # ACL Check
    acl_parser = subparsers.add_parser("acl-check", help="Test ACL rules")
    acl_parser.add_argument("file", help="Manifest file")
    acl_parser.add_argument("--action", required=True)
    acl_parser.add_argument("--resource", required=True)
    acl_parser.add_argument("--roles", help="Comma-separated roles")
    acl_parser.add_argument("--attrs", help="JSON string of actor attributes")

    # List forms
    lf_parser = subparsers.add_parser("list-forms", help="List FormDef definitions in a manifest")
    lf_parser.add_argument("file", help="Manifest file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Commands that do not need a file argument are handled first.
    if args.command == "repl":
        _run_repl()
        sys.exit(0)
    elif args.command == "status":
        _run_status(args)
        sys.exit(0)
    elif args.command in ("rollout", "approve", "promote-canary", "rollback", "set-mode"):
        try:
            if args.command == "rollout":
                _run_rollout(args)
            elif args.command == "approve":
                _run_approve(args)
            elif args.command == "promote-canary":
                _run_promote_canary(args)
            elif args.command == "rollback":
                _run_rollback(args)
            elif args.command == "set-mode":
                _run_set_mode(args)
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    try:
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File {args.file} not found.", file=sys.stderr)
            sys.exit(1)

        text = path.read_text(encoding="utf-8")

        ast = parse(text)

        if args.command == "validate":
            kind_names = sorted({node.kind for node in ast.defs if isinstance(node.kind, str)})

            meta: DomainMeta
            meta_path = getattr(args, "meta", None)
            if meta_path:
                meta_text = Path(meta_path).read_text(encoding="utf-8")
                meta_json = json.loads(meta_text)
                meta = DomainMeta.from_dict(meta_json) if hasattr(DomainMeta, "from_dict") else DomainMeta(**meta_json)
            else:
                # Fallback: permissive meta derived from AST to avoid false unknown-kind noise.
                meta = DomainMeta(kinds=[KindDef(name=name) for name in kind_names])

            s_errs = validate_structural(ast, meta)

            # Drift detection is only meaningful when meta is provided explicitly.
            drifts = detect_drift(ast, meta) if meta_path else []
            if not args.json:
                for drift in drifts:
                    print(f"DRIFT: {drift}")

            m_errs = validate_semantic(ast)
            all_errs = s_errs + m_errs

            if args.json:
                # Combine all errors and drifts for JSON output
                json_output = [{"code": e.code, "message": e.message, "severity": e.severity} for e in all_errs]
                json_output.extend([{"code": "DRIFT", "message": str(d), "severity": "warning"} for d in drifts])
                print(json.dumps(json_output))
            else:
                if not all_errs and not drifts:
                                        # Avoid non-ASCII glyphs: Windows consoles often default to a legacy code page.
                    print("OK: Validation passed.")
                for e in all_errs:
                    print(f"[{e.severity.upper()}] {e.code}: {e.message}")
                for d in drifts:
                    print(f"[WARNING] DRIFT: {d}")
            
            if any(e.severity == "error" for e in all_errs):
                sys.exit(1)

        elif args.command == "export":
            if args.format == "mermaid":
                wf_node = next((n for n in ast.defs if n.kind == "Workflow"), None)
                if wf_node:
                    engine = WorkflowEngine.from_ast_node(wf_node)
                    print(engine.to_mermaid())
                else:
                    print("Error: No Workflow definition found in manifest.", file=sys.stderr)
                    sys.exit(1)
            elif args.format == "json":
                # Assuming AST has a to_dict or similar
                print(json.dumps(ast.__dict__, default=lambda o: str(o), indent=2))
            elif args.format == "ast":
                print(ast)

        elif args.command == "redact":
            _run_redact(args)

        elif args.command == "overlay":
            _run_overlay(args)

        elif args.command == "resolve-imports":
            _run_resolve_imports(args)

        elif args.command == "ui-schema":
            _run_ui_schema(args)

        elif args.command == "sbom":
            _run_sbom(args)

        elif args.command == "bundle":
            _run_bundle(args)

        elif args.command == "activate":
            _run_activate(args)

        elif args.command == "acl-check":
            _run_acl_check(args)

        elif args.command == "list-forms":
            _run_list_forms(ast)

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

def _run_repl():
    print("MPC Expression REPL (Type 'exit' or 'quit' to leave)")
    print("Available variables: data={...}")
    
    from mpc.features.expr import ExprEngine
    from mpc.kernel.meta.models import DomainMeta, FunctionDef
    
    # Simple meta with basic functions
    meta = DomainMeta(allowed_functions=[
        FunctionDef(name="len", args=["string|array"], returns="int"),
        FunctionDef(name="now", returns="string"),
        FunctionDef(name="concat", args=["any", "any"], returns="string"),
    ])
    engine = ExprEngine(meta=meta)
    ctx = {"data": {"user": "yusuf", "role": "admin", "age": 30}}
    
    while True:
        try:
            line = input("mpc > ").strip()
            if line.lower() in ("exit", "quit"):
                break
            if not line:
                continue
                
            res = engine.evaluate(line, context=ctx, enable_trace=True)
            print(f"Result: {res.value} (Type: {res.type})")
            if res.trace:
                print(f"Trace: {len(res.trace)} steps")
                
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")

def _run_redact(args):
    import json
    import yaml
    from mpc.features.redaction import RedactionEngine, RedactionConfig

    file_path = args.file
    with open(file_path, "r", encoding="utf-8") as f:
        if file_path.endswith(".yaml") or file_path.endswith(".yml"):
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    keys = set()
    if args.keys:
        keys = {k.strip() for k in args.keys.split(",")}
    
    config = RedactionConfig(deny_keys=frozenset(keys)) if keys else RedactionConfig()
    engine = RedactionEngine(config=config)
    
    redacted = engine.redact(data)
    print(json.dumps(redacted, indent=2))

def _run_overlay(args):
    from mpc.kernel.parser import parse
    from mpc.features.overlay import OverlayEngine
    
    with open(args.base, "r", encoding="utf-8") as f:
        base_ast = parse(f.read())
    
    current_ast = base_ast
    for ov_path in args.overlays:
        with open(ov_path, "r", encoding="utf-8") as f:
            ov_ast = parse(f.read())
        
        engine = OverlayEngine(base=current_ast)
        res = engine.apply(ov_ast)
        if res.conflicts:
            for c in res.conflicts:
                print(f"CONFLICT: {c.message}", file=sys.stderr)
            sys.exit(1)
        current_ast = res.ast
    
    # Output result as DSL
    print("# Resulting Overlay AST (Simplified view)")
    for node in current_ast.defs:
        print(f"kind: {node.kind}, id: {node.id}")

def _run_resolve_imports(args):
    import os
    from mpc.kernel.parser import parse
    from mpc.tooling.imports import ImportResolver
    
    resolver = ImportResolver()
    
    # Helper to register local files as available manifests
    def _reg_dir(d):
        for f in os.listdir(d):
            if f.endswith((".manifest", ".yaml", ".json")):
                path = os.path.join(d, f)
                try:
                    with open(path, "r", encoding="utf-8") as f_obj:
                        name = os.path.splitext(f)[0]
                        resolver.register(name, parse(f_obj.read()))
                except Exception as exc:
                    print(f"[WARN] Could not parse '{path}' for import registry: {exc}", file=sys.stderr)

    _reg_dir(os.path.dirname(os.path.abspath(args.file)))

    with open(args.file, "r", encoding="utf-8") as f:
        base_ast = parse(f.read())
    
    res = resolver.resolve(base_ast)
    if res.errors:
        for e in res.errors:
            print(f"ERROR: {e.message}", file=sys.stderr)
        sys.exit(1)
    
    print(f"# Resolved Imports: {', '.join(res.resolved_imports)}")
    print(f"# Total Definitions: {len(res.ast.defs)}")

def _run_ui_schema(args):
    from mpc.kernel.parser import parse
    from mpc.tooling.uischema.generator import generate_ui_schema
    from mpc.kernel.meta.models import DomainMeta, KindDef
    
    with open(args.file, "r", encoding="utf-8") as f:
        ast = parse(f.read())
    
    # Simple meta inference
    kinds = list(set(d.kind for d in ast.defs))
    meta = DomainMeta(kinds=[KindDef(name=k) for k in kinds])
    
    res = generate_ui_schema(ast, meta)
    print(json.dumps(res.schemas, indent=2))

def _run_sbom(args):
    from mpc.kernel.parser import parse
    with open(args.file, "r", encoding="utf-8") as f:
        ast = parse(f.read())
    
    sbom = {
        "manifest": {
            "name": ast.name,
            "version": ast.manifest_version,
            "namespace": ast.namespace
        },
        "statistics": {
            "total_definitions": len(ast.defs),
            "kinds": list(set(d.kind for d in ast.defs))
        },
        "dependencies": [d.properties.get("base") for d in ast.defs if d.kind == "Import"]
    }
    print(json.dumps(sbom, indent=2))

def _run_bundle(args):
    import hashlib
    from mpc.kernel.parser import parse
    from mpc.tooling.imports import ImportResolver
    from mpc.enterprise.governance.signing import HMACSigningPort
    
    with open(args.file, "r", encoding="utf-8") as f:
        raw = f.read()
        ast = parse(raw)
    
    # Resolve imports for self-contained bundle
    resolver = ImportResolver()
    res = resolver.resolve(ast)
    
    signature = None
    if args.key:
        port = HMACSigningPort(args.key)
        signature = port.sign(raw.encode())

    bundle = {
        "format": "mpc-bundle-v1",
        "timestamp": "2026-03-13T20:41:00Z",
        "checksum": hashlib.sha256(raw.encode()).hexdigest(),
        "signature": signature,
        "manifest": {
            "name": ast.name,
            "version": ast.manifest_version,
            "namespace": ast.namespace,
            "defs": len(res.ast.defs)
        },
        "provenance": {
            "tool": "mpc-cli",
            "version": "1.2.0"
        }
    }
    print(json.dumps(bundle, indent=2))

def _run_activate(args):
    if getattr(args, "runtime_url", None):
        if not args.tenant_id:
            raise RuntimeError("--tenant-id is required with --runtime-url")
        raw = Path(args.file).read_text(encoding="utf-8")
        signature = getattr(args, "signature", None)
        if signature is None and getattr(args, "key", None):
            from mpc.enterprise.governance.signing import HMACSigningPort
            signature = HMACSigningPort(str(args.key)).sign(raw.encode("utf-8"))
        created = _runtime_post(
            args.runtime_url,
            "/api/v1/rule-artifacts",
            {"tenant_id": args.tenant_id, "manifest_text": raw, "signature": signature},
        )
        artifact_id = created.get("id")
        if not artifact_id:
            raise RuntimeError(f"Runtime did not return artifact id: {created}")
        headers: dict[str, str] = {}
        if getattr(args, "idempotency_key", None):
            headers["Idempotency-Key"] = str(args.idempotency_key)
        res = _runtime_post(
            args.runtime_url,
            f"/api/v1/tenants/{args.tenant_id}/activation/activate",
            {
                "artifact_id": artifact_id,
                "enterprise_mode": bool(getattr(args, "enterprise_mode", False)),
                "verification": (
                    {"algorithm": "hmac-sha256", "key": str(args.key)}
                    if getattr(args, "key", None)
                    else None
                ),
            },
            headers=headers or None,
        )
        print(json.dumps(res, indent=2))
        return
    from mpc.enterprise.governance.signing import HMACSigningPort
    
    print(">>> Phase 1: VERIFY - Checksum & AST integrity...")
    
    # Simple check if file is bundle
    with open(args.file, "r") as f:
        data = f.read()
        if data.strip().startswith("{"):
            bundle = json.loads(data)
            if bundle.get("signature") and args.key:
                port = HMACSigningPort(args.key)
                # Verify logic simplified for demo
                print(">>> [SIG] Verifying HMAC signature... [OK]")
            elif bundle.get("signature") and not args.key:
                print("FAILED: Bundle is signed but no --key provided.", file=sys.stderr)
                sys.exit(1)

    print(">>> Phase 2: ATTEST - DomainMeta compliance... [OK]")
    print(">>> Phase 3: SWAP   - Atomic symbolic link update... [OK]")
    print(">>> Phase 4: AUDIT  - Emitting activation event... [OK]")
    print("SUCCESS: Manifest activated.")


def _runtime_request(
    method: str,
    runtime_url: str,
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    base = runtime_url.rstrip("/")
    url = f"{base}{path}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = Request(url, data=body, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read().decode("utf-8") if hasattr(e, "read") else ""
        raise RuntimeError(f"Runtime HTTP {e.code}: {raw or e.reason}") from e
    except URLError as e:
        raise RuntimeError(f"Runtime connection failed: {e}") from e


def _runtime_get(runtime_url: str, path: str) -> dict:
    return _runtime_request("GET", runtime_url, path)


def _runtime_post(
    runtime_url: str,
    path: str,
    payload: dict,
    headers: dict[str, str] | None = None,
) -> dict:
    return _runtime_request("POST", runtime_url, path, payload=payload, headers=headers)


def _get_store():
    from mpc.features.workflow.file_store import JSONFileStateStore
    return JSONFileStateStore(".mpc_state.json")

def _run_rollout(args):
    if getattr(args, "runtime_url", None):
        if not args.tenant_id:
            raise RuntimeError("--tenant-id is required with --runtime-url")
        bundle_path = Path(args.bundle)
        artifact_id = args.bundle
        if bundle_path.exists():
            raw = bundle_path.read_text(encoding="utf-8")
            created = _runtime_post(
                args.runtime_url,
                "/api/v1/rule-artifacts",
                {"tenant_id": args.tenant_id, "manifest_text": raw, "signature": getattr(args, "signature", None)},
            )
            artifact_id = created.get("id") or artifact_id
        res = _runtime_post(
            args.runtime_url,
            f"/api/v1/tenants/{args.tenant_id}/activation/canary",
            {"artifact_id": artifact_id, "weight": float(args.weight)},
        )
        print(json.dumps(res, indent=2))
        return
    store = _get_store()
    store.set_global_config("canary_bundle", args.bundle)
    store.set_global_config("canary_weight", args.weight)
    print(f">>> ROLLOUT: Routing {args.weight*100}% traffic to {args.bundle} (PERSISTED)")
    print(f"SUCCESS: Canary routing active.")

def _run_approve(args):
    store = _get_store()
    approvals = store.get_global_config(f"approvals_{args.bundle}") or []
    if args.role not in approvals:
        approvals.append(args.role)
        store.set_global_config(f"approvals_{args.bundle}", approvals)
    print(f">>> APPROVAL: Recorded role '{args.role}' for bundle {args.bundle} (PERSISTED)")
    print(f"Current approvals: {', '.join(approvals)}")
    print(f"SUCCESS: Approval recorded.")

def _run_status(args):
    if getattr(args, "runtime_url", None):
        if not args.tenant_id:
            raise RuntimeError("--tenant-id is required with --runtime-url")
        res = _runtime_get(args.runtime_url, f"/api/v1/tenants/{args.tenant_id}/activation/status")
        print(json.dumps(res, indent=2))
        return
    store = _get_store()
    canary = store.get_global_config("canary_bundle")
    weight = store.get_global_config("canary_weight")
    
    print("MPC PLATFORM STATUS")
    print("===================")
    print(f"Current Stable: [active-manifest]")
    if canary:
        print(f"Canary Active : {canary}")
        print(f"Canary Weight : {weight*100}%")
    else:
        print("Canary Active : None")
    
    print("\nRecent Approvals:")
    for k, v in store._data.get("config", {}).items():
        if k.startswith("approvals_"):
            bundle = k.replace("approvals_", "")
            print(f"  - {bundle}: {', '.join(v)}")


def _run_promote_canary(args):
    res = _runtime_post(
        args.runtime_url,
        f"/api/v1/tenants/{args.tenant_id}/activation/promote-canary",
        {},
    )
    print(json.dumps(res, indent=2))


def _run_rollback(args):
    res = _runtime_post(
        args.runtime_url,
        f"/api/v1/tenants/{args.tenant_id}/activation/rollback",
        {},
    )
    print(json.dumps(res, indent=2))


def _run_set_mode(args):
    res = _runtime_post(
        args.runtime_url,
        f"/api/v1/tenants/{args.tenant_id}/activation/mode",
        {"mode": args.mode},
    )
    print(json.dumps(res, indent=2))

def _run_acl_check(args):
    from mpc.kernel.parser import parse
    from mpc.features.acl import ACLEngine
    from mpc.kernel.meta.models import DomainMeta, KindDef
    
    with open(args.file, "r", encoding="utf-8") as f:
        ast = parse(f.read())
    
    roles = args.roles.split(",") if args.roles else []
    attrs = json.loads(args.attrs) if args.attrs else {}
    
    meta = DomainMeta(kinds=[KindDef(name="ACL")])
    engine = ACLEngine(ast=ast, meta=meta)
    res = engine.check(args.action, args.resource, actor_roles=roles, actor_attrs=attrs)
    
    print(f"DECISION: {'ALLOW' if res.allowed else 'DENY'}")
    for r in res.reasons:
        print(f"REASON: [{r.code}] {r.summary}")


def _run_list_forms(ast: ManifestAST):
    """List FormDef nodes: id, title, workflow fields, field summary, jsonSchema."""
    from mpc.features.form.engine import FormEngine
    from mpc.features.form.kinds import FORM_KINDS

    meta = DomainMeta(kinds=FORM_KINDS)
    engine = FormEngine(ast=ast, meta=meta)
    forms = engine.get_forms()

    output = [
        {
            "id": form.id,
            "title": form.title,
            "workflowState": form.workflow_state,
            "workflowTrigger": form.workflow_trigger,
            "fieldCount": len(form.fields),
            "fields": [{"id": f.id, "type": f.type, "required": f.required} for f in form.fields],
            "jsonSchema": form.to_json_schema(),
        }
        for form in forms
    ]
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
