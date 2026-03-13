"""Tests for the policy engine."""
from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.features.policy.engine import PolicyEngine


def _manifest(*defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="test",
        name="policies",
        manifest_version="1.0.0",
        defs=list(defs),
    )


def _meta() -> DomainMeta:
    return DomainMeta(kinds=[KindDef(name="Policy")])


class TestPolicyEngine:
    def test_allow_by_default(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={"effect": "allow"})
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read"})
        assert result.allow is True
        assert any(r.code == "R_POLICY_ALLOW" for r in result.reasons)

    def test_deny_effect(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={"effect": "deny"})
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read"})
        assert result.allow is False
        assert any(r.code == "R_POLICY_DENY" for r in result.reasons)

    def test_match_filter(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={
                "effect": "deny",
                "match": {"kind": "delete"},
            }),
            ASTNode(kind="Policy", id="p2", properties={
                "effect": "allow",
            }),
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read"})
        assert result.allow is True

        result2 = engine.evaluate({"kind": "delete"})
        assert result2.allow is False

    def test_priority_ordering(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={
                "effect": "allow", "priority": 5,
            }),
            ASTNode(kind="Policy", id="p2", properties={
                "effect": "deny", "priority": 10,
            }),
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read"})
        assert result.allow is False
        assert result.reasons[0].code == "R_POLICY_DENY"

    def test_intents_collected(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={
                "effect": "allow",
                "intents": [{"kind": "audit", "target": "user.ssn"}],
            })
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read"})
        assert len(result.intents) == 1
        assert result.intents[0].kind == "audit"

    def test_allow_without_intents(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={"effect": "allow"})
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read"})
        assert result.allow is True
        assert result.intents == []

    def test_no_matching_policy(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={
                "effect": "deny",
                "match": {"kind": "delete"},
            })
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read"})
        assert result.allow is True
        assert result.reasons == []

    def test_multiple_matching_policies_deny_wins(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={"effect": "allow"}),
            ASTNode(kind="Policy", id="p2", properties={"effect": "deny"}),
            ASTNode(kind="Policy", id="p3", properties={"effect": "allow"}),
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read"})
        assert result.allow is False
        deny_reasons = [r for r in result.reasons if r.code == "R_POLICY_DENY"]
        allow_reasons = [r for r in result.reasons if r.code == "R_POLICY_ALLOW"]
        assert len(deny_reasons) == 1
        assert len(allow_reasons) == 2

    def test_dotted_key_match(self):
        ast = _manifest(
            ASTNode(kind="Policy", id="p1", properties={
                "effect": "deny",
                "match": {"object.type": "secret"},
            })
        )
        engine = PolicyEngine(ast=ast, meta=_meta())
        result = engine.evaluate({"kind": "read", "object": {"type": "secret"}})
        assert result.allow is False

        result2 = engine.evaluate({"kind": "read", "object": {"type": "public"}})
        assert result2.allow is True
