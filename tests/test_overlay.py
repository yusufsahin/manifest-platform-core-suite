"""Tests for overlay engine (E1/E2) — ops, stable selectors, conflict detection."""
import pytest

from mpc.ast.models import ASTNode, ManifestAST
from mpc.overlay import OverlayEngine, OverlayResult, Selector


def _base_ast(*defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1, namespace="acme", name="base",
        manifest_version="1.0", defs=list(defs),
    )


def _overlay_ast(*defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1, namespace="acme", name="overlay",
        manifest_version="1.0", defs=list(defs),
    )


class TestOverlayOps:
    def test_merge_op(self):
        base = _base_ast(ASTNode(kind="Policy", id="p1", properties={"effect": "allow", "ttl": 3600}))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"target": "p1", "op": "merge", "values": {"owner": "team-a", "ttl": 7200}},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        p1 = next(d for d in result.ast.defs if d.id == "p1")
        assert p1.properties["effect"] == "allow"
        assert p1.properties["owner"] == "team-a"
        assert p1.properties["ttl"] == 7200
        assert "merge:p1" in result.applied

    def test_replace_op(self):
        base = _base_ast(ASTNode(kind="Entity", id="e1", properties={"name": "old", "flag": True}))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"target": "e1", "op": "replace", "values": {"name": "new"}},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        e1 = next(d for d in result.ast.defs if d.id == "e1")
        assert e1.properties == {"name": "new"}
        assert "replace:e1" in result.applied

    def test_remove_op(self):
        base = _base_ast(
            ASTNode(kind="Entity", id="e1", properties={}),
            ASTNode(kind="Entity", id="e2", properties={}),
        )
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"target": "e1", "op": "remove"},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        ids = [d.id for d in result.ast.defs]
        assert "e1" not in ids
        assert "e2" in ids

    def test_append_list(self):
        base = _base_ast(ASTNode(kind="Entity", id="e1", properties={"tags": ["a", "b"]}))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"target": "e1", "op": "append", "values": {"tags": ["c"]}},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        e1 = next(d for d in result.ast.defs if d.id == "e1")
        assert e1.properties["tags"] == ["a", "b", "c"]

    def test_patch_op(self):
        base = _base_ast(ASTNode(kind="Policy", id="p1", properties={"effect": "allow", "priority": 10}))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"target": "p1", "op": "patch", "values": {"priority": 20}},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        p1 = next(d for d in result.ast.defs if d.id == "p1")
        assert p1.properties["priority"] == 20
        assert p1.properties["effect"] == "allow"

    def test_unknown_target(self):
        base = _base_ast(ASTNode(kind="Entity", id="e1", properties={}))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"target": "nonexistent", "op": "merge", "values": {}},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        assert any(e.code == "E_OVERLAY_UNKNOWN_SELECTOR" for e in result.conflicts)

    def test_invalid_op(self):
        base = _base_ast(ASTNode(kind="Entity", id="e1", properties={}))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"target": "e1", "op": "explode", "values": {}},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        assert any(e.code == "E_OVERLAY_INVALID_OP" for e in result.conflicts)

    def test_no_target(self):
        base = _base_ast(ASTNode(kind="Entity", id="e1", properties={}))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"op": "merge"},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        assert any(e.code == "E_OVERLAY_UNKNOWN_SELECTOR" for e in result.conflicts)

    def test_remove_op_path(self):
        base = _base_ast(ASTNode(
            kind="Policy", id="p1",
            properties={"attributes": {"effect": "allow", "ttl": 3600, "owner": "team-a"}},
        ))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={
                "selector": {"id": "p1", "kind": "Policy"},
                "op": "remove",
                "path": "attributes.owner",
            },
        ))
        result = OverlayEngine(base=base).apply(overlay)
        p1 = next(d for d in result.ast.defs if d.id == "p1")
        assert "owner" not in p1.properties["attributes"]
        assert p1.properties["attributes"]["effect"] == "allow"
        assert p1.properties["attributes"]["ttl"] == 3600

    def test_append_op_path(self):
        base = _base_ast(ASTNode(
            kind="Entity", id="e1",
            properties={"meta": {"tags": ["a", "b"]}},
        ))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={
                "target": "e1",
                "op": "append",
                "path": "meta.tags",
                "values": {"meta.tags": ["c"]},
            },
        ))
        result = OverlayEngine(base=base).apply(overlay)
        e1 = next(d for d in result.ast.defs if d.id == "e1")
        assert e1.properties["meta"]["tags"] == ["a", "b", "c"]

    def test_deep_merge(self):
        base = _base_ast(ASTNode(
            kind="Config", id="c1",
            properties={"settings": {"db": {"host": "localhost", "port": 5432}}},
        ))
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={"target": "c1", "op": "merge",
                         "values": {"settings": {"db": {"port": 5433, "ssl": True}}}},
        ))
        result = OverlayEngine(base=base).apply(overlay)
        c1 = next(d for d in result.ast.defs if d.id == "c1")
        db = c1.properties["settings"]["db"]
        assert db["host"] == "localhost"
        assert db["port"] == 5433
        assert db["ssl"] is True


class TestStableSelectors:
    def test_selector_by_kind_and_id(self):
        base = _base_ast(
            ASTNode(kind="Policy", id="p1", properties={"effect": "allow"}),
            ASTNode(kind="Entity", id="p1", properties={"name": "entity"}),
        )
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={
                "selector": {"kind": "Policy", "id": "p1"},
                "op": "merge",
                "values": {"priority": 10},
            },
        ))
        result = OverlayEngine(base=base).apply(overlay)
        policy_p1 = next(d for d in result.ast.defs if d.kind == "Policy" and d.id == "p1")
        entity_p1 = next(d for d in result.ast.defs if d.kind == "Entity" and d.id == "p1")
        assert policy_p1.properties.get("priority") == 10
        assert "priority" not in entity_p1.properties

    def test_selector_by_namespace(self):
        base = _base_ast(
            ASTNode(kind="Policy", id="p1", properties={"ns": "acme"}),
        )
        overlay = _overlay_ast(ASTNode(
            kind="Overlay", id="o1",
            properties={
                "selector": {"namespace": "acme", "id": "p1"},
                "op": "merge",
                "values": {"updated": True},
            },
        ))
        result = OverlayEngine(base=base).apply(overlay)
        p1 = next(d for d in result.ast.defs if d.id == "p1")
        assert p1.properties["updated"] is True

    def test_selector_object(self):
        sel = Selector(kind="Policy", namespace="acme", id="p1")
        node = ASTNode(kind="Policy", id="p1", properties={})
        assert sel.matches(node, "acme")
        assert not sel.matches(node, "other")


class TestConflictDetection:
    def test_conflicting_replace_ops(self):
        base = _base_ast(ASTNode(
            kind="Policy", id="p1",
            properties={"attributes": {"effect": "allow"}},
        ))
        overlay = _overlay_ast(
            ASTNode(kind="Overlay", id="o1", properties={
                "target": "p1", "op": "replace",
                "path": "attributes.effect", "value": "deny",
            }),
            ASTNode(kind="Overlay", id="o2", properties={
                "target": "p1", "op": "replace",
                "path": "attributes.effect", "value": "allow",
            }),
        )
        result = OverlayEngine(base=base).apply(overlay)
        assert any(
            e.code == "E_OVERLAY_CONFLICT" and "attributes.effect" in e.message
            for e in result.conflicts
        )
