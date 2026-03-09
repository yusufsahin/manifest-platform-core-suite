"""Expression engine — typed IR, typecheck, eval, budget enforcement.

Per MASTER_SPEC section 11.
"""
from mpc.expr.engine import ExprEngine, ExprResult, typecheck, evaluate
from mpc.expr.ir import (
    ExprNode,
    ExprLit,
    ExprRef,
    ExprCall,
    ExprBinOp,
    ExprUnary,
    ExprCond,
    from_dict as ir_from_dict,
    to_dict as ir_to_dict,
)

__all__ = [
    "ExprEngine",
    "ExprResult",
    "typecheck",
    "evaluate",
    "ExprNode",
    "ExprLit",
    "ExprRef",
    "ExprCall",
    "ExprBinOp",
    "ExprUnary",
    "ExprCond",
    "ir_from_dict",
    "ir_to_dict",
]
