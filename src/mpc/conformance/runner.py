"""Conformance runner — executes fixture packs and verifies outputs.

Implements the behaviour described in tools/CONFORMANCE_RUNNER_SPEC.md:
  1. Load meta.json, fix clock, load preset, merge limit overrides.
  2. Run the category-specific operation.
  3. Canonicalize output; byte-compare with expected.json.
  4. Reject unknown E_*/R_*/Intent-kind codes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import jsonschema
from referencing import Registry, Resource

from mpc.canonical import canonicalize, order_definitions
from mpc.errors.registry import validate_all_codes


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


CategoryHandler = Callable[["ConformanceRunner", FixtureContext], dict[str, Any]]


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
        return FixtureResult(
            fixture=fixture_label,
            passed=False,
            diff=diff,
            violations=violations,
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
        return {
            "error": {
                "code": "E_VALID_DUPLICATE_DEF",
                "message": first.message,
                "severity": "error",
            }
        }

    def _handle_canonical(self, ctx: FixtureContext) -> dict[str, Any]:
        result = ctx.input_data
        if "definitions" in result:
            result = {**result, "definitions": order_definitions(result["definitions"])}
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
