"""Tests for the ACL engine."""
from mpc.ast import ASTNode, ManifestAST
from mpc.acl import ACLEngine


def _manifest(*defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="test",
        name="acl",
        manifest_version="1.0.0",
        defs=list(defs),
    )


class TestACLEngine:
    def test_allow_by_role(self):
        ast = _manifest(
            ASTNode(kind="ACL", id="r1", properties={
                "action": "read",
                "resource": "document",
                "roles": ["viewer", "editor"],
                "effect": "allow",
            })
        )
        engine = ACLEngine(ast=ast)
        result = engine.check("read", "document", actor_roles=["viewer"])
        assert result.allowed is True
        assert any(r.code == "R_ACL_ALLOW_ROLE" for r in result.reasons)

    def test_deny_missing_role(self):
        ast = _manifest(
            ASTNode(kind="ACL", id="r1", properties={
                "action": "write",
                "resource": "document",
                "roles": ["editor"],
                "effect": "allow",
            })
        )
        engine = ACLEngine(ast=ast)
        result = engine.check("write", "document", actor_roles=["viewer"])
        assert result.allowed is False

    def test_deny_by_explicit_rule(self):
        ast = _manifest(
            ASTNode(kind="ACL", id="r1", properties={
                "action": "delete",
                "resource": "*",
                "roles": ["intern"],
                "effect": "deny",
                "priority": 10,
            }),
            ASTNode(kind="ACL", id="r2", properties={
                "action": "*",
                "resource": "*",
                "roles": ["intern"],
                "effect": "allow",
            }),
        )
        engine = ACLEngine(ast=ast)
        result = engine.check("delete", "anything", actor_roles=["intern"])
        assert result.allowed is False
        assert any(r.code == "R_ACL_DENY_ROLE" for r in result.reasons)

    def test_abac_condition(self):
        ast = _manifest(
            ASTNode(kind="ACL", id="r1", properties={
                "action": "read",
                "resource": "classified",
                "condition": {"clearance": "top-secret"},
                "effect": "allow",
            })
        )
        engine = ACLEngine(ast=ast)
        result = engine.check(
            "read", "classified",
            actor_attrs={"clearance": "top-secret"},
        )
        assert result.allowed is True
        assert any(r.code == "R_ACL_ALLOW_ABAC" for r in result.reasons)

    def test_no_matching_rule(self):
        ast = _manifest()
        engine = ACLEngine(ast=ast)
        result = engine.check("read", "doc", actor_roles=["user"])
        assert result.allowed is False
