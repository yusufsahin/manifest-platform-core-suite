"""Tests for the expression engine."""
import pytest

from mpc.errors import MPCError, MPCBudgetError
from mpc.meta import DomainMeta, FunctionDef
from mpc.expr import ExprEngine, ExprResult, typecheck, evaluate


def _meta() -> DomainMeta:
    return DomainMeta(
        allowed_functions=[
            FunctionDef(name="len", args=["string"], returns="int"),
            FunctionDef(name="lower", args=["string"], returns="string"),
            FunctionDef(name="upper", args=["string"], returns="string"),
            FunctionDef(name="contains", args=["string", "string"], returns="bool"),
        ]
    )


class TestTypecheck:
    def test_int_literal(self):
        assert typecheck("42", _meta()) == "int"

    def test_float_literal(self):
        assert typecheck("3.14", _meta()) == "float"

    def test_string_literal(self):
        assert typecheck('"hello"', _meta()) == "string"

    def test_bool_literal(self):
        assert typecheck("true", _meta()) == "bool"

    def test_known_function(self):
        assert typecheck("len(x)", _meta()) == "int"

    def test_unknown_function(self):
        with pytest.raises(MPCError) as exc_info:
            typecheck("unknown(x)", _meta())
        assert exc_info.value.code == "E_EXPR_UNKNOWN_FUNCTION"


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

    def test_unknown_function_raises(self):
        with pytest.raises(MPCError) as exc_info:
            evaluate("nope(x)", _meta())
        assert exc_info.value.code == "E_EXPR_UNKNOWN_FUNCTION"

    def test_step_limit(self):
        with pytest.raises(MPCBudgetError) as exc_info:
            evaluate("42", _meta(), max_steps=0)
        assert exc_info.value.code == "E_EXPR_LIMIT_STEPS"

    def test_steps_tracked(self):
        result = evaluate("42", _meta())
        assert result.steps >= 1


class TestExprEngine:
    def test_instance(self):
        engine = ExprEngine(meta=_meta())
        result = engine.evaluate("42")
        assert result.value == 42

    def test_typecheck_method(self):
        engine = ExprEngine(meta=_meta())
        assert engine.typecheck("len(x)") == "int"
