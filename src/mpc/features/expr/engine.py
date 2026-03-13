"""Expression engine — typed IR, typecheck, eval, budget enforcement.

Per MASTER_SPEC section 11:
  - No host-language eval
  - Typed IR + typecheck
  - Budgets MUST be enforced: steps, depth, timeMs, regexOps
  - Side-effect-free, deterministic
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from mpc.kernel.errors.exceptions import MPCBudgetError, MPCError
from mpc.features.expr.ir import (
    ExprBinOp,
    ExprCall,
    ExprCond,
    ExprLit,
    ExprNode,
    ExprRef,
    ExprUnary,
    from_dict as ir_from_dict,
)
from mpc.kernel.meta.models import DomainMeta, FunctionDef


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExprResult:
    value: Any = None
    type: str = "any"
    steps: int = 0
    depth: int = 0


# ---------------------------------------------------------------------------
# Budget tracker
# ---------------------------------------------------------------------------

@dataclass
class _Budget:
    max_steps: int = 5000
    max_depth: int = 50
    max_time_ms: float = 50.0
    max_regex_ops: int = 5000

    _steps: int = field(default=0, init=False, repr=False)
    _depth: int = field(default=0, init=False, repr=False)
    _peak_depth: int = field(default=0, init=False, repr=False)
    _regex_ops: int = field(default=0, init=False, repr=False)
    _start_ns: int = field(default=0, init=False, repr=False)

    def start(self) -> None:
        self._steps = 0
        self._depth = 0
        self._peak_depth = 0
        self._regex_ops = 0
        self._start_ns = time.monotonic_ns()

    def tick(self) -> None:
        self._steps += 1
        if self._steps > self.max_steps:
            raise MPCBudgetError(
                "E_BUDGET_EXCEEDED",
                f"Expression evaluation exceeded step budget (limit: {self.max_steps})",
                limit=self.max_steps,
            )
        self._check_time()

    def push_depth(self) -> None:
        self._depth += 1
        if self._depth > self._peak_depth:
            self._peak_depth = self._depth
        if self._depth > self.max_depth:
            raise MPCBudgetError(
                "E_EXPR_LIMIT_DEPTH",
                f"Expression depth limit exceeded (limit: {self.max_depth})",
                limit=self.max_depth,
            )

    def pop_depth(self) -> None:
        self._depth -= 1

    def count_regex(self, n: int = 1) -> None:
        self._regex_ops += n
        if self._regex_ops > self.max_regex_ops:
            raise MPCBudgetError(
                "E_EXPR_REGEX_LIMIT",
                f"Regex operation limit exceeded (limit: {self.max_regex_ops})",
                limit=self.max_regex_ops,
            )

    def _check_time(self) -> None:
        if self.max_time_ms <= 0:
            return
        elapsed_ms = (time.monotonic_ns() - self._start_ns) / 1_000_000
        if elapsed_ms > self.max_time_ms:
            raise MPCBudgetError(
                "E_EXPR_LIMIT_TIME",
                f"Expression time limit exceeded (limit: {self.max_time_ms}ms)",
                limit=int(self.max_time_ms),
            )


# ---------------------------------------------------------------------------
# Type system
# ---------------------------------------------------------------------------

_LITERAL_TYPES: dict[type, str] = {
    bool: "bool",
    int: "int",
    float: "float",
    str: "string",
}

_ARITH_OPS = frozenset({"+", "-", "*", "/", "%"})
_CMP_OPS = frozenset({"==", "!=", "<", ">", "<=", ">="})
_LOGIC_OPS = frozenset({"and", "or"})


def _types_compatible(actual: str, expected: str) -> bool:
    """Check if *actual* is assignable to *expected* (supports union types like 'string|array')."""
    if actual == expected:
        return True
    if actual == "any" or expected == "any":
        return True
    if "|" in expected:
        return any(_types_compatible(actual, p.strip()) for p in expected.split("|"))
    if expected == "number" and actual in ("int", "float", "number"):
        return True
    if expected in ("int", "float") and actual == "number":
        return True
    return False


def _infer_type(node: ExprNode, meta: DomainMeta) -> str:
    """Infer the result type of an IR node. Raises MPCError on type issues."""
    if isinstance(node, ExprLit):
        if node.value is None:
            return "null"
        if isinstance(node.value, bool):
            return "bool"
        return _LITERAL_TYPES.get(type(node.value), "any")

    if isinstance(node, ExprRef):
        return "any"

    if isinstance(node, ExprCall):
        fn_def = meta.get_function(node.fn)
        if fn_def is None:
            raise MPCError("E_EXPR_UNKNOWN_FUNCTION", f"Unknown function: '{node.fn}'")
        if fn_def.args:
            for i, (arg_node, expected_type) in enumerate(
                zip(node.args, fn_def.args, strict=False)
            ):
                actual = _infer_type(arg_node, meta)
                if not _types_compatible(actual, expected_type):
                    raise MPCError(
                        "E_EXPR_TYPE_MISMATCH",
                        f"Argument {i} of '{node.fn}' expects '{expected_type}', "
                        f"got '{actual}'",
                    )
        return fn_def.returns

    if isinstance(node, ExprBinOp):
        if node.op in _ARITH_OPS:
            return "number"
        if node.op in _CMP_OPS:
            return "bool"
        if node.op in _LOGIC_OPS:
            return "bool"
        if node.op == "matches":
            return "bool"
        return "any"

    if isinstance(node, ExprUnary):
        if node.op == "not":
            return "bool"
        if node.op == "neg":
            return "number"
        return "any"

    if isinstance(node, ExprCond):
        return _infer_type(node.then_, meta)

    return "any"


# ---------------------------------------------------------------------------
# Built-in functions
# ---------------------------------------------------------------------------

_BUILTINS: dict[str, Any] = {}


def _register_builtin(name: str):
    def _decorator(fn):
        _BUILTINS[name] = fn
        return fn
    return _decorator


@_register_builtin("len")
def _fn_len(args: list[Any], _ctx: dict[str, Any]) -> int:
    if args and isinstance(args[0], (str, list, dict)):
        return len(args[0])
    return 0


@_register_builtin("lower")
def _fn_lower(args: list[Any], _ctx: dict[str, Any]) -> str:
    return str(args[0]).lower() if args else ""


@_register_builtin("upper")
def _fn_upper(args: list[Any], _ctx: dict[str, Any]) -> str:
    return str(args[0]).upper() if args else ""


@_register_builtin("contains")
def _fn_contains(args: list[Any], _ctx: dict[str, Any]) -> bool:
    if len(args) >= 2 and isinstance(args[0], (str, list)):
        return args[1] in args[0]
    return False


@_register_builtin("startsWith")
def _fn_starts_with(args: list[Any], _ctx: dict[str, Any]) -> bool:
    if len(args) >= 2:
        return str(args[0]).startswith(str(args[1]))
    return False


@_register_builtin("endsWith")
def _fn_ends_with(args: list[Any], _ctx: dict[str, Any]) -> bool:
    if len(args) >= 2:
        return str(args[0]).endswith(str(args[1]))
    return False


@_register_builtin("isEmpty")
def _fn_is_empty(args: list[Any], _ctx: dict[str, Any]) -> bool:
    if not args:
        return True
    v = args[0]
    if v is None:
        return True
    if isinstance(v, (str, list, dict)):
        return len(v) == 0
    return False


@_register_builtin("concat")
def _fn_concat(args: list[Any], _ctx: dict[str, Any]) -> str:
    return "".join(str(a) for a in args)


@_register_builtin("substr")
def _fn_substr(args: list[Any], _ctx: dict[str, Any]) -> str:
    if len(args) >= 2:
        s = str(args[0])
        start = int(args[1])
        length = int(args[2]) if len(args) >= 3 else len(s) - start
        return s[start:start + length]
    return ""


@_register_builtin("abs")
def _fn_abs(args: list[Any], _ctx: dict[str, Any]) -> int | float:
    if args:
        return abs(args[0])
    return 0


@_register_builtin("min")
def _fn_min(args: list[Any], _ctx: dict[str, Any]) -> Any:
    if args:
        return min(args)
    return None


@_register_builtin("max")
def _fn_max(args: list[Any], _ctx: dict[str, Any]) -> Any:
    if args:
        return max(args)
    return None


@_register_builtin("now")
def _fn_now(args: list[Any], ctx: dict[str, Any]) -> str:
    """Return the injected clock value. No system time access."""
    clock = ctx.get("__clock__")
    if clock is not None:
        if isinstance(clock, datetime):
            return clock.isoformat()
        return str(clock)
    return ""


@_register_builtin("regex")
def _fn_regex(args: list[Any], ctx: dict[str, Any]) -> bool:
    """Regex match — counts against the regex budget."""
    if len(args) < 2:
        return False
    text = str(args[0])
    pattern = str(args[1])
    budget: _Budget | None = ctx.get("__budget__")
    if budget:
        budget.count_regex()
    try:
        return bool(re.search(pattern, text))
    except re.error:
        return False


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def _eval_node(
    node: ExprNode,
    ctx: dict[str, Any],
    meta: DomainMeta,
    budget: _Budget,
) -> Any:
    """Recursively evaluate an IR node."""
    budget.tick()
    budget.push_depth()
    try:
        return _eval_dispatch(node, ctx, meta, budget)
    finally:
        budget.pop_depth()


def _eval_dispatch(
    node: ExprNode,
    ctx: dict[str, Any],
    meta: DomainMeta,
    budget: _Budget,
) -> Any:
    if isinstance(node, ExprLit):
        return node.value

    if isinstance(node, ExprRef):
        return ctx.get(node.name)

    if isinstance(node, ExprCall):
        fn_def = meta.get_function(node.fn)
        if fn_def is None:
            raise MPCError("E_EXPR_UNKNOWN_FUNCTION", f"Unknown function: '{node.fn}'")
        evaluated_args = [_eval_node(a, ctx, meta, budget) for a in node.args]
        builtin = _BUILTINS.get(node.fn)
        if builtin is not None:
            return builtin(evaluated_args, ctx)
        return None

    if isinstance(node, ExprBinOp):
        return _eval_binop(node, ctx, meta, budget)

    if isinstance(node, ExprUnary):
        val = _eval_node(node.operand, ctx, meta, budget)
        if node.op == "not":
            return not val
        if node.op == "neg":
            return -val if isinstance(val, (int, float)) else 0
        return val

    if isinstance(node, ExprCond):
        test_val = _eval_node(node.test, ctx, meta, budget)
        if test_val:
            return _eval_node(node.then_, ctx, meta, budget)
        return _eval_node(node.else_, ctx, meta, budget)

    return None


def _eval_binop(
    node: ExprBinOp,
    ctx: dict[str, Any],
    meta: DomainMeta,
    budget: _Budget,
) -> Any:
    def _to_number(value: Any) -> int | float:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        if value is None:
            return 0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0

    left = _eval_node(node.left, ctx, meta, budget)
    right = _eval_node(node.right, ctx, meta, budget)
    op = node.op

    if op == "+":
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        return _to_number(left) + _to_number(right)
    if op == "-":
        return _to_number(left) - _to_number(right)
    if op == "*":
        return _to_number(left) * _to_number(right)
    if op == "/":
        r = _to_number(right)
        if r == 0:
            return None
        return _to_number(left) / r
    if op == "%":
        r = _to_number(right)
        if r == 0:
            return None
        return _to_number(left) % r

    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right

    if op == "and":
        return bool(left and right)
    if op == "or":
        return bool(left or right)

    if op == "matches":
        budget.count_regex()
        try:
            return bool(re.search(str(right), str(left)))
        except re.error:
            return False

    return None


# ---------------------------------------------------------------------------
# String expression parser (backward compatible convenience)
# ---------------------------------------------------------------------------

_STR_BUILTINS: dict[str, Any] = {
    "true": True,
    "false": False,
    "null": None,
}


def _parse_string_expr(expr: str) -> ExprNode:
    """Convert a simple string expression to IR. Supports:
    - Literals: 42, 3.14, "hello", true, false, null
    - Variable references: name
    - Function calls: fn(arg1, arg2)
    """
    stripped = expr.strip()

    if stripped in _STR_BUILTINS:
        return ExprLit(_STR_BUILTINS[stripped])

    try:
        return ExprLit(int(stripped))
    except ValueError:
        pass
    try:
        return ExprLit(float(stripped))
    except ValueError:
        pass

    if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
        return ExprLit(stripped[1:-1])

    paren = stripped.find("(")
    if paren > 0 and stripped.endswith(")"):
        fn_name = stripped[:paren].strip()
        args_str = stripped[paren + 1:-1]
        raw_args = _split_args(args_str)
        args = tuple(_parse_string_expr(a) for a in raw_args)
        return ExprCall(fn=fn_name, args=args)

    return ExprRef(stripped)


def _split_args(args_str: str) -> list[str]:
    """Split comma-separated arguments, respecting nested parens and quotes."""
    args: list[str] = []
    depth = 0
    in_str = False
    current: list[str] = []
    for ch in args_str:
        if ch == '"' and depth == 0:
            in_str = not in_str
            current.append(ch)
        elif in_str:
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            arg = "".join(current).strip()
            if arg:
                args.append(arg)
            current = []
        else:
            current.append(ch)
    final = "".join(current).strip()
    if final:
        args.append(final)
    return args


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class ExprEngine:
    """Evaluate manifest expressions against DomainMeta functions.

    Supports both IR (dict/ExprNode) and string expressions.
    """
    meta: DomainMeta
    max_depth: int = 50
    max_steps: int = 5000
    max_time_ms: float = 50.0
    max_regex_ops: int = 5000
    clock: datetime | str | None = None

    def typecheck(self, expr: str | dict | ExprNode) -> str:
        """Return the inferred type of *expr*, or raise on type mismatch."""
        node = self._to_node(expr)
        return _infer_type(node, self.meta)

    def evaluate(
        self,
        expr: str | dict | ExprNode,
        context: dict[str, Any] | None = None,
    ) -> ExprResult:
        """Evaluate *expr* with optional *context* bindings."""
        node = self._to_node(expr)
        budget = _Budget(
            max_steps=self.max_steps,
            max_depth=self.max_depth,
            max_time_ms=self.max_time_ms,
            max_regex_ops=self.max_regex_ops,
        )
        budget.start()

        ctx = dict(context) if context else {}
        if self.clock is not None:
            ctx.setdefault("__clock__", self.clock)
        ctx["__budget__"] = budget

        result_val = _eval_node(node, ctx, self.meta, budget)
        result_type = _infer_type(node, self.meta)

        return ExprResult(
            value=result_val,
            type=result_type,
            steps=budget._steps,
            depth=budget._peak_depth,
        )

    def _to_node(self, expr: str | dict | ExprNode) -> ExprNode:
        if isinstance(expr, (ExprLit, ExprRef, ExprCall, ExprBinOp, ExprUnary, ExprCond)):
            return expr
        if isinstance(expr, dict):
            return ir_from_dict(expr)
        return _parse_string_expr(str(expr))


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def typecheck(expr: str | dict | ExprNode, meta: DomainMeta) -> str:
    """Module-level typecheck shortcut."""
    engine = ExprEngine(meta=meta)
    return engine.typecheck(expr)


def evaluate(
    expr: str | dict | ExprNode,
    meta: DomainMeta,
    context: dict[str, Any] | None = None,
    *,
    max_steps: int = 5000,
    max_depth: int = 50,
    max_time_ms: float = 50.0,
    max_regex_ops: int = 5000,
    clock: datetime | str | None = None,
) -> ExprResult:
    """Module-level evaluate shortcut."""
    engine = ExprEngine(
        meta=meta,
        max_steps=max_steps,
        max_depth=max_depth,
        max_time_ms=max_time_ms,
        max_regex_ops=max_regex_ops,
        clock=clock,
    )
    return engine.evaluate(expr, context)
