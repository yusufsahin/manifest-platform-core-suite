import pytest
from mpc.kernel.meta.models import DomainMeta, KindDef, FunctionDef
from mpc.features.expr.engine import evaluate
from mpc.kernel.meta.diff import diff_meta
from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.tooling.validator.semantic import validate_semantic
from mpc.tooling.validator.structural import validate_structural


def _meta() -> DomainMeta:
    return DomainMeta(
        allowed_functions=[
            FunctionDef(name="len", args=["string"], returns="int"),
            FunctionDef(name="lower", args=["string"], returns="string"),
            FunctionDef(name="upper", args=["string"], returns="string"),
            FunctionDef(name="contains", args=["string", "string"], returns="bool"),
            FunctionDef(name="substr", args=["string", "int", "int"], returns="string"),
            FunctionDef(name="abs", args=["number"], returns="number"),
            FunctionDef(name="min", args=["number", "number"], returns="number"),
            FunctionDef(name="max", args=["number", "number"], returns="number"),
            FunctionDef(name="now", args=[], returns="string"),
            FunctionDef(name="regex", args=["string", "string"], returns="bool"),
        ]
    )


class TestExprEdgeCases:
    def test_nested_arithmetic(self):
        expr = {
            "op": "/",
            "left": {
                "op": "*",
                "left": {"op": "+", "left": {"lit": 10}, "right": {"lit": 5}},
                "right": {"op": "-", "left": {"lit": 8}, "right": {"lit": 2}},
            },
            "right": {"lit": 3},
        }
        result = evaluate(expr, _meta())
        assert result.value == 30

    def test_substr_out_of_bounds_start(self):
        result = evaluate(
            {"fn": "substr", "args": [{"lit": "hello"}, {"lit": 10}, {"lit": 2}]},
            _meta(),
        )
        assert result.value == ""

    def test_substr_partial_length(self):
        result = evaluate(
            {"fn": "substr", "args": [{"lit": "hello"}, {"lit": 3}, {"lit": 10}]},
            _meta(),
        )
        assert result.value == "lo"

    def test_min_max_single_arg(self):
        result_min = evaluate({"fn": "min", "args": [{"lit": 42}]}, _meta())
        assert result_min.value == 42

        result_max = evaluate({"fn": "max", "args": [{"lit": 42}]}, _meta())
        assert result_max.value == 42

    def test_min_max_empty_args(self):
        result_min = evaluate({"fn": "min", "args": []}, _meta())
        assert result_min.value is None

        result_max = evaluate({"fn": "max", "args": []}, _meta())
        assert result_max.value is None

    def test_now_without_clock(self):
        result = evaluate({"fn": "now"}, _meta())
        assert result.value == ""

    def test_regex_invalid_pattern(self):
        result = evaluate({"fn": "regex", "args": [{"lit": "abc"}, {"lit": "["}]}, _meta())
        assert result.value is False

    def test_binop_type_mismatch_arithmetic(self):
        result = evaluate({"op": "+", "left": {"lit": 10}, "right": {"lit": "abc"}}, _meta())
        assert result.value == 10

    @pytest.mark.parametrize(
        ("op", "left", "right", "expected"),
        [
            ("-", 10, "abc", 10),
            ("*", 10, "abc", 0),
            ("/", 10, "abc", None),
            ("%", 10, "abc", None),
            ("==", 10, "10", False),
            ("!=", 10, "10", True),
            ("and", 10, "abc", True),
            ("or", 0, "abc", True),
            ("matches", 10, r"^10$", True),
        ],
    )
    def test_binop_type_mismatch_coverage(self, op, left, right, expected):
        result = evaluate(
            {"op": op, "left": {"lit": left}, "right": {"lit": right}},
            _meta(),
        )
        assert result.value == expected

    @pytest.mark.parametrize("op", ["<", ">", "<=", ">="])
    def test_binop_type_mismatch_ordering_raises(self, op):
        with pytest.raises(TypeError):
            evaluate(
                {"op": op, "left": {"lit": 10}, "right": {"lit": "abc"}},
                _meta(),
            )


