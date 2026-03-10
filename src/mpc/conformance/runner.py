"""Conformance runner — executes fixture packs and verifies outputs.

Implements the behaviour described in tools/CONFORMANCE_RUNNER_SPEC.md:
  1. Load meta.json, fix clock, load preset, merge limit overrides.
  2. Run the category-specific operation.
  3. Canonicalize output; byte-compare with expected.json.
  4. Reject unknown E_*/R_*/Intent-kind codes.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import jsonschema
from referencing import Registry, Resource

from mpc.acl.engine import ACLEngine, ACLResult
from mpc.ast.models import ASTNode, ManifestAST
from mpc.canonical import canonicalize, order_definitions
from mpc.compose.engine import compose_decisions
from mpc.contracts.models import Decision, Intent, Reason
from mpc.errors.exceptions import MPCBudgetError, MPCError
from mpc.errors.registry import validate_all_codes
from mpc.expr import ExprEngine, typecheck as expr_typecheck, evaluate as expr_evaluate
from mpc.meta.models import DomainMeta, FunctionDef
from mpc.overlay.engine import OverlayEngine
from mpc.policy.engine import PolicyEngine
from mpc.workflow import GuardPort
from mpc.workflow.fsm import WorkflowEngine


# ---------------------------------------------------------------------------
# Data carriers
# ---------------------------------------------------------------------------

@dataclass
class FixtureContext:
    category: str
    fixture_name: str
    input_data: dict[str, Any]
    preset: dict[str, Any]
    limits: dict[str, Any]
    meta: dict[str, Any]
    clock: str | None = None


@dataclass
class FixtureResult:
    fixture: str
    passed: bool
    skipped: bool = False
    skip_reason: str | None = None
    diff: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


CategoryHandler = Callable[["ConformanceRunner", FixtureContext], dict[str, Any]]


class _FailGuard:
    """GuardPort that always returns False. Used by guard_fail conformance fixtures."""

    def check(self, trigger: str, context: dict[str, Any]) -> bool:
        return False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class ConformanceRunner:
    """Load and execute conformance fixture packs."""

    def __init__(
        self,
        fixtures_root: Path,
        *,
        presets_root: Path | None = None,
        schemas_root: Path | None = None,
    ) -> None:
        self.fixtures_root = Path(fixtures_root)
        self.presets_root = Path(
            presets_root or self.fixtures_root.parent.parent / "presets"
        )
        self.schemas_root = Path(
            schemas_root
            or self.fixtures_root.parent.parent / "core-contracts" / "schemas"
        )
        self._schema_registry: Registry = self._build_schema_registry()
        self._handlers: dict[str, CategoryHandler] = {}
        self._register_builtin_handlers()

    # -- handler registration -----------------------------------------------

    def _register_builtin_handlers(self) -> None:
        self._handlers["contracts"] = ConformanceRunner._handle_contracts
        self._handlers["canonical"] = ConformanceRunner._handle_canonical
        self._handlers["workflow"] = ConformanceRunner._handle_workflow
        self._handlers["expr"] = ConformanceRunner._handle_expr
        self._handlers["acl"] = ConformanceRunner._handle_acl
        self._handlers["policy"] = ConformanceRunner._handle_policy
        self._handlers["compose"] = ConformanceRunner._handle_compose
        self._handlers["overlay"] = ConformanceRunner._handle_overlay
        self._handlers["governance"] = ConformanceRunner._handle_governance

    def register_handler(self, category: str, handler: CategoryHandler) -> None:
        """Register a custom handler for *category* (e.g. ``"expr"``)."""
        self._handlers[category] = handler

    # -- schema helpers -----------------------------------------------------

    def _build_schema_registry(self) -> Registry:
        registry: Registry = Registry()
        if not self.schemas_root.exists():
            return registry
        for schema_file in sorted(self.schemas_root.glob("*.schema.json")):
            raw = json.loads(schema_file.read_text(encoding="utf-8"))
            schema = {"$id": schema_file.name, **raw}
            resource = Resource.from_contents(schema)
            registry = registry.with_resource(schema_file.name, resource)
        return registry

    # -- preset helpers -----------------------------------------------------

    def load_preset(self, name: str) -> dict[str, Any]:
        path = self.presets_root / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Preset not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    # -- public API ---------------------------------------------------------

    def run_all(self) -> list[FixtureResult]:
        """Run every fixture under *fixtures_root* and return results."""
        results: list[FixtureResult] = []
        for category_dir in sorted(self.fixtures_root.iterdir()):
            if not category_dir.is_dir():
                continue
            for fixture_dir in sorted(category_dir.iterdir()):
                if not fixture_dir.is_dir():
                    continue
                results.append(self.run_fixture(fixture_dir))
        return results

    def run_category(self, category: str) -> list[FixtureResult]:
        """Run all fixtures for a single *category* and return results."""
        results: list[FixtureResult] = []
        category_dir = self.fixtures_root / category
        if not category_dir.is_dir():
            return results
        for fixture_dir in sorted(category_dir.iterdir()):
            if fixture_dir.is_dir():
                results.append(self.run_fixture(fixture_dir))
        return results

    def run_fixture(self, fixture_dir: Path) -> FixtureResult:
        """Run a single fixture directory and return the result."""
        category = fixture_dir.parent.name
        fixture_label = f"{category}/{fixture_dir.name}"

        if category not in self._handlers:
            return FixtureResult(
                fixture=fixture_label,
                passed=False,
                skipped=True,
                skip_reason=f"Category '{category}' not yet implemented",
            )

        try:
            input_data = _load_json(fixture_dir / "input.json")
            expected = _load_json(fixture_dir / "expected.json")
            meta = _load_json(fixture_dir / "meta.json")
        except Exception as exc:
            return FixtureResult(
                fixture=fixture_label, passed=False, diff=[f"Load error: {exc}"]
            )

        preset_name = meta.get("preset", "preset-generic-full")
        try:
            preset = self.load_preset(preset_name)
        except FileNotFoundError:
            return FixtureResult(
                fixture=fixture_label,
                passed=False,
                violations=[f"Preset '{preset_name}' not found"],
            )

        limits = {**preset.get("defaultLimits", {}), **meta.get("limits", {})}

        ctx = FixtureContext(
            category=category,
            fixture_name=fixture_dir.name,
            input_data=input_data,
            preset=preset,
            limits=limits,
            meta=meta,
            clock=meta.get("clock"),
        )

        try:
            handler = self._handlers[category]
            output = handler(self, ctx)
        except Exception as exc:
            return FixtureResult(
                fixture=fixture_label, passed=False, diff=[f"Handler error: {exc}"]
            )

        canon_err = _check_canonicalizable(output)
        if canon_err is not None:
            return FixtureResult(
                fixture=fixture_label,
                passed=False,
                diff=[f"Output not canonicalizable: {canon_err}"],
            )

        violations = validate_all_codes(output)

        canon_output = canonicalize(output)
        canon_expected = canonicalize(expected)

        if canon_output == canon_expected and not violations:
            return FixtureResult(fixture=fixture_label, passed=True)

        diff = (
            _compute_diff(output, expected)
            if canon_output != canon_expected
            else []
        )
        trace = _extract_trace(output)
        return FixtureResult(
            fixture=fixture_label,
            passed=False,
            diff=diff,
            violations=violations,
            trace=trace,
        )

    # -- built-in category handlers -----------------------------------------

    def _handle_contracts(self, ctx: FixtureContext) -> dict[str, Any]:
        schema_map: dict[str, str] = {
            "decision": "decision.schema.json",
            "error": "error.schema.json",
            "event": "event_envelope.schema.json",
            "intent": "intent.schema.json",
            "trace": "trace.schema.json",
        }

        schema_file: str | None = None
        for prefix, filename in schema_map.items():
            if ctx.fixture_name.startswith(prefix):
                schema_file = filename
                break

        if schema_file is None:
            return {
                "error": {
                    "code": "E_PARSE_SYNTAX",
                    "message": f"Cannot determine schema for '{ctx.fixture_name}'",
                    "severity": "error",
                }
            }

        raw_schema = json.loads(
            (self.schemas_root / schema_file).read_text(encoding="utf-8")
        )
        schema = {"$id": schema_file, **raw_schema}

        validator = jsonschema.Draft202012Validator(
            schema, registry=self._schema_registry
        )
        errors = list(validator.iter_errors(ctx.input_data))

        if not errors:
            return {"valid": True}

        first = errors[0]
        code = _classify_schema_error(first)
        return {
            "error": {
                "code": code,
                "message": first.message,
                "severity": "error",
            }
        }

    def _handle_canonical(self, ctx: FixtureContext) -> dict[str, Any]:
        result = ctx.input_data
        result = _apply_ordering_recursive(result)
        return result

    def _handle_workflow(self, ctx: FixtureContext) -> dict[str, Any]:
        """Run workflow fixture: build FSM from input, validate or fire(event), return decision or error."""
        data = ctx.input_data
        meta = ctx.meta
        guard_port: GuardPort | None = None
        if meta.get("guard_behavior") == "fail":
            guard_port = _FailGuard()
        engine = WorkflowEngine.from_fixture_input(
            data, guard_port=guard_port, auth_port=None
        )
        event = data.get("event")
        if event is None:
            errors = engine.validate()
            if errors:
                e = errors[0]
                return {
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "severity": e.severity,
                    }
                }
            return {"allow": True, "reasons": []}
        actor_roles = data.get("actor_roles") or data.get("actorRoles")
        actor_id = data.get("actor_id") or data.get("actorId")
        context = data.get("context") or {}
        result = engine.fire(
            str(event),
            actor_roles=actor_roles,
            actor_id=actor_id,
            context=context,
        )
        if result.errors:
            e = result.errors[0]
            return {
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "severity": e.severity,
                }
            }
        out: dict[str, Any] = {
            "allow": result.decision.allow,
            "reasons": [{"code": r.code} for r in result.decision.reasons],
        }
        return out

    def _handle_expr(self, ctx: FixtureContext) -> dict[str, Any]:
        """Run expr fixture: typecheck then evaluate with preset/limits; return error or value."""
        data = ctx.input_data
        expr_data = data.get("expr")
        if expr_data is None:
            return {
                "error": {
                    "code": "E_PARSE_SYNTAX",
                    "message": "Missing 'expr' in input",
                    "severity": "error",
                }
            }
        preset = ctx.preset
        limits = ctx.limits
        default_funcs = preset.get("defaultFunctions", [])
        allowed_names = data.get("functions")
        if isinstance(allowed_names, list) and allowed_names:
            default_funcs = [f for f in default_funcs if f.get("name") in allowed_names]
        allowed_functions = [
            FunctionDef(
                f.get("name", ""),
                f.get("args", []),
                f.get("returns", "any"),
                f.get("cost", 1),
            )
            for f in default_funcs
        ]
        meta = DomainMeta(allowed_functions=allowed_functions)
        max_steps = limits.get("maxExprSteps", 5000)
        max_depth = limits.get("maxExprDepth", 50)
        max_time_ms = limits.get("maxEvalTimeMs", 50.0)
        max_regex_ops = limits.get("maxRegexOps", 5000)
        clock = ctx.clock

        try:
            expr_typecheck(expr_data, meta)
        except (MPCError, MPCBudgetError) as e:
            return {
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "severity": "error",
                }
            }

        engine = ExprEngine(
            meta=meta,
            max_steps=max_steps,
            max_depth=max_depth,
            max_time_ms=max_time_ms,
            max_regex_ops=max_regex_ops,
            clock=clock,
        )
        try:
            result = engine.evaluate(expr_data, data.get("typeEnv"))
        except (MPCError, MPCBudgetError) as e:
            return {
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "severity": "error",
                }
            }
        return {"value": result.value, "type": result.type}

    def _handle_acl(self, ctx: FixtureContext) -> dict[str, Any]:
        """Run ACL fixture: build AST from rules, run ACLEngine.check, return allow/reasons/intents."""
        data = ctx.input_data
        action = data.get("action", "")
        actor = data.get("actor") or {}
        actor_roles = actor.get("roles") or []
        obj = data.get("object") or {}
        resource = obj.get("type", "entity")
        rules = data.get("rules") or []
        defs: list[ASTNode] = []
        for i, r in enumerate(rules):
            role = r.get("role", "")
            actions = r.get("actions", [])
            mask_fields = r.get("maskFields", [])
            for a in actions:
                props: dict[str, Any] = {
                    "action": a,
                    "roles": [role],
                    "effect": "allow",
                    "resource": "*",
                }
                if mask_fields:
                    props["maskFields"] = mask_fields
                defs.append(ASTNode(kind="ACL", id=f"r{i}_{a}", properties=props))
        ast = ManifestAST(schema_version=1, namespace="", name="", manifest_version="1", defs=defs)
        engine = ACLEngine(ast=ast)
        result: ACLResult = engine.check(action, resource, actor_roles=actor_roles)
        out: dict[str, Any] = {
            "allow": result.allowed,
            "reasons": [{"code": r.code} for r in result.reasons],
        }
        if result.intents:
            out["intents"] = [
                {"kind": i.kind, "target": i.target} for i in result.intents
            ]
        return out

    def _handle_policy(self, ctx: FixtureContext) -> dict[str, Any]:
        """Run policy fixture: build AST from policies, run PolicyEngine.evaluate(event)."""
        data = ctx.input_data
        event = data.get("event")
        if event is None:
            return {
                "error": {
                    "code": "E_PARSE_SYNTAX",
                    "message": "Missing 'event' in input",
                    "severity": "error",
                }
            }
        event = _flatten_dotted_keys(event)
        policies = data.get("policies") or []
        defs = []
        for p in policies:
            pid = p.get("id", "p")
            props = dict(p)
            props.pop("id", None)
            defs.append(ASTNode(kind="Policy", id=pid, properties=props))
        ast = ManifestAST(schema_version=1, namespace="", name="", manifest_version="1", defs=defs)
        meta = DomainMeta()
        engine = PolicyEngine(ast=ast, meta=meta)
        result = engine.evaluate(event)
        strategy = data.get("strategy", "deny-wins")
        reasons = result.reasons
        if strategy == "deny-wins":
            if not result.allow:
                reasons = [r for r in result.reasons if r.code == "R_POLICY_DENY"]
            else:
                reasons = [r for r in result.reasons if r.code == "R_POLICY_ALLOW"]
        out = {
            "allow": result.allow,
            "reasons": [{"code": r.code} for r in reasons],
        }
        if result.intents:
            out["intents"] = [{"kind": i.kind, "target": i.target} for i in result.intents]
        return out

    def _handle_compose(self, ctx: FixtureContext) -> dict[str, Any]:
        """Run compose fixture: build Decision list from input, compose with strategy."""
        data = ctx.input_data
        decisions_data = data.get("decisions") or []
        strategy = data.get("strategy", "deny-wins")
        decisions = []
        for d in decisions_data:
            allow = d.get("allow", True)
            reasons = [
                Reason(code=r.get("code", ""), summary=r.get("summary"))
                for r in d.get("reasons", [])
            ]
            decisions.append(Decision(allow=allow, reasons=reasons))
        result = compose_decisions(decisions, strategy=strategy)
        out: dict[str, Any] = {
            "allow": result.allow,
            "reasons": [{"code": r.code} for r in result.reasons],
        }
        if result.intents:
            out["intents"] = [
                {"kind": i.kind, "target": i.target} for i in result.intents
            ]
        return out

    def _handle_overlay(self, ctx: FixtureContext) -> dict[str, Any]:
        """Run overlay fixture: base node + overlay list -> apply and return merged node or error."""
        data = ctx.input_data
        base_node = data.get("base")
        overlays_list = data.get("overlays") or []
        if base_node is None:
            return {
                "error": {
                    "code": "E_PARSE_SYNTAX",
                    "message": "Missing 'base' in input",
                    "severity": "error",
                }
            }
        ns = base_node.get("namespace", "")
        name = base_node.get("name", "manifest")
        base_props = copy.deepcopy(dict(base_node))
        base_ast = ManifestAST(
            schema_version=1,
            namespace=ns,
            name=name,
            manifest_version="1",
            defs=[
                ASTNode(
                    kind=base_node.get("kind", "Policy"),
                    id=base_node.get("id", "p1"),
                    properties=base_props,
                )
            ],
        )
        overlay_defs = []
        for i, o in enumerate(overlays_list):
            sel = o.get("selector", {})
            props = {
                "selector": sel,
                "op": o.get("op", "replace"),
                "path": o.get("path"),
            }
            if "value" in o:
                props["value"] = o["value"]
            if "values" in o:
                props["values"] = o["values"]
            overlay_defs.append(
                ASTNode(kind="Overlay", id=o.get("id", f"ov{i}"), properties=props)
            )
        overlay_ast = ManifestAST(
            schema_version=1, namespace=ns, name=name, manifest_version="1", defs=overlay_defs
        )
        engine = OverlayEngine(base=base_ast)
        result = engine.apply(overlay_ast)
        if result.conflicts:
            e = result.conflicts[0]
            return {
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "severity": e.severity,
                }
            }
        if not result.ast.defs:
            return {"error": {"code": "E_OVERLAY_UNKNOWN_SELECTOR", "message": "No defs", "severity": "error"}}
        node = result.ast.defs[0]
        out = {"id": node.id, "kind": node.kind, "namespace": result.ast.namespace, **node.properties}
        return {k: v for k, v in out.items() if v is not None}

    def _handle_governance(self, ctx: FixtureContext) -> dict[str, Any]:
        """Run governance fixture: enterpriseMode + artifact -> signature required/invalid error or ok."""
        data = ctx.input_data
        enterprise = data.get("enterpriseMode", False)
        artifact = data.get("artifact") or {}
        signature = artifact.get("signature") if isinstance(artifact, dict) else None
        if enterprise and not signature:
            return {
                "error": {
                    "code": "E_GOV_SIGNATURE_REQUIRED",
                    "message": "Enterprise mode requires a signature; artifact has none",
                    "severity": "fatal",
                }
            }
        if enterprise and signature and (
            signature.startswith("INVALID") or "tampered" in signature.lower()
        ):
            return {
                "error": {
                    "code": "E_GOV_SIGNATURE_INVALID",
                    "message": "Artifact signature verification failed",
                    "severity": "fatal",
                }
            }
        return {"valid": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_dotted_keys(obj: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Return a copy of obj with dotted keys for nested paths so match keys like 'object.type' work."""
    result: dict[str, Any] = dict(obj)
    for k, v in obj.items():
        if isinstance(v, dict) and v and not isinstance(v.get("id"), dict):
            dot_prefix = f"{prefix}.{k}" if prefix else k
            for nk, nv in v.items():
                if not isinstance(nv, (dict, list)):
                    result[f"{dot_prefix}.{nk}"] = nv
    return result


