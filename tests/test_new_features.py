"""Tests for newly added features across multiple modules."""
import textwrap
import pytest

from mpc.parser import parse, parse_dsl
from mpc.contracts.models import Actor
from mpc.contracts.serialization import from_dict
from mpc.meta import DomainMeta, FunctionDef, diff_meta
from mpc.conformance.runner import ConformanceRunner, _check_canonicalizable


class TestDslNestedDefinitions:
    def test_nested_def(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "ns"
            @name "n"
            @version "1.0.0"

            def Policy p1 "PolicyOne" {
                effect: "allow"
                def Condition c1 {
                    expr: "role == 'admin'"
                }
            }
        """)
        ast = parse_dsl(dsl)
        assert len(ast.defs) == 1
        parent = ast.defs[0]
        assert parent.kind == "Policy"
        assert len(parent.children) == 1
        child = parent.children[0]
        assert child.kind == "Condition"
        assert child.id == "c1"
        assert child.properties["expr"] == "role == 'admin'"

    def test_multiple_nested_defs(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "ns"
            @name "n"
            @version "1.0.0"

            def Policy p1 {
                effect: "allow"
                def Condition c1 { type: "role" }
                def Condition c2 { type: "time" }
            }
        """)
        ast = parse_dsl(dsl)
        assert len(ast.defs[0].children) == 2


class TestDslQuotedPropertyKeys:
    def test_quoted_key(self):
        dsl = textwrap.dedent("""\
            @schema 1
            @namespace "ns"
            @name "n"
            @version "1.0.0"

            def Config c1 {
                "$ref": "schema://base"
                "user.name": "admin"
                "@type": "special"
            }
        """)
        ast = parse_dsl(dsl)
        props = ast.defs[0].properties
        assert props["$ref"] == "schema://base"
        assert props["user.name"] == "admin"
        assert props["@type"] == "special"


class TestFromDictStrictMode:
    def test_strict_rejects_unknown_key(self):
        with pytest.raises(ValueError, match="Unknown key"):
            from_dict(Actor, {"id": "1", "type": "user", "bogus": "bad"}, strict=True)

    def test_non_strict_ignores_unknown_key(self):
        actor = from_dict(Actor, {"id": "1", "type": "user", "bogus": "bad"})
        assert actor.id == "1"


class TestMetaDiffFunctionSignature:
    def test_args_change_is_breaking(self):
        old = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="int")]
        )
        new = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["list"], returns="int")]
        )
        result = diff_meta(old, new)
        assert result.has_breaking
        assert any("args changed" in b for b in result.breaking)

    def test_return_type_change_is_breaking(self):
        old = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="int")]
        )
        new = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="float")]
        )
        result = diff_meta(old, new)
        assert result.has_breaking
        assert any("return type" in b for b in result.breaking)

    def test_cost_change_is_breaking(self):
        old = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], cost=1)]
        )
        new = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], cost=5)]
        )
        result = diff_meta(old, new)
        assert result.has_breaking
        assert any("cost changed" in b for b in result.breaking)

    def test_same_signature_no_changes(self):
        meta = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="int", cost=1)]
        )
        result = diff_meta(meta, meta)
        assert not result.has_breaking


class TestCanonicalizeGuard:
    def test_nan_detected(self):
        err = _check_canonicalizable({"value": float("nan")})
        assert err is not None
        assert "Non-finite" in err

    def test_infinity_detected(self):
        err = _check_canonicalizable({"value": float("inf")})
        assert err is not None

    def test_normal_passes(self):
        err = _check_canonicalizable({"value": 42, "items": [1, 2, "three"]})
        assert err is None


class TestRunCategory:
    def test_run_category_returns_results(self, tmp_path):
        fixtures = tmp_path / "fixtures"
        contracts = fixtures / "contracts" / "event_test"
        contracts.mkdir(parents=True)
        import json
        (contracts / "input.json").write_text(json.dumps({}))
        (contracts / "expected.json").write_text(json.dumps({"valid": True}))
        (contracts / "meta.json").write_text(json.dumps({"preset": "p"}))

        presets = tmp_path / "presets"
        presets.mkdir()
        (presets / "p.json").write_text(json.dumps({"defaultLimits": {}}))

        schemas = tmp_path / "schemas"
        schemas.mkdir()

        runner = ConformanceRunner(fixtures, presets_root=presets, schemas_root=schemas)
        results = runner.run_category("contracts")
        assert len(results) == 1

    def test_run_category_empty(self, tmp_path):
        fixtures = tmp_path / "fixtures"
        fixtures.mkdir()
        runner = ConformanceRunner(fixtures)
        results = runner.run_category("nonexistent")
        assert results == []


class TestConformanceCLI:
    def test_no_command_returns_1(self):
        from mpc.conformance.__main__ import main
        assert main([]) == 1

    def test_run_all_pass_returns_0(self, tmp_path):
        import json
        from mpc.conformance.__main__ import main
        fixtures = tmp_path / "fixtures"
        fx = fixtures / "compose" / "01_all_allow"
        fx.mkdir(parents=True)
        (fx / "meta.json").write_text(json.dumps({"preset": "preset-generic-full"}))
        (fx / "input.json").write_text(json.dumps({
            "decisions": [{"allow": True, "reasons": [{"code": "R_POLICY_ALLOW"}]}],
            "strategy": "deny-wins",
        }))
        (fx / "expected.json").write_text(json.dumps({
            "allow": True,
            "reasons": [{"code": "R_POLICY_ALLOW"}],
        }))
        presets = tmp_path / "presets"
        presets.mkdir()
        (presets / "preset-generic-full.json").write_text(json.dumps({"defaultLimits": {}}))
        rc = main(["run", str(fixtures), "--presets", str(presets)])
        assert rc == 0

    def test_run_category_returns_0(self, tmp_path):
        import json
        from mpc.conformance.__main__ import main
        fixtures = tmp_path / "fixtures"
        fx = fixtures / "compose" / "01_all_allow"
        fx.mkdir(parents=True)
        (fx / "meta.json").write_text(json.dumps({"preset": "preset-generic-full"}))
        (fx / "input.json").write_text(json.dumps({
            "decisions": [{"allow": True, "reasons": [{"code": "R_POLICY_ALLOW"}]}],
            "strategy": "deny-wins",
        }))
        (fx / "expected.json").write_text(json.dumps({
            "allow": True,
            "reasons": [{"code": "R_POLICY_ALLOW"}],
        }))
        presets = tmp_path / "presets"
        presets.mkdir()
        (presets / "preset-generic-full.json").write_text(json.dumps({"defaultLimits": {}}))
        rc = main(["run", str(fixtures), "--presets", str(presets), "--category", "compose"])
        assert rc == 0
