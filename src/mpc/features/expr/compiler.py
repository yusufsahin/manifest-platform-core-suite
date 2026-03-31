from __future__ import annotations

from enum import IntEnum, auto
from typing import Any, List, Tuple
from mpc.features.expr.ir import (
    ExprNode, ExprLit, ExprRef, ExprCall, ExprBinOp, ExprUnary, ExprCond
)
from mpc.kernel.errors.exceptions import MPCError

class OpCode(IntEnum):
    PUSH_LIT = auto()
    PUSH_REF = auto()
    CALL = auto()
    BINARY_OP = auto()
    UNARY_OP = auto()
    JUMP_IF_FALSE = auto()
    JUMP = auto()
    POP = auto()
    RETURN = auto()

class BytecodeCompiler:
    def __init__(self):
        self.instructions: List[Tuple[OpCode, Any]] = []

    def compile(self, node: ExprNode) -> List[Tuple[OpCode, Any]]:
        self.instructions = []
        self._compile_node(node)
        self.instructions.append((OpCode.RETURN, None))
        return self.instructions

    def _compile_node(self, node: ExprNode):
        if isinstance(node, ExprLit):
            self.instructions.append((OpCode.PUSH_LIT, node.value))
        
        elif isinstance(node, ExprRef):
            self.instructions.append((OpCode.PUSH_REF, node.name))
        
        elif isinstance(node, ExprCall):
            for arg in node.args:
                self._compile_node(arg)
            self.instructions.append((OpCode.CALL, (node.fn, len(node.args))))
            
        elif isinstance(node, ExprBinOp):
            if node.op == "and":
                # Short-circuit: if left is false, keep it and skip right.
                # If left is true, pop it and evaluate right.
                self._compile_node(node.left)
                jump_idx = len(self.instructions)
                self.instructions.append((OpCode.JUMP_IF_FALSE, 0))  # placeholder
                self.instructions.append((OpCode.POP, None))
                self._compile_node(node.right)
                self.instructions[jump_idx] = (OpCode.JUMP_IF_FALSE, len(self.instructions))
            elif node.op == "or":
                # Short-circuit: if left is truthy, skip right and return left's value.
                # Pattern:
                #   <left>
                #   JUMP_IF_FALSE  -> right_label   (left is false: pop and eval right)
                #   JUMP           -> end_label      (left is true: keep it on stack)
                # right_label:
                #   POP                              (discard false left)
                #   <right>
                # end_label:
                self._compile_node(node.left)
                false_jump_idx = len(self.instructions)
                self.instructions.append((OpCode.JUMP_IF_FALSE, 0))  # placeholder
                end_jump_idx = len(self.instructions)
                self.instructions.append((OpCode.JUMP, 0))           # placeholder
                # right_label: left was false, pop it and evaluate right
                self.instructions[false_jump_idx] = (OpCode.JUMP_IF_FALSE, len(self.instructions))
                self.instructions.append((OpCode.POP, None))
                self._compile_node(node.right)
                # end_label: left was true, its value is already on the stack
                self.instructions[end_jump_idx] = (OpCode.JUMP, len(self.instructions))
            else:
                self._compile_node(node.left)
                self._compile_node(node.right)
                self.instructions.append((OpCode.BINARY_OP, node.op))
                
        elif isinstance(node, ExprUnary):
            self._compile_node(node.operand)
            self.instructions.append((OpCode.UNARY_OP, node.op))
            
        elif isinstance(node, ExprCond):
            # Keep test value for branching, then pop before evaluating chosen branch.
            self._compile_node(node.test)
            else_jump_idx = len(self.instructions)
            self.instructions.append((OpCode.JUMP_IF_FALSE, 0))
            self.instructions.append((OpCode.POP, None))
            self._compile_node(node.then_)
            end_jump_idx = len(self.instructions)
            self.instructions.append((OpCode.JUMP, 0))
            self.instructions[else_jump_idx] = (OpCode.JUMP_IF_FALSE, len(self.instructions))
            self.instructions.append((OpCode.POP, None))
            self._compile_node(node.else_)
            self.instructions[end_jump_idx] = (OpCode.JUMP, len(self.instructions))

class BytecodeVM:
    def __init__(self, builtins, budget):
        self.builtins = builtins
        self.budget = budget
        self.stack: List[Any] = []

    def execute(self, instructions: List[Tuple[OpCode, Any]], ctx: dict, meta: Any) -> Any:
        pc = 0
        while pc < len(instructions):
            self.budget.tick()
            op, arg = instructions[pc]
            
            if op == OpCode.PUSH_LIT:
                self.stack.append(arg)
            elif op == OpCode.PUSH_REF:
                self.stack.append(ctx.get(arg))
            elif op == OpCode.CALL:
                fn_name, arg_count = arg
                args = [self.stack.pop() for _ in range(arg_count)]
                args.reverse()
                builtin = self.builtins.get(fn_name)
                if builtin:
                    self.stack.append(builtin(args, ctx))
                else:
                    self.stack.append(None)
            elif op == OpCode.BINARY_OP:
                right = self.stack.pop()
                left = self.stack.pop()
                self.stack.append(self._eval_binop(arg, left, right))
            elif op == OpCode.UNARY_OP:
                val = self.stack.pop()
                self.stack.append(not val if arg == "not" else -val)
            elif op == OpCode.JUMP_IF_FALSE:
                if not self.stack[-1]:
                    pc = arg
                    continue
            elif op == OpCode.JUMP:
                pc = arg
                continue
            elif op == OpCode.POP:
                self.stack.pop()
            elif op == OpCode.RETURN:
                return self.stack.pop()
            
            pc += 1
        return None

    def _eval_binop(self, op, left, right):
        if op == "+": return left + right
        if op == "-": return left - right
        if op == "*": return left * right
        if op == "/":
            if right == 0:
                raise MPCError("E_EXPR_DIV_BY_ZERO", "Division by zero")
            return left / right
        if op == "%":
            if right == 0:
                raise MPCError("E_EXPR_DIV_BY_ZERO", "Modulo by zero")
            return left % right
        if op == "==": return left == right
        if op == "!=": return left != right
        if op == "<": return left < right
        if op == ">": return left > right
        if op == "<=": return left <= right
        if op == ">=": return left >= right
        if op == "and": return bool(left and right)
        if op == "or": return bool(left or right)
        if op == "matches":
            import re
            return bool(re.search(str(right), str(left)))
        return None
