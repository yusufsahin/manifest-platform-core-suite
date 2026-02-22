from mpc.ast import ASTNode, ManifestAST
from mpc.meta import DomainMeta, KindDef
from mpc.validator import validate_structural, validate_semantic


def _ast(*defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="test",
        name="test",
        manifest_version="1.0.0",
        defs=list(defs),
    )


class TestStructuralValidator:
    def test_valid(self):
        meta = DomainMeta(
            kinds=[KindDef(name="Policy", required_props=["effect"])]
        )
        ast = _ast(ASTNode(kind="Policy", id="p1", properties={"effect": "allow"}))
        errors = validate_structural(ast, meta)
        assert errors == []

    def test_unknown_kind(self):
        meta = DomainMeta(kinds=[KindDef(name="Policy")])
        ast = _ast(ASTNode(kind="Unknown", id="x1"))
        errors = validate_structural(ast, meta)
        assert len(errors) == 1
        assert errors[0].code == "E_META_UNKNOWN_KIND"

    def test_missing_required_prop(self):
        meta = DomainMeta(
            kinds=[KindDef(name="Policy", required_props=["effect", "priority"])]
        )
        ast = _ast(ASTNode(kind="Policy", id="p1", properties={"effect": "allow"}))
        errors = validate_structural(ast, meta)
        assert len(errors) == 1
        assert errors[0].code == "E_META_MISSING_REQUIRED_FIELD"
        assert "priority" in errors[0].message

    def test_type_not_allowed(self):
        meta = DomainMeta(
            kinds=[KindDef(name="Policy", allowed_types=["string", "bool"])]
        )
        ast = _ast(
            ASTNode(kind="Policy", id="p1", properties={"priority": 10})
        )
        errors = validate_structural(ast, meta)
        assert len(errors) == 1
        assert errors[0].code == "E_META_TYPE_NOT_ALLOWED"


class TestSemanticValidator:
    def test_no_errors(self):
        ast = _ast(
            ASTNode(kind="Policy", id="p1"),
            ASTNode(kind="Policy", id="p2"),
        )
        errors = validate_semantic(ast)
        assert errors == []

    def test_duplicate_def(self):
        ast = _ast(
            ASTNode(kind="Policy", id="p1"),
            ASTNode(kind="Policy", id="p1"),
        )
        errors = validate_semantic(ast)
        assert len(errors) == 1
        assert errors[0].code == "E_VALID_DUPLICATE_DEF"

    def test_unresolved_workflow_ref(self):
        ast = _ast(
            ASTNode(
                kind="Workflow",
                id="wf1",
                properties={
                    "states": ["draft", "published"],
                    "transitions": [
                        {"from": "draft", "on": "go", "to": "nonexistent"},
                    ],
                },
            )
        )
        errors = validate_semantic(ast)
        assert len(errors) == 1
        assert errors[0].code == "E_VALID_UNRESOLVED_REF"
        assert "nonexistent" in errors[0].message

    def test_cycle_detection(self):
        ast = _ast(
            ASTNode(kind="Policy", id="a", properties={"extends": "b"}),
            ASTNode(kind="Policy", id="b", properties={"extends": "a"}),
        )
        errors = validate_semantic(ast)
        cycle_errors = [e for e in errors if e.code == "E_VALID_CYCLE_DETECTED"]
        assert len(cycle_errors) >= 1

    def test_valid_workflow(self):
        ast = _ast(
            ASTNode(
                kind="Workflow",
                id="wf1",
                properties={
                    "states": ["draft", "review", "published"],
                    "transitions": [
                        {"from": "draft", "on": "submit", "to": "review"},
                        {"from": "review", "on": "publish", "to": "published"},
                    ],
                },
            )
        )
        errors = validate_semantic(ast)
        assert errors == []
