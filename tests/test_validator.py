from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.meta.models import DomainMeta, KindDef, FunctionDef
from mpc.tooling.validator.structural import validate_structural
from mpc.tooling.validator.semantic import validate_semantic


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

    def test_array_type_checked(self):
        meta = DomainMeta(
            kinds=[KindDef(name="Policy", allowed_types=["string", "bool"])]
        )
        ast = _ast(
            ASTNode(kind="Policy", id="p1", properties={"tags": ["a", "b"]})
        )
        errors = validate_structural(ast, meta)
        assert len(errors) == 1
        assert errors[0].code == "E_META_TYPE_NOT_ALLOWED"
        assert "array" in errors[0].message

    def test_object_type_checked(self):
        meta = DomainMeta(
            kinds=[KindDef(name="Policy", allowed_types=["string"])]
        )
        ast = _ast(
            ASTNode(kind="Policy", id="p1", properties={"match": {"kind": "x"}})
        )
        errors = validate_structural(ast, meta)
        assert len(errors) == 1
        assert errors[0].code == "E_META_TYPE_NOT_ALLOWED"
        assert "object" in errors[0].message

    def test_array_and_object_allowed(self):
        meta = DomainMeta(
            kinds=[KindDef(name="Policy", allowed_types=["string", "array", "object"])]
        )
        ast = _ast(
            ASTNode(kind="Policy", id="p1", properties={
                "tags": ["a"],
                "match": {"kind": "x"},
                "effect": "allow",
            })
        )
        errors = validate_structural(ast, meta)
        assert errors == []

    def test_function_not_allowed(self):
        meta = DomainMeta(
            kinds=[KindDef(name="Policy")],
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="int")],
        )
        ast = _ast(
            ASTNode(kind="Policy", id="p1", properties={
                "condition": "unknown_fn(x)"
            })
        )
        errors = validate_structural(ast, meta)
        assert len(errors) == 1
        assert errors[0].code == "E_META_FUNCTION_NOT_ALLOWED"
        assert "unknown_fn" in errors[0].message

    def test_known_function_allowed(self):
        meta = DomainMeta(
            kinds=[KindDef(name="Policy")],
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="int")],
        )
        ast = _ast(
            ASTNode(kind="Policy", id="p1", properties={
                "condition": "len(name) > 0"
            })
        )
        errors = validate_structural(ast, meta)
        assert errors == []


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
        dup_errors = [e for e in errors if e.code == "E_VALID_DUPLICATE_DEF"]
        assert len(dup_errors) == 1

    def test_namespace_conflict(self):
        ast = _ast(
            ASTNode(kind="Policy", id="shared_id"),
            ASTNode(kind="Workflow", id="shared_id"),
        )
        errors = validate_semantic(ast)
        ns_errors = [e for e in errors if e.code == "E_VALID_NAMESPACE_CONFLICT"]
        assert len(ns_errors) == 1
        assert "Policy" in ns_errors[0].message
        assert "Workflow" in ns_errors[0].message

    def test_unresolved_workflow_ref(self):
        ast = _ast(
            ASTNode(
                kind="Workflow",
                id="wf1",
                properties={
                    "initial": "draft",
                    "states": ["draft", "published"],
                    "transitions": [
                        {"from": "draft", "on": "go", "to": "nonexistent"},
                    ],
                },
            )
        )
        errors = validate_semantic(ast)
        ref_errors = [e for e in errors if e.code == "E_VALID_UNRESOLVED_REF"]
        assert len(ref_errors) == 1
        assert "nonexistent" in ref_errors[0].message

    def test_workflow_no_initial(self):
        ast = _ast(
            ASTNode(
                kind="Workflow",
                id="wf1",
                properties={
                    "states": ["draft", "published"],
                    "transitions": [
                        {"from": "draft", "on": "go", "to": "published"},
                    ],
                },
            )
        )
        errors = validate_semantic(ast)
        no_init = [e for e in errors if e.code == "E_WF_NO_INITIAL"]
        assert len(no_init) == 1

    def test_workflow_unreachable_state(self):
        ast = _ast(
            ASTNode(
                kind="Workflow",
                id="wf1",
                properties={
                    "initial": "draft",
                    "states": ["draft", "published", "orphan"],
                    "transitions": [
                        {"from": "draft", "on": "go", "to": "published"},
                    ],
                },
            )
        )
        errors = validate_semantic(ast)
        unreach = [e for e in errors if e.code == "E_VALID_INVALID_WORKFLOW"]
        assert len(unreach) == 1
        assert "orphan" in unreach[0].message

    def test_cycle_detection(self):
        ast = _ast(
            ASTNode(kind="Policy", id="a", properties={"extends": "b"}),
            ASTNode(kind="Policy", id="b", properties={"extends": "a"}),
        )
        errors = validate_semantic(ast)
        cycle_errors = [e for e in errors if e.code == "E_VALID_CYCLE_DETECTED"]
        assert len(cycle_errors) == 1

    def test_cycle_detection_no_duplicate_reports(self):
        ast = _ast(
            ASTNode(kind="Policy", id="a", properties={"extends": "b"}),
            ASTNode(kind="Policy", id="b", properties={"extends": "c"}),
            ASTNode(kind="Policy", id="c", properties={"extends": "a"}),
        )
        errors = validate_semantic(ast)
        cycle_errors = [e for e in errors if e.code == "E_VALID_CYCLE_DETECTED"]
        assert len(cycle_errors) == 1

    def test_cycle_detection_includes_source_map(self):
        from mpc.kernel.contracts.models import SourceMap
        src = SourceMap(line=5, col=1)
        ast = _ast(
            ASTNode(kind="Policy", id="a", properties={"extends": "b"}, source=src),
            ASTNode(kind="Policy", id="b", properties={"extends": "a"}),
        )
        errors = validate_semantic(ast)
        cycle_errors = [e for e in errors if e.code == "E_VALID_CYCLE_DETECTED"]
        assert len(cycle_errors) == 1
        assert cycle_errors[0].source is not None

    def test_import_cycle_detected(self):
        ast = _ast(
            ASTNode(kind="Policy", id="a", properties={"imports": ["b"]}),
            ASTNode(kind="Policy", id="b", properties={"imports": ["a"]}),
        )
        errors = validate_semantic(ast)
        cycle_errors = [e for e in errors if e.code == "E_VALID_CYCLE_DETECTED"]
        assert len(cycle_errors) >= 1

    def test_workflow_self_loop(self):
        ast = _ast(
            ASTNode(
                kind="Workflow",
                id="wf1",
                properties={
                    "initial": "draft",
                    "states": ["draft"],
                    "transitions": [
                        {"from": "draft", "on": "retry", "to": "draft"},
                    ],
                },
            )
        )
        errors = validate_semantic(ast)
        loop_errors = [e for e in errors if "self-loop" in (e.message or "").lower()]
        assert len(loop_errors) == 1

    def test_valid_workflow(self):
        ast = _ast(
            ASTNode(
                kind="Workflow",
                id="wf1",
                properties={
                    "initial": "draft",
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
