"""Tests for the overlay engine."""
from mpc.ast import ASTNode, ManifestAST
from mpc.overlay import OverlayEngine


def _base() -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="test",
        name="base",
        manifest_version="1.0.0",
        defs=[
            ASTNode(kind="Policy", id="p1", properties={"effect": "allow", "priority": 5}),
            ASTNode(kind="Policy", id="p2", properties={"effect": "deny", "priority": 10}),
        ],
    )


def _overlay(*defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="test",
        name="overlay",
        manifest_version="1.0.0",
        defs=list(defs),
    )


class TestOverlayEngine:
    def test_merge_op(self):
        engine = OverlayEngine(base=_base())
        result = engine.apply(_overlay(
            ASTNode(kind="Overlay", id="o1", properties={
                "target": "p1",
                "op": "merge",
                "values": {"priority": 20},
            })
        ))
        p1 = next(d for d in result.ast.defs if d.id == "p1")
        assert p1.properties["priority"] == 20
        assert p1.properties["effect"] == "allow"
        assert "merge:p1" in result.applied

    def test_replace_op(self):
        engine = OverlayEngine(base=_base())
        result = engine.apply(_overlay(
            ASTNode(kind="Overlay", id="o1", properties={
                "target": "p1",
                "op": "replace",
                "values": {"effect": "deny"},
            })
        ))
        p1 = next(d for d in result.ast.defs if d.id == "p1")
        assert p1.properties == {"effect": "deny"}
        assert "replace:p1" in result.applied

    def test_remove_op(self):
        engine = OverlayEngine(base=_base())
        result = engine.apply(_overlay(
            ASTNode(kind="Overlay", id="o1", properties={
                "target": "p2",
                "op": "remove",
            })
        ))
        ids = [d.id for d in result.ast.defs]
        assert "p2" not in ids
        assert "p1" in ids
        assert "remove:p2" in result.applied

    def test_unknown_target(self):
        engine = OverlayEngine(base=_base())
        result = engine.apply(_overlay(
            ASTNode(kind="Overlay", id="o1", properties={
                "target": "nonexistent",
                "op": "merge",
                "values": {"x": 1},
            })
        ))
        assert len(result.conflicts) == 1
        assert result.conflicts[0].code == "E_OVERLAY_UNKNOWN_SELECTOR"

    def test_invalid_op(self):
        engine = OverlayEngine(base=_base())
        result = engine.apply(_overlay(
            ASTNode(kind="Overlay", id="o1", properties={
                "target": "p1",
                "op": "explode",
            })
        ))
        assert len(result.conflicts) == 1
        assert result.conflicts[0].code == "E_OVERLAY_INVALID_OP"

    def test_no_target(self):
        engine = OverlayEngine(base=_base())
        result = engine.apply(_overlay(
            ASTNode(kind="Overlay", id="o1", properties={
                "op": "merge",
            })
        ))
        assert len(result.conflicts) == 1
        assert result.conflicts[0].code == "E_OVERLAY_UNKNOWN_SELECTOR"
