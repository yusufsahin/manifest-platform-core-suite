"""Tests for the expression engine — covers C1 (IR), C2 (typecheck), C3 (eval+clock), C4 (budget)."""
import pytest
from datetime import datetime, timezone

from mpc.kernel.errors import MPCError, MPCBudgetError
from mpc.kernel.meta.models import DomainMeta, FunctionDef
from mpc.features.expr.engine import (
    ExprEngine, ExprResult, typecheck, evaluate,
)
from mpc.features.expr.ir import (
    ExprLit, ExprRef, ExprCall, ExprBinOp, ExprUnary, ExprCond,
    ir_from_dict, ir_to_dict,
)


def _meta() -> DomainMeta:
    return DomainMeta(
        allowed_functions=[
            FunctionDef(name="len", args=["string"], returns="int"),
            FunctionDef(name="lower", args=["string"], returns="string"),
            FunctionDef(name="upper", args=["string"], returns="string"),
            FunctionDef(name="contains", args=["string", "string"], returns="bool"),
            FunctionDef(name="startsWith", args=["string", "string"], returns="bool"),
            FunctionDef(name="endsWith", args=["string", "string"], returns="bool"),
            FunctionDef(name="isEmpty", args=["any"], returns="bool"),
            FunctionDef(name="concat", args=["string", "string"], returns="string"),
            FunctionDef(name="substr", args=["string", "int", "int"], returns="string"),
            FunctionDef(name="abs", args=["number"], returns="number"),
            FunctionDef(name="min", args=["number", "number"], returns="number"),
            FunctionDef(name="max", args=["number", "number"], returns="number"),
            FunctionDef(name="now", args=[], returns="string"),
            FunctionDef(name="regex", args=["string", "string"], returns="bool"),
        ]
    )


# ===================================================================
# C1 — IR + JSON form
# ===================================================================

class TestIR:
    def test_lit_int(self):
        node = ir_from_dict({"lit": 42})
        assert isinstance(node, ExprLit)
        assert node.value == 42

    def test_lit_string(self):
        node = ir_from_dict({"lit": "hello"})
        assert isinstance(node, ExprLit)
        assert node.value == "hello"

    def test_lit_bool(self):
        node = ir_from_dict({"lit": True})
        assert isinstance(node, ExprLit)
        assert node.value is True

    def test_lit_null(self):
        node = ir_from_dict({"lit": None})
        assert isinstance(node, ExprLit)
        assert node.value is None

    def test_ref(self):
        node = ir_from_dict({"ref": "user_name"})
        assert isinstance(node, ExprRef)
        assert node.name == "user_name"

    def test_fn_call(self):
        node = ir_from_dict({"fn": "len", "args": [{"lit": "abc"}]})
        assert isinstance(node, ExprCall)
        assert node.fn == "len"
        assert len(node.args) == 1
        assert isinstance(node.args[0], ExprLit)

    def test_fn_no_args(self):
        node = ir_from_dict({"fn": "now"})
        assert isinstance(node, ExprCall)
        assert node.args == ()

    def test_nested_calls(self):
        node = ir_from_dict({
            "fn": "len",
            "args": [{"fn": "lower", "args": [{"lit": "ABC"}]}]
        })
        assert isinstance(node, ExprCall)
        inner = node.args[0]
        assert isinstance(inner, ExprCall)
        assert inner.fn == "lower"

    def test_binop(self):
        node = ir_from_dict({"op": "+", "left": {"lit": 1}, "right": {"lit": 2}})
        assert isinstance(node, ExprBinOp)
        assert node.op == "+"

    def test_unary_not(self):
        node = ir_from_dict({"not": {"lit": True}})
        assert isinstance(node, ExprUnary)
        assert node.op == "not"

    def test_unary_neg(self):
        node = ir_from_dict({"neg": {"lit": 5}})
        assert isinstance(node, ExprUnary)
        assert node.op == "neg"

    def test_cond(self):
        node = ir_from_dict({
            "if": {"lit": True},
            "then": {"lit": 1},
            "else": {"lit": 2},
        })
        assert isinstance(node, ExprCond)

    def test_roundtrip(self):
        original = {"fn": "len", "args": [{"ref": "items"}]}
        node = ir_from_dict(original)
        serialized = ir_to_dict(node)
        assert serialized == original

    def test_complex_roundtrip(self):
        original = {
            "if": {"op": ">", "left": {"ref": "x"}, "right": {"lit": 0}},
            "then": {"fn": "len", "args": [{"ref": "items"}]},
            "else": {"lit": 0},
        }
        node = ir_from_dict(original)
        serialized = ir_to_dict(node)
        assert serialized == original

    def test_raw_value_becomes_lit(self):
        node = ir_from_dict(42)
        assert isinstance(node, ExprLit)
        assert node.value == 42

    def test_invalid_dict_raises(self):
        with pytest.raises(ValueError, match="Cannot parse expression IR"):
            ir_from_dict({"unknown_key": "???"})


