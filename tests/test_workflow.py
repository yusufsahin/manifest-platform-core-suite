"""Tests for workflow engine (D1/D2) — FSM, GuardPort, AuthPort, Decision output."""
import pytest
from typing import Any

from mpc.ast.models import ASTNode
from mpc.workflow import WorkflowEngine, FSMState, Transition, FireResult, GuardPort, AuthPort


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
                {"from": "review", "on": "expedite", "to": "completed",
                 "guard": "ctx.urgent == true"},
            ],
        },
    )


class TestWorkflowEngine:
    def test_from_ast_node(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        assert engine.current_state == "draft"
        assert len(engine.states) == 4
        assert len(engine.transitions) == 5

    def test_validate_valid(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        errors = engine.validate()
        assert len(errors) == 0

    def test_validate_missing_initial(self):
        node = ASTNode(
            kind="Workflow", id="broken",
            properties={"states": ["a", "b"], "transitions": []},
        )
        engine = WorkflowEngine.from_ast_node(node)
        engine.current_state = ""
        errors = engine.validate()
        assert any(e.code == "E_WF_NO_INITIAL" for e in errors)

    def test_fire_transition(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        result = engine.fire("submit")
        assert isinstance(result, FireResult)
        assert result.new_state == "review"
        assert result.decision.allow is True
        assert engine.current_state == "review"

    def test_fire_chain(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        engine.fire("submit")
        result = engine.fire("approve")
        assert result.new_state == "completed"

    def test_fire_invalid_event(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        result = engine.fire("approve")
        assert result.new_state == "draft"
        assert result.decision.allow is False
        assert any(e.code == "E_WF_UNKNOWN_TRANSITION" for e in result.errors)

    def test_fire_with_auth_roles(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        result = engine.fire("cancel", actor_roles=["admin"])
        assert result.new_state == "cancelled"
        assert result.decision.allow is True

    def test_fire_without_required_role(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        result = engine.fire("cancel", actor_roles=["viewer"])
        assert result.new_state == "draft"
        assert any(
            r.code == "R_WF_AUTH_DENIED"
            for r in result.decision.reasons
        )

    def test_available_transitions(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        available = engine.available_transitions()
        events = [t.on for t in available]
        assert "submit" in events
        assert "cancel" in events


class TestGuardPort:
    def test_guard_passes(self):
        class PassGuard:
            def check(self, transition: str, context: dict[str, Any]) -> bool:
                return True

        engine = WorkflowEngine.from_ast_node(
            _workflow_node(), guard_port=PassGuard()
        )
        engine.fire("submit")
        result = engine.fire("expedite")
        assert result.new_state == "completed"
        assert result.decision.allow is True
        assert any(r.code == "R_WF_GUARD_PASS" for r in result.decision.reasons)

    def test_guard_fails(self):
        class FailGuard:
            def check(self, transition: str, context: dict[str, Any]) -> bool:
                return False

        engine = WorkflowEngine.from_ast_node(
            _workflow_node(), guard_port=FailGuard()
        )
        engine.fire("submit")
        result = engine.fire("expedite")
        assert result.new_state == "review"
        assert result.decision.allow is False
        assert any(r.code == "R_WF_GUARD_FAIL" for r in result.decision.reasons)


class TestAuthPort:
    def test_auth_port_allows(self):
        class AllowAuth:
            def authorize(self, actor_id: str, transition: str) -> bool:
                return True

        engine = WorkflowEngine.from_ast_node(
            _workflow_node(), auth_port=AllowAuth()
        )
        result = engine.fire("submit", actor_id="user1")
        assert result.new_state == "review"
        assert result.decision.allow is True

    def test_auth_port_denies(self):
        class DenyAuth:
            def authorize(self, actor_id: str, transition: str) -> bool:
                return False

        engine = WorkflowEngine.from_ast_node(
            _workflow_node(), auth_port=DenyAuth()
        )
        result = engine.fire("submit", actor_id="user1")
        assert result.new_state == "draft"
        assert result.decision.allow is False
        assert any(r.code == "R_WF_AUTH_DENIED" for r in result.decision.reasons)
