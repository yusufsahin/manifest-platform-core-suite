"""Tests for ACL engine (D4) — RBAC, ABAC, maskField intents, role hierarchy."""
import pytest

from mpc.ast.models import ASTNode, ManifestAST
from mpc.acl import ACLEngine, ACLResult


def _acl_ast(*rules: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="acme",
        name="test",
        manifest_version="1.0",
        defs=list(rules),
    )


class TestACLEngine:
    def test_allow_by_role(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={"action": "read", "resource": "doc", "roles": ["viewer"]},
        )))
        result = acl.check("read", "doc", actor_roles=["viewer"])
        assert result.allowed is True
        assert any(r.code == "R_ACL_ALLOW_ROLE" for r in result.reasons)

    def test_deny_missing_role(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={"action": "read", "resource": "doc", "roles": ["admin"]},
        )))
        result = acl.check("read", "doc", actor_roles=["viewer"])
        assert result.allowed is False

    def test_deny_by_explicit_rule(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={
                "action": "delete", "resource": "doc",
                "roles": ["viewer"], "effect": "deny",
            },
        )))
        result = acl.check("delete", "doc", actor_roles=["viewer"])
        assert result.allowed is False
        assert any(r.code == "R_ACL_DENY_ROLE" for r in result.reasons)

    def test_abac_condition(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={
                "action": "read", "resource": "doc",
                "condition": {"department": "engineering"},
            },
        )))
        result = acl.check("read", "doc", actor_attrs={"department": "engineering"})
        assert result.allowed is True
        assert any(r.code == "R_ACL_ALLOW_ABAC" for r in result.reasons)

    def test_no_matching_rule(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={"action": "write", "resource": "log", "roles": ["admin"]},
        )))
        result = acl.check("read", "doc", actor_roles=["viewer"])
        assert result.allowed is False


class TestMaskFieldIntents:
    def test_mask_intents_returned(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={
                "action": "read", "resource": "user",
                "roles": ["viewer"],
                "maskFields": ["content.ssn", "content.salary"],
            },
        )))
        result = acl.check("read", "user", actor_roles=["viewer"])
        assert result.allowed is True
        assert len(result.intents) == 2
        targets = [i.target for i in result.intents]
        assert "content.salary" in targets
        assert "content.ssn" in targets

    def test_mask_intents_sorted_by_target(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={
                "action": "read", "resource": "user",
                "roles": ["viewer"],
                "maskFields": ["z.field", "a.field", "m.field"],
            },
        )))
        result = acl.check("read", "user", actor_roles=["viewer"])
        targets = [i.target for i in result.intents]
        assert targets == ["a.field", "m.field", "z.field"]

    def test_mask_intent_kind(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={
                "action": "read", "resource": "user",
                "roles": ["viewer"],
                "maskFields": ["user.ssn"],
            },
        )))
        result = acl.check("read", "user", actor_roles=["viewer"])
        assert result.intents[0].kind == "maskField"

    def test_no_mask_fields(self):
        acl = ACLEngine(ast=_acl_ast(ASTNode(
            kind="ACL", id="r1",
            properties={"action": "read", "resource": "doc", "roles": ["viewer"]},
        )))
        result = acl.check("read", "doc", actor_roles=["viewer"])
        assert result.intents == []


class TestRoleHierarchy:
    def test_admin_inherits_editor(self):
        acl = ACLEngine(
            ast=_acl_ast(ASTNode(
                kind="ACL", id="r1",
                properties={"action": "edit", "resource": "doc", "roles": ["editor"]},
            )),
            role_hierarchy={"admin": {"editor", "viewer"}},
        )
        result = acl.check("edit", "doc", actor_roles=["admin"])
        assert result.allowed is True

    def test_viewer_cannot_edit(self):
        acl = ACLEngine(
            ast=_acl_ast(ASTNode(
                kind="ACL", id="r1",
                properties={"action": "edit", "resource": "doc", "roles": ["editor"]},
            )),
            role_hierarchy={"admin": {"editor", "viewer"}},
        )
        result = acl.check("edit", "doc", actor_roles=["viewer"])
        assert result.allowed is False

    def test_transitive_hierarchy(self):
        acl = ACLEngine(
            ast=_acl_ast(ASTNode(
                kind="ACL", id="r1",
                properties={"action": "read", "resource": "doc", "roles": ["viewer"]},
            )),
            role_hierarchy={
                "super_admin": {"admin"},
                "admin": {"editor"},
                "editor": {"viewer"},
            },
        )
        result = acl.check("read", "doc", actor_roles=["super_admin"])
        assert result.allowed is True
