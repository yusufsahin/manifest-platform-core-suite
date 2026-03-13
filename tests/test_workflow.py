"""Tests for workflow engine (D1/D2) — FSM, GuardPort, AuthPort, Decision output."""
import pytest
from typing import Any

from mpc.kernel.ast.models import ASTNode
from mpc.features.workflow.fsm import WorkflowEngine, FSMState, Transition, FireResult, GuardPort, AuthPort


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
        # Fixture-style: no "initial" in definition → E_WF_NO_INITIAL
        engine = WorkflowEngine.from_fixture_input(
            {"states": ["a", "b"], "transitions": []},
        )
        errors = engine.validate()
        assert any(e.code == "E_WF_NO_INITIAL" for e in errors)
        assert any("declare an initial state" in e.message for e in errors)

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

    def test_auth_port_exception_converted(self):
        class BrokenAuth:
            def authorize(self, actor_id: str, transition: str) -> bool:
                raise RuntimeError("auth service unavailable")

        engine = WorkflowEngine.from_ast_node(
            _workflow_node(), auth_port=BrokenAuth()
        )
        result = engine.fire("submit", actor_id="user1")
        assert result.new_state == "draft"
        assert result.decision.allow is False
        assert any(e.code == "E_WF_AUTH_DENIED" for e in result.errors)


class TestGuardExceptions:
    def test_guard_exception_converted(self):
        class BrokenGuard:
            def check(self, trigger: str, context: dict[str, Any]) -> bool:
                raise ValueError("guard service down")

        engine = WorkflowEngine.from_ast_node(
            _workflow_node(), guard_port=BrokenGuard()
        )
        engine.fire("submit")
        result = engine.fire("expedite")
        assert result.new_state == "review"
        assert result.decision.allow is False
        assert any(e.code == "E_WF_GUARD_FAIL" for e in result.errors)


class TestWorkflowInspection:
    def test_is_valid_transition_true(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        assert engine.is_valid_transition("draft", "review") is True

    def test_is_valid_transition_false(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        assert engine.is_valid_transition("draft", "completed") is False

    def test_get_transition_actions_present(self):
        node = ASTNode(
            kind="Workflow", id="wf",
            properties={
                "initial": "a",
                "states": ["a", "b"],
                "transitions": [
                    {"from": "a", "on": "go", "to": "b",
                     "onEnter": ["logEntry"], "onLeave": ["cleanUp"]},
                ],
            },
        )
        engine = WorkflowEngine.from_ast_node(node)
        actions = engine.get_transition_actions("a", "b")
        assert actions["on_enter"] == ["logEntry"]
        assert actions["on_leave"] == ["cleanUp"]

    def test_get_transition_actions_absent(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        actions = engine.get_transition_actions("draft", "completed")
        assert actions == {"on_leave": [], "on_enter": []}

    def test_to_spec(self):
        from mpc.workflow.spec import WorkflowSpec
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        spec = engine.to_spec()
        assert isinstance(spec, WorkflowSpec)
        assert "draft" in spec.states
        assert spec.initial == "draft"
        assert "completed" in spec.finals
        assert len(spec.transitions) == 5

    def test_available_transitions_with_role_filter(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        available = engine.available_transitions(actor_roles=["admin"])
        events = {t.on for t in available}
        assert "submit" in events
        assert "cancel" in events

    def test_available_transitions_role_hides_restricted(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        available = engine.available_transitions(actor_roles=["viewer"])
        events = {t.on for t in available}
        assert "submit" in events
        assert "cancel" not in events

    def test_get_initial_state(self):
        engine = WorkflowEngine.from_ast_node(_workflow_node())
        assert engine.get_initial_state() == "draft"


class TestWorkflowValidation:
    def test_validate_unknown_from_state(self):
        engine = WorkflowEngine.from_fixture_input({
            "initial": "a",
            "states": ["a", "b"],
            "transitions": [
                {"from": "unknown_state", "on": "go", "to": "b"},
            ],
        })
        errors = engine.validate()
        assert any(e.code == "E_WF_UNKNOWN_STATE" for e in errors)
        assert any("unknown_state" in e.message for e in errors)

    def test_validate_unknown_to_state(self):
        engine = WorkflowEngine.from_fixture_input({
            "initial": "a",
            "states": ["a", "b"],
            "transitions": [
                {"from": "a", "on": "go", "to": "nonexistent"},
            ],
        })
        errors = engine.validate()
        assert any(e.code == "E_WF_UNKNOWN_STATE" for e in errors)
        assert any("nonexistent" in e.message for e in errors)