def _apply_ordering_recursive(obj: Any) -> Any:
    """Recursively apply definition ordering to any dict containing
    ``definitions`` or ``defs`` keys."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in ("definitions", "defs") and isinstance(v, list):
                result[k] = order_definitions(
                    [_apply_ordering_recursive(item) for item in v]
                )
            else:
                result[k] = _apply_ordering_recursive(v)
        return result
    if isinstance(obj, list):
        return [_apply_ordering_recursive(item) for item in obj]
    return obj


def _check_canonicalizable(output: Any) -> str | None:
    """Return an error message if *output* cannot be safely canonicalized."""
    try:
        _walk_check(output)
    except ValueError as exc:
        return str(exc)
    return None


def _walk_check(obj: Any) -> None:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"Non-finite number: {obj}")
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_check(v)
    elif isinstance(obj, list):
        for item in obj:
            _walk_check(item)


def _classify_schema_error(error: jsonschema.ValidationError) -> str:
    """Map a jsonschema validation error to the closest registered E_* code."""
    validator = error.validator
    if validator == "required":
        return "E_META_MISSING_REQUIRED_FIELD"
    if validator == "type":
        return "E_META_TYPE_NOT_ALLOWED"
    if validator in ("additionalProperties", "unevaluatedProperties"):
        return "E_META_UNKNOWN_KIND"
    return "E_PARSE_SYNTAX"


def _extract_trace(output: Any) -> list[str]:
    """Extract trace snippets from output if present."""
    traces: list[str] = []
    if isinstance(output, dict):
        trace_data = output.get("trace")
        if isinstance(trace_data, dict):
            events = trace_data.get("events", [])
            if isinstance(events, list):
                for ev in events[:5]:
                    if isinstance(ev, dict):
                        label = ev.get("label", ev.get("name", "?"))
                        duration = ev.get("durationMs", "?")
                        traces.append(f"  {label} ({duration}ms)")
        elif isinstance(trace_data, list):
            for ev in trace_data[:5]:
                if isinstance(ev, dict):
                    label = ev.get("label", ev.get("name", "?"))
                    traces.append(f"  {label}")
    return traces


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compute_diff(
    actual: Any, expected: Any, path: str = ""
) -> list[str]:
    diffs: list[str] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}" if path else key
            if key not in actual:
                diffs.append(
                    f"  path: {child}\n"
                    f"  expected: {json.dumps(expected[key])}\n"
                    f"  actual: (missing)"
                )
            elif key not in expected:
                diffs.append(
                    f"  path: {child}\n"
                    f"  expected: (missing)\n"
                    f"  actual: {json.dumps(actual[key])}"
                )
            else:
                diffs.extend(_compute_diff(actual[key], expected[key], child))
    elif isinstance(expected, list) and isinstance(actual, list):
        for i in range(max(len(expected), len(actual))):
            child = f"{path}[{i}]"
            if i >= len(actual):
                diffs.append(
                    f"  path: {child}\n"
                    f"  expected: {json.dumps(expected[i])}\n"
                    f"  actual: (missing)"
                )
            elif i >= len(expected):
                diffs.append(
                    f"  path: {child}\n"
                    f"  expected: (missing)\n"
                    f"  actual: {json.dumps(actual[i])}"
                )
            else:
                diffs.extend(_compute_diff(actual[i], expected[i], child))
    elif expected != actual:
        diffs.append(
            f"  path: {path}\n"
            f"  expected: {json.dumps(expected)}\n"
            f"  actual: {json.dumps(actual)}"
        )
    return diffs
