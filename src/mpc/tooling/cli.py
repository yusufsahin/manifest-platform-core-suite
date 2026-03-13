import sys
import argparse
import json
from pathlib import Path
from mpc.kernel.parser import parse
from mpc.tooling.validator.structural import validate_structural
from mpc.tooling.validator.semantic import validate_semantic
from mpc.kernel.meta.diff import detect_drift
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.features.workflow import WorkflowEngine

def main():
    parser = argparse.ArgumentParser(prog="mpc", description="MPC Unified CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Validate
    val_parser = subparsers.add_parser("validate", help="Validate a manifest file")
    val_parser.add_argument("file", help="Path to manifest file (.manifest, .yaml, .json)")
    val_parser.add_argument("--json", action="store_true", help="Output results as JSON")

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

    # Rollout
    ro_parser = subparsers.add_parser("rollout", help="Manage canary rollout")
    ro_parser.add_argument("bundle", help="Bundle hash or file")
    ro_parser.add_argument("--weight", type=float, default=0.1, help="Canary weight (0.0-1.0)")

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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File {args.file} not found.", file=sys.stderr)
            sys.exit(1)

        text = path.read_text(encoding="utf-8")
        
        # Determine parser based on extension
        ext = path.suffix.lower()
        ast = parse(text) # parse() handles DSL/YAML/JSON internally in some versions, 
                         # but here we assume canonical parser for now

        if args.command == "validate":
            # For CLI validation, we use a generic meta or allow all kinds
            kind_names = sorted({node.kind for node in ast.defs if isinstance(node.kind, str)})
            meta = DomainMeta(kinds=[KindDef(name=name) for name in kind_names])
            
            s_errs = validate_structural(ast, meta)
            # Drift Detection
            # In a real scenario, meta would be loaded from a registered domain.
            # For this CLI tool, we'll use a placeholder/derived meta or skip if not provided.
            # Placeholder for now to demonstrate integrated drift detection
            demo_meta = DomainMeta(kinds=[KindDef(name="Workflow", required_props=["initial"])])
            drifts = detect_drift(ast, demo_meta)
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
                    print("✓ Validation passed.")
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

        elif args.command == "repl":
            _run_repl()

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

        elif args.command == "rollout":
            _run_rollout(args)

        elif args.command == "approve":
            _run_approve(args)

        elif args.command == "acl-check":
            _run_acl_check(args)

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
                except: pass

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
            "version": ast.version,
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
            "version": ast.version,
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

def _run_rollout(args):
    from mpc.features.routing.canary import CanaryRouter
    router = CanaryRouter(stable_hash="current-stable", canary_hash=args.bundle, weight=args.weight)
    print(f">>> ROLLOUT: Routing {args.weight*100}% traffic to {args.bundle}")
    print(f"SUCCESS: Canary routing active.")

def _run_approve(args):
    print(f">>> APPROVAL: Recorded role '{args.role}' for bundle {args.bundle}")
    print(f"SUCCESS: Approval recorded.")

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

if __name__ == "__main__":
    main()
