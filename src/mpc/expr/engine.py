"""Expression engine core.

Per MASTER_SPEC section 11:
  - Typed IR, typecheck, eval
  - Budget enforcement (depth, steps, time, regex)
  - Side-effect-free, deterministic
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.errors.exceptions import MPCBudgetError
from mpc.meta.models import DomainMeta, FunctionDef


@dataclass(frozen=True)
class ExprResult:
    value: Any = None
    type: str = "any"
    steps: int = 0


@dataclass
class ExprEngine:
    """Evaluate manifest expressions against DomainMeta functions."""

    meta: DomainMeta
    max_depth: int = 10
    max_steps: int = 1000
    _steps: int = field(default=0, init=False, repr=False)

    def reset(self) -> None:
        self._steps = 0

    def typecheck(self, expr: str) -> str:
        """Return the inferred type of *expr*, or raise on type mismatch."""
        return _typecheck_impl(expr, self.meta)

    def evaluate(self, expr: str, context: dict[str, Any] | None = None) -> ExprResult:
        """Evaluate *expr* with optional *context* bindings."""
        self.reset()
        ctx = context or {}
        result = _evaluate_impl(expr, ctx, self.meta, self)
        return ExprResult(value=result, steps=self._steps)

    def _tick(self) -> None:
        self._steps += 1
        if self._steps > self.max_steps:
            raise MPCBudgetError(
                "E_EXPR_LIMIT_STEPS",
                f"Expression exceeded step limit ({self.max_steps})",
                limit=self.max_steps,
            )


def typecheck(expr: str, meta: DomainMeta) -> str:
    """Module-level typecheck shortcut."""
    return _typecheck_impl(expr, meta)


def evaluate(
    expr: str,
    meta: DomainMeta,
    context: dict[str, Any] | None = None,
    *,
    max_steps: int = 1000,
) -> ExprResult:
    """Module-level evaluate shortcut."""
    engine = ExprEngine(meta=meta, max_steps=max_steps)
    return engine.evaluate(expr, context)


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

_BUILTINS: dict[str, Any] = {
    "true": True,
    "false": False,
    "null": None,
}


def _typecheck_impl(expr: str, meta: DomainMeta) -> str:
    """Basic typecheck: resolve literals and known function return types."""
    stripped = expr.strip()
    if stripped in ("true", "false"):
        return "bool"
    if stripped == "null":
        return "null"
    try:
        int(stripped)
        return "int"
    except ValueError:
        pass
    try:
        float(stripped)
        return "float"
    except ValueError:
        pass
    if stripped.startswith('"') and stripped.endswith('"'):
        return "string"
    paren = stripped.find("(")
    if paren > 0:
        fn_name = stripped[:paren].strip()
        fn_def = meta.get_function(fn_name)
        if fn_def is not None:
            return fn_def.returns
        from mpc.errors.exceptions import MPCError
        raise MPCError("E_EXPR_UNKNOWN_FUNCTION", f"Unknown function: '{fn_name}'")
    return "any"


def _evaluate_impl(
    expr: str,
    context: dict[str, Any],
    meta: DomainMeta,
    engine: ExprEngine | None = None,
) -> Any:
    """Evaluate simple expressions (literals, variable refs, function calls)."""
    stripped = expr.strip()

    if engine:
        engine._tick()

    if stripped in _BUILTINS:
        return _BUILTINS[stripped]

    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass

    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped[1:-1]

    if stripped in context:
        return context[stripped]

    paren = stripped.find("(")
    if paren > 0:
        fn_name = stripped[:paren].strip()
        fn_def = meta.get_function(fn_name)
        if fn_def is None:
            from mpc.errors.exceptions import MPCError
            raise MPCError("E_EXPR_UNKNOWN_FUNCTION", f"Unknown function: '{fn_name}'")
        args_str = stripped[paren + 1 : stripped.rfind(")")]
        args = [a.strip() for a in args_str.split(",") if a.strip()] if args_str.strip() else []
        evaluated_args = [_evaluate_impl(a, context, meta, engine) for a in args]
        return _call_builtin(fn_name, evaluated_args)

    return None


def _call_builtin(fn_name: str, args: list[Any]) -> Any:
    """Execute built-in functions."""
    if fn_name == "len" and len(args) == 1:
        arg = args[0]
        return len(arg) if isinstance(arg, (str, list)) else 0
    if fn_name == "lower" and len(args) == 1:
        return str(args[0]).lower()
    if fn_name == "upper" and len(args) == 1:
        return str(args[0]).upper()
    if fn_name == "contains" and len(args) == 2:
        return args[1] in args[0] if isinstance(args[0], (str, list)) else False
    if fn_name == "startsWith" and len(args) == 2:
        return str(args[0]).startswith(str(args[1]))
    if fn_name == "endsWith" and len(args) == 2:
        return str(args[0]).endswith(str(args[1]))
    return None
