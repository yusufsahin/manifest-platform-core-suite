"""Expression IR — typed intermediate representation for manifest expressions.

JSON form examples:
    {"lit": 5}                                → ExprLit(5)
    {"ref": "name"}                           → ExprRef("name")
    {"fn": "len", "args": [{"lit": "abc"}]}   → ExprCall("len", [ExprLit("abc")])
    {"op": "+", "left": {...}, "right": {...}} → ExprBinOp("+", left, right)
    {"not": {...}}                             → ExprUnary("not", operand)
    {"if": {...}, "then": {...}, "else": {...}} → ExprCond(test, then_, else_)

No host-language eval. All evaluation goes through the budget-enforced evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# IR node types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExprLit:
    """Literal value: int, float, string, bool, or null."""
    value: Any

@dataclass(frozen=True)
class ExprRef:
    """Variable reference resolved from the evaluation context."""
    name: str

@dataclass(frozen=True)
class ExprCall:
    """Function call — must be declared in DomainMeta.allowed_functions."""
    fn: str
    args: tuple[ExprNode, ...] = ()

@dataclass(frozen=True)
class ExprBinOp:
    """Binary operator: arithmetic (+, -, *, /, %), comparison (==, !=, <, >, <=, >=),
    logical (and, or), string (matches)."""
    op: str
    left: "ExprNode | None" = None
    right: "ExprNode | None" = None

    def __post_init__(self) -> None:
        if self.left is None or self.right is None:
            raise ValueError(
                f"ExprBinOp(op='{self.op}') requires both 'left' and 'right' operands"
            )

@dataclass(frozen=True)
class ExprUnary:
    """Unary operator: 'not' (logical negation), 'neg' (arithmetic negation)."""
    op: str
    operand: "ExprNode | None" = None

    def __post_init__(self) -> None:
        if self.operand is None:
            raise ValueError(
                f"ExprUnary(op='{self.op}') requires an 'operand'"
            )

@dataclass(frozen=True)
class ExprCond:
    """Conditional: if test then then_ else else_."""
    test: "ExprNode | None" = None
    then_: "ExprNode | None" = None
    else_: "ExprNode | None" = None

    def __post_init__(self) -> None:
        if self.test is None or self.then_ is None or self.else_ is None:
            raise ValueError(
                "ExprCond requires 'test', 'then_', and 'else_' operands"
            )


ExprNode = ExprLit | ExprRef | ExprCall | ExprBinOp | ExprUnary | ExprCond


# ---------------------------------------------------------------------------
# JSON ↔ IR serialization
# ---------------------------------------------------------------------------

_BINARY_OPS = frozenset({
    "+", "-", "*", "/", "%",
    "==", "!=", "<", ">", "<=", ">=",
    "and", "or",
    "matches",
})

def from_dict(data: Any) -> ExprNode:
    """Deserialize a JSON-compatible dict into an IR node tree."""
    if not isinstance(data, dict):
        return ExprLit(data)

    if "lit" in data:
        return ExprLit(data["lit"])

    if "ref" in data:
        return ExprRef(data["ref"])

    if "fn" in data:
        raw_args = data.get("args", [])
        args = tuple(from_dict(a) for a in raw_args)
        return ExprCall(fn=data["fn"], args=args)

    if "op" in data and "left" in data and "right" in data:
        return ExprBinOp(
            op=data["op"],
            left=from_dict(data["left"]),
            right=from_dict(data["right"]),
        )

    if "not" in data:
        return ExprUnary(op="not", operand=from_dict(data["not"]))

    if "neg" in data:
        return ExprUnary(op="neg", operand=from_dict(data["neg"]))

    if "if" in data:
        return ExprCond(
            test=from_dict(data["if"]),
            then_=from_dict(data["then"]),
            else_=from_dict(data.get("else", {"lit": None})),
        )

    raise ValueError(f"Cannot parse expression IR: {data!r}")


def to_dict(node: ExprNode) -> Any:
    """Serialize an IR node tree into a JSON-compatible dict."""
    if isinstance(node, ExprLit):
        return {"lit": node.value}

    if isinstance(node, ExprRef):
        return {"ref": node.name}

    if isinstance(node, ExprCall):
        result: dict[str, Any] = {"fn": node.fn}
        if node.args:
            result["args"] = [to_dict(a) for a in node.args]
        return result

    if isinstance(node, ExprBinOp):
        return {
            "op": node.op,
            "left": to_dict(node.left),
            "right": to_dict(node.right),
        }

    if isinstance(node, ExprUnary):
        key = node.op  # "not" or "neg"
        return {key: to_dict(node.operand)}

    if isinstance(node, ExprCond):
        return {
            "if": to_dict(node.test),
            "then": to_dict(node.then_),
            "else": to_dict(node.else_),
        }

    raise TypeError(f"Unknown IR node type: {type(node)}")