# ===================================================================
# C2 — Type checker
# ===================================================================

class TestTypecheck:
    def test_int_literal(self):
        assert typecheck("42", _meta()) == "int"

    def test_float_literal(self):
        assert typecheck("3.14", _meta()) == "float"

    def test_string_literal(self):
        assert typecheck('"hello"', _meta()) == "string"

    def test_bool_literal(self):
        assert typecheck("true", _meta()) == "bool"

    def test_null_literal(self):
        assert typecheck("null", _meta()) == "null"

    def test_known_function(self):
        assert typecheck("len(x)", _meta()) == "int"

    def test_unknown_function(self):
        with pytest.raises(MPCError) as exc_info:
            typecheck("unknown(x)", _meta())
        assert exc_info.value.code == "E_EXPR_UNKNOWN_FUNCTION"

    def test_ir_literal_typecheck(self):
        assert typecheck({"lit": 5}, _meta()) == "int"

    def test_ir_ref_typecheck(self):
        assert typecheck({"ref": "x"}, _meta()) == "any"

    def test_ir_fn_typecheck(self):
        assert typecheck({"fn": "len", "args": [{"lit": "abc"}]}, _meta()) == "int"

    def test_ir_type_mismatch(self):
        with pytest.raises(MPCError) as exc_info:
            typecheck({"fn": "len", "args": [{"lit": 5}]}, _meta())
        assert exc_info.value.code == "E_EXPR_TYPE_MISMATCH"

    def test_ir_binop_arithmetic(self):
        assert typecheck({"op": "+", "left": {"lit": 1}, "right": {"lit": 2}}, _meta()) == "number"

    def test_ir_binop_comparison(self):
        assert typecheck({"op": "==", "left": {"lit": 1}, "right": {"lit": 2}}, _meta()) == "bool"

    def test_ir_binop_logic(self):
        assert typecheck({"op": "and", "left": {"lit": True}, "right": {"lit": False}}, _meta()) == "bool"

    def test_ir_unary_not(self):
        assert typecheck({"not": {"lit": True}}, _meta()) == "bool"

    def test_ir_unary_neg(self):
        assert typecheck({"neg": {"lit": 5}}, _meta()) == "number"

    def test_ir_cond(self):
        result = typecheck({
            "if": {"lit": True},
            "then": {"lit": 42},
            "else": {"lit": 0},
        }, _meta())
        assert result == "int"


# ===================================================================
# C3 — Evaluator + clock injection
# ===================================================================

