"""Finite State Machine engine for workflow definitions.

Per MASTER_SPEC section 12:
  - Pure FSM: states, transitions, guards
  - Auth checks on transitions
  - Deterministic — same input always produces same output
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.ast.models import ASTNode
from mpc.contracts.models import Error


@dataclass(frozen=True)
class FSMState:
    name: str
    is_initial: bool = False
    is_final: bool = False


@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    on: str
    guard: str | None = None
    auth_roles: list[str] = field(default_factory=list)


@dataclass
class WorkflowEngine:
    """Execute workflow definitions as finite state machines."""

    states: dict[str, FSMState] = field(default_factory=dict)
    transitions: list[Transition] = field(default_factory=list)
    current_state: str = ""

    @classmethod
    def from_ast_node(cls, node: ASTNode) -> WorkflowEngine:
        """Build a WorkflowEngine from a workflow ASTNode."""
        state_names = node.properties.get("states", [])
        initial = node.properties.get("initial", state_names[0] if state_names else "")
        finals = set(node.properties.get("finals", []))

        states: dict[str, FSMState] = {}
        for s in state_names:
            if isinstance(s, str):
                states[s] = FSMState(
                    name=s,
                    is_initial=(s == initial),
                    is_final=(s in finals),
                )

        transitions: list[Transition] = []
        for tr in node.properties.get("transitions", []):
            if isinstance(tr, dict):
                transitions.append(Transition(
                    from_state=str(tr.get("from", "")),
                    to_state=str(tr.get("to", "")),
                    on=str(tr.get("on", "")),
                    guard=tr.get("guard"),
                    auth_roles=tr.get("authRoles", []),
                ))

        return cls(
            states=states,
            transitions=transitions,
            current_state=initial,
        )

    def validate(self) -> list[Error]:
        """Validate the workflow structure."""
        errors: list[Error] = []
        if not self.current_state:
            errors.append(Error(
                code="E_WF_NO_INITIAL",
                message="Workflow has no initial state",
                severity="error",
            ))
        for tr in self.transitions:
            if tr.from_state not in self.states:
                errors.append(Error(
                    code="E_WF_UNKNOWN_STATE",
                    message=f"Transition references unknown state '{tr.from_state}'",
                    severity="error",
                ))
            if tr.to_state not in self.states:
                errors.append(Error(
                    code="E_WF_UNKNOWN_STATE",
                    message=f"Transition references unknown state '{tr.to_state}'",
                    severity="error",
                ))
        return errors

    def available_transitions(
        self, *, actor_roles: list[str] | None = None
    ) -> list[Transition]:
        """Return transitions available from the current state."""
        result: list[Transition] = []
        for tr in self.transitions:
            if tr.from_state != self.current_state:
                continue
            if tr.auth_roles and actor_roles is not None:
                if not set(tr.auth_roles) & set(actor_roles):
                    continue
            result.append(tr)
        return result

    def fire(
        self,
        event: str,
        *,
        actor_roles: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[str, list[Error]]:
        """Attempt to fire *event* and return (new_state, errors)."""
        errors: list[Error] = []
        for tr in self.transitions:
            if tr.from_state != self.current_state or tr.on != event:
                continue
            if tr.auth_roles and actor_roles is not None:
                if not set(tr.auth_roles) & set(actor_roles):
                    errors.append(Error(
                        code="E_WF_UNKNOWN_TRANSITION",
                        message=f"Actor lacks required roles for '{event}'",
                        severity="error",
                    ))
                    continue
            self.current_state = tr.to_state
            return self.current_state, errors

        errors.append(Error(
            code="E_WF_UNKNOWN_TRANSITION",
            message=f"No valid transition for event '{event}' from state '{self.current_state}'",
            severity="error",
        ))
        return self.current_state, errors