class TestMetaDiffEdgeCases:
    def test_kind_removed(self):
        old = DomainMeta(kinds=[KindDef(name="A"), KindDef(name="B")])
        new = DomainMeta(kinds=[KindDef(name="A")])
        res = diff_meta(old, new)
        assert res.has_breaking
        assert "Kind 'B' removed" in res.breaking

    def test_allowed_type_removed_from_kind(self):
        old = DomainMeta(kinds=[KindDef(name="A", allowed_types=["string", "int"])])
        new = DomainMeta(kinds=[KindDef(name="A", allowed_types=["string"])])
        res = diff_meta(old, new)
        assert res.has_breaking
        assert "Kind 'A': allowed type 'int' removed" in res.breaking

    def test_function_signature_changed_args(self):
        old = DomainMeta(allowed_functions=[FunctionDef(name="f", args=["int"], returns="int")])
        new = DomainMeta(allowed_functions=[FunctionDef(name="f", args=["string"], returns="int")])
        res = diff_meta(old, new)
        assert res.has_breaking
        assert "Function 'f': args changed" in res.breaking[0]

    def test_function_signature_changed_returns(self):
        old = DomainMeta(allowed_functions=[FunctionDef(name="f", args=["int"], returns="int")])
        new = DomainMeta(allowed_functions=[FunctionDef(name="f", args=["int"], returns="string")])
        res = diff_meta(old, new)
        assert res.has_breaking
        assert "Function 'f': return type changed" in res.breaking[0]

    def test_kind_added_non_breaking(self):
        old = DomainMeta(kinds=[KindDef(name="A")])
        new = DomainMeta(kinds=[KindDef(name="A"), KindDef(name="B")])
        res = diff_meta(old, new)
        assert not res.has_breaking
        assert "Kind 'B' added" in res.non_breaking

    def test_optional_function_added_non_breaking(self):
        old = DomainMeta(
            allowed_functions=[FunctionDef(name="requiredFn", args=["string"], returns="bool")]
        )
        new = DomainMeta(
            allowed_functions=[
                FunctionDef(name="requiredFn", args=["string"], returns="bool"),
                FunctionDef(name="optionalFn", args=["string"], returns="string"),
            ]
        )
        res = diff_meta(old, new)
        assert not res.has_breaking
        assert "Function 'optionalFn' added" in res.non_breaking


def _ast(*defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="test",
        name="test",
        manifest_version="1.0.0",
        defs=list(defs),
    )


class TestValidatorEdgeCases:
    def test_complex_import_cycle(self):
        ast = _ast(
            ASTNode(kind="Policy", id="A", properties={"imports": ["B"]}),
            ASTNode(kind="Policy", id="B", properties={"imports": ["C"]}),
            ASTNode(kind="Policy", id="C", properties={"imports": ["A"]}),
        )
        errors = validate_semantic(ast)
        cycle_errors = [e for e in errors if e.code == "E_VALID_CYCLE_DETECTED"]
        assert len(cycle_errors) >= 1

    def test_cross_kind_namespace_conflict(self):
        ast = _ast(
            ASTNode(kind="Entity", id="User"),
            ASTNode(kind="Workflow", id="User"),
        )
        errors = validate_semantic(ast)
        ns_errors = [e for e in errors if e.code == "E_VALID_NAMESPACE_CONFLICT"]
        assert len(ns_errors) == 1
        assert "User" in ns_errors[0].message

    def test_invalid_function_reference_in_policy_expression(self):
        ast = _ast(
            ASTNode(
                kind="Policy",
                id="P1",
                properties={"expr": "unknownFunc(user.id)"},
            )
        )
        meta = DomainMeta(
            kinds=[KindDef(name="Policy", required_props=["expr"])],
            allowed_functions=[FunctionDef(name="knownFunc", args=["string"], returns="bool")],
        )

        errors = validate_structural(ast, meta)
        fn_errors = [e for e in errors if e.code == "E_META_FUNCTION_NOT_ALLOWED"]
        assert len(fn_errors) == 1
        assert "unknownFunc" in fn_errors[0].message

    def test_nested_invalid_function_reference_in_policy_expression(self):
        ast = _ast(
            ASTNode(
                kind="Policy",
                id="P2",
                properties={"rules": [{"when": "isVip(user) and fooBar(amount)"}]},
            )
        )
        meta = DomainMeta(
            kinds=[KindDef(name="Policy")],
            allowed_functions=[FunctionDef(name="isVip", args=["string"], returns="bool")],
        )

        errors = validate_structural(ast, meta)
        fn_errors = [e for e in errors if e.code == "E_META_FUNCTION_NOT_ALLOWED"]
        assert len(fn_errors) == 1
        assert "fooBar" in fn_errors[0].message
