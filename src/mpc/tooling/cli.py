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

if __name__ == "__main__":
    main()