class TestEvaluate:
    def test_int_literal(self):
        result = evaluate("42", _meta())
        assert result.value == 42

    def test_string_literal(self):
        result = evaluate('"hello"', _meta())
        assert result.value == "hello"

    def test_bool_literal(self):
        result = evaluate("true", _meta())
        assert result.value is True

    def test_null_literal(self):
        result = evaluate("null", _meta())
        assert result.value is None

    def test_variable_from_context(self):
        result = evaluate("name", _meta(), context={"name": "Alice"})
        assert result.value == "Alice"

    def test_len_function(self):
        result = evaluate('len("abc")', _meta())
        assert result.value == 3

    def test_lower_function(self):
        result = evaluate('lower("ABC")', _meta())
        assert result.value == "abc"

    def test_upper_function(self):
        result = evaluate('upper("abc")', _meta())
        assert result.value == "ABC"

    def test_contains_function(self):
        result = evaluate({"fn": "contains", "args": [{"lit": "hello world"}, {"lit": "world"}]}, _meta())
        assert result.value is True

    def test_startsWith_function(self):
        result = evaluate({"fn": "startsWith", "args": [{"lit": "hello"}, {"lit": "hel"}]}, _meta())
        assert result.value is True

    def test_endsWith_function(self):
        result = evaluate({"fn": "endsWith", "args": [{"lit": "hello"}, {"lit": "llo"}]}, _meta())
        assert result.value is True

    def test_isEmpty_true(self):
        result = evaluate({"fn": "isEmpty", "args": [{"lit": ""}]}, _meta())
        assert result.value is True

    def test_isEmpty_false(self):
        result = evaluate({"fn": "isEmpty", "args": [{"lit": "data"}]}, _meta())
        assert result.value is False

    def test_concat(self):
        result = evaluate({"fn": "concat", "args": [{"lit": "a"}, {"lit": "b"}]}, _meta())
        assert result.value == "ab"

    def test_substr(self):
        result = evaluate({"fn": "substr", "args": [{"lit": "hello"}, {"lit": 1}, {"lit": 3}]}, _meta())
        assert result.value == "ell"

    def test_abs_function(self):
        result = evaluate({"fn": "abs", "args": [{"lit": -5}]}, _meta())
        assert result.value == 5

    def test_min_max(self):
        result_min = evaluate({"fn": "min", "args": [{"lit": 3}, {"lit": 1}]}, _meta())
        result_max = evaluate({"fn": "max", "args": [{"lit": 3}, {"lit": 1}]}, _meta())
        assert result_min.value == 1
        assert result_max.value == 3

    def test_unknown_function_raises(self):
        with pytest.raises(MPCError) as exc_info:
            evaluate("nope(x)", _meta())
        assert exc_info.value.code == "E_EXPR_UNKNOWN_FUNCTION"

    def test_ir_binop_add(self):
        result = evaluate({"op": "+", "left": {"lit": 10}, "right": {"lit": 5}}, _meta())
        assert result.value == 15

    def test_ir_binop_subtract(self):
        result = evaluate({"op": "-", "left": {"lit": 10}, "right": {"lit": 3}}, _meta())
        assert result.value == 7

    def test_ir_binop_multiply(self):
        result = evaluate({"op": "*", "left": {"lit": 4}, "right": {"lit": 3}}, _meta())
        assert result.value == 12

    def test_ir_binop_divide(self):
        result = evaluate({"op": "/", "left": {"lit": 10}, "right": {"lit": 4}}, _meta())
        assert result.value == 2.5

    def test_ir_binop_divide_by_zero(self):
        with pytest.raises(Exception) as exc_info:
            evaluate({"op": "/", "left": {"lit": 10}, "right": {"lit": 0}}, _meta())
        assert "DIV_BY_ZERO" in str(exc_info.value)

    def test_ir_binop_modulo(self):
        result = evaluate({"op": "%", "left": {"lit": 10}, "right": {"lit": 3}}, _meta())
        assert result.value == 1

    def test_ir_binop_eq(self):
        result = evaluate({"op": "==", "left": {"lit": 5}, "right": {"lit": 5}}, _meta())
        assert result.value is True

    def test_ir_binop_neq(self):
        result = evaluate({"op": "!=", "left": {"lit": 5}, "right": {"lit": 3}}, _meta())
        assert result.value is True

    def test_ir_binop_lt(self):
        result = evaluate({"op": "<", "left": {"lit": 3}, "right": {"lit": 5}}, _meta())
        assert result.value is True

    def test_ir_binop_string_concat(self):
        result = evaluate({"op": "+", "left": {"lit": "a"}, "right": {"lit": "b"}}, _meta())
        assert result.value == "ab"

    def test_ir_binop_and(self):
        result = evaluate({"op": "and", "left": {"lit": True}, "right": {"lit": False}}, _meta())
        assert result.value is False

    def test_ir_binop_or(self):
        result = evaluate({"op": "or", "left": {"lit": False}, "right": {"lit": True}}, _meta())
        assert result.value is True

    def test_ir_unary_not(self):
        result = evaluate({"not": {"lit": True}}, _meta())
        assert result.value is False

    def test_ir_unary_neg(self):
        result = evaluate({"neg": {"lit": 5}}, _meta())
        assert result.value == -5

    def test_ir_cond_true(self):
        result = evaluate({
            "if": {"lit": True},
            "then": {"lit": "yes"},
            "else": {"lit": "no"},
        }, _meta())
        assert result.value == "yes"

    def test_ir_cond_false(self):
        result = evaluate({
            "if": {"lit": False},
            "then": {"lit": "yes"},
            "else": {"lit": "no"},
        }, _meta())
        assert result.value == "no"

    def test_nested_expression(self):
        """Test: if len(name) > 3 then upper(name) else lower(name)"""
        expr = {
            "if": {"op": ">", "left": {"fn": "len", "args": [{"ref": "name"}]}, "right": {"lit": 3}},
            "then": {"fn": "upper", "args": [{"ref": "name"}]},
            "else": {"fn": "lower", "args": [{"ref": "name"}]},
        }
        result = evaluate(expr, _meta(), context={"name": "Alice"})
        assert result.value == "ALICE"

        result2 = evaluate(expr, _meta(), context={"name": "Bo"})
        assert result2.value == "bo"

    def test_clock_injection(self):
        clock = "2026-02-22T00:00:00+03:00"
        result = evaluate({"fn": "now"}, _meta(), clock=clock)
        assert result.value == clock

    def test_clock_injection_datetime(self):
        clock = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = evaluate({"fn": "now"}, _meta(), clock=clock)
        assert "2026-01-15" in result.value

    def test_regex_function(self):
        result = evaluate(
            {"fn": "regex", "args": [{"lit": "hello123"}, {"lit": "\\d+"}]},
            _meta(),
        )
        assert result.value is True

    def test_regex_no_match(self):
        result = evaluate(
            {"fn": "regex", "args": [{"lit": "hello"}, {"lit": "\\d+"}]},
            _meta(),
        )
        assert result.value is False

    def test_matches_operator(self):
        result = evaluate(
            {"op": "matches", "left": {"lit": "abc123"}, "right": {"lit": "[0-9]+"}},
            _meta(),
        )
        assert result.value is True

    def test_steps_tracked(self):
        result = evaluate("42", _meta())
        assert result.steps >= 1

    def test_depth_tracked(self):
        result = evaluate(
            {"fn": "len", "args": [{"fn": "lower", "args": [{"lit": "ABC"}]}]},
            _meta(),
        )
        assert result.depth >= 2


