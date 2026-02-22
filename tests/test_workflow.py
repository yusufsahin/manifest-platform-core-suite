"""Tests for the workflow/FSM engine."""
from mpc.ast import ASTNode
from mpc.workflow import WorkflowEngine, FSMState, Transition


def _workflow_node() -> ASTNode:
    return ASTNode(
        kind="Workflow",
        id="order_flow",
        properties={
            "initial": "draft",
            "finals": ["completed", "cancelled"],
            "states": ["draft", "review", "completed", "cancelled"],
            "transitions": [
                {"from": "draft", "on": "submit", "to": "review"},
                {"from": "review", "on": "approve", "to": "completed"},
                {"from": "review", "on": "reject", "to": "draft"},
                {"from": "draft", "on": "cancel", "to": "cancelled",
                 "authRoles": ["admin"]},
            ],
        },
    )


class TestWorkflowEngine:
    def test_from_ast_node(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        assert engine.current_state == "draft"
        assert len(engine.states) == 4
        assert engine.states["draft"].is_initial
        assert engine.states["completed"].is_final

    def test_validate_valid(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        errors = engine.validate()
        assert errors == []

    def test_validate_missing_initial(self):
        engine = WorkflowEngine(
            states={"a": FSMState(name="a")},
            transitions=[],
            current_state="",
        )
        errors = engine.validate()
        assert any(e.code == "E_WF_NO_INITIAL" for e in errors)

    def test_fire_transition(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        new_state, errors = engine.fire("submit")
        assert new_state == "review"
        assert errors == []

    def test_fire_chain(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        engine.fire("submit")
        new_state, errors = engine.fire("approve")
        assert new_state == "completed"
        assert errors == []

    def test_fire_invalid_event(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        new_state, errors = engine.fire("approve")
        assert new_state == "draft"
        assert any(e.code == "E_WF_UNKNOWN_TRANSITION" for e in errors)

    def test_fire_with_auth_roles(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        new_state, errors = engine.fire("cancel", actor_roles=["admin"])
        assert new_state == "cancelled"
        assert errors == []

    def test_fire_without_required_role(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        new_state, errors = engine.fire("cancel", actor_roles=["user"])
        assert new_state == "draft"
        assert len(errors) >= 1

    def test_available_transitions(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        available = engine.available_transitions()
        events = {t.on for t in available}
        assert "submit" in events
        assert "cancel" in events