# ===================================================================
# C4 — Budget enforcement
# ===================================================================

class TestBudget:
    def test_step_limit(self):
        with pytest.raises(MPCBudgetError) as exc_info:
            evaluate("42", _meta(), max_steps=0)
        assert exc_info.value.code == "E_BUDGET_EXCEEDED"

    def test_step_limit_ir(self):
        with pytest.raises(MPCBudgetError) as exc_info:
            evaluate({"fn": "len", "args": [{"lit": "hello"}]}, _meta(), max_steps=1)
        assert exc_info.value.code == "E_BUDGET_EXCEEDED"

    def test_depth_limit(self):
        with pytest.raises(MPCBudgetError) as exc_info:
            evaluate(
                {"fn": "isEmpty", "args": [{"fn": "len", "args": [{"lit": "hello"}]}]},
                _meta(),
                max_depth=1,
            )
        assert exc_info.value.code == "E_EXPR_LIMIT_DEPTH"

    def test_regex_limit(self):
        with pytest.raises(MPCBudgetError) as exc_info:
            evaluate(
                {"fn": "regex", "args": [{"lit": "abc"}, {"lit": "a"}]},
                _meta(),
                max_regex_ops=0,
            )
        assert exc_info.value.code == "E_EXPR_REGEX_LIMIT"

    def test_matches_regex_budget(self):
        with pytest.raises(MPCBudgetError) as exc_info:
            evaluate(
                {"op": "matches", "left": {"lit": "abc"}, "right": {"lit": "a"}},
                _meta(),
                max_regex_ops=0,
            )
        assert exc_info.value.code == "E_EXPR_REGEX_LIMIT"

    def test_div_by_zero_raises(self):
        with pytest.raises(MPCError) as exc_info:
            evaluate(
                {"op": "/", "left": {"lit": 10}, "right": {"lit": 0}},
                _meta(),
            )
        assert exc_info.value.code == "E_EXPR_DIV_BY_ZERO"

    def test_mod_by_zero_raises(self):
        with pytest.raises(MPCError) as exc_info:
            evaluate(
                {"op": "%", "left": {"lit": 10}, "right": {"lit": 0}},
                _meta(),
            )
        assert exc_info.value.code == "E_EXPR_DIV_BY_ZERO"

    def test_invalid_regex_raises(self):
        with pytest.raises(MPCError) as exc_info:
            evaluate(
                {"fn": "regex", "args": [{"lit": "hello"}, {"lit": "[invalid("}]},
                _meta(),
            )
        assert exc_info.value.code == "E_EXPR_INVALID_REGEX"

    def test_invalid_regex_in_matches_raises(self):
        with pytest.raises(MPCError) as exc_info:
            evaluate(
                {"op": "matches", "left": {"lit": "hello"}, "right": {"lit": "[invalid("}},
                _meta(),
            )
        assert exc_info.value.code == "E_EXPR_INVALID_REGEX"

    def test_step_limit_message(self):
        with pytest.raises(MPCBudgetError) as exc_info:
            evaluate("42", _meta(), max_steps=0)
        assert "step budget" in exc_info.value.message.lower()
        assert exc_info.value.limit == 0

    def test_depth_limit_message(self):
        with pytest.raises(MPCBudgetError) as exc_info:
            evaluate(
                {"fn": "isEmpty", "args": [{"fn": "len", "args": [{"lit": "x"}]}]},
                _meta(),
                max_depth=1,
            )
        assert "depth" in exc_info.value.message.lower()
        assert exc_info.value.limit == 1


# ===================================================================
# ExprEngine class interface
# ===================================================================

class TestExprEngine:
    def test_instance(self):
        engine = ExprEngine(meta=_meta())
        result = engine.evaluate("42")
        assert result.value == 42

    def test_typecheck_method(self):
        engine = ExprEngine(meta=_meta())
        assert engine.typecheck("len(x)") == "int"

    def test_ir_evaluate(self):
        engine = ExprEngine(meta=_meta())
        result = engine.evaluate({"fn": "len", "args": [{"lit": "test"}]})
        assert result.value == 4

    def test_ir_typecheck(self):
        engine = ExprEngine(meta=_meta())
        assert engine.typecheck({"fn": "lower", "args": [{"lit": "X"}]}) == "string"

    def test_engine_clock(self):
        engine = ExprEngine(meta=_meta(), clock="2026-06-01T12:00:00Z")
        result = engine.evaluate({"fn": "now"})
        assert result.value == "2026-06-01T12:00:00Z"

    def test_engine_budget_config(self):
        engine = ExprEngine(meta=_meta(), max_steps=2, max_depth=5)
        result = engine.evaluate({"lit": 42})
        assert result.value == 42

    def test_result_has_type(self):
        engine = ExprEngine(meta=_meta())
        result = engine.evaluate({"lit": 42})
        assert result.type == "int"

    def test_result_has_steps_and_depth(self):
        engine = ExprEngine(meta=_meta())
        result = engine.evaluate({"fn": "len", "args": [{"lit": "abc"}]})
        assert result.steps > 0
        assert result.depth > 0

    def test_node_input(self):
        engine = ExprEngine(meta=_meta())
        node = ExprCall(fn="len", args=(ExprLit("abc"),))
        result = engine.evaluate(node)
        assert result.value == 3
