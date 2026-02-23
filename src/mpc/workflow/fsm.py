"""Finite State Machine engine for workflow definitions.

Per MASTER_SPEC section 12:
  - Pure FSM: states, transitions, guards
  - Auth checks via AuthPort (optional)
  - Guard checks via GuardPort (optional)
  - Outputs Decision + Intent + Trace
  - Deterministic — same input always produces same output
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from mpc.ast.models import ASTNode
from mpc.contracts.models import Decision, Error, Intent, Reason


# ---------------------------------------------------------------------------
# Port interfaces for consuming apps
# ---------------------------------------------------------------------------

@runtime_checkable
class GuardPort(Protocol):
    """Interface for external guard logic.

    Consuming apps implement this to add custom pre-conditions
    beyond what expressions can evaluate.
    """
    def check(self, transition: str, context: dict[str, Any]) -> bool: ...


@runtime_checkable
class AuthPort(Protocol):
    """Interface for external authorization delegation.

    Consuming apps implement this to check actor permissions
    against an external identity/authorization system.
    """
    def authorize(self, actor_id: str, transition: str) -> bool: ...


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

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
    on_enter: list[str] = field(default_factory=list)
    on_leave: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FireResult:
    """Result of firing a transition."""
    new_state: str
    decision: Decision
    errors: list[Error] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class WorkflowEngine:
    """Execute workflow definitions as finite state machines."""

    states: dict[str, FSMState] = field(default_factory=dict)
    transitions: list[Transition] = field(default_factory=list)
    current_state: str = ""
    initial_state: str = ""
    guard_port: GuardPort | None = None
    auth_port: AuthPort | None = None

    @classmethod
    def from_ast_node(
        cls,
        node: ASTNode,
        *,
        guard_port: GuardPort | None = None,
        auth_port: AuthPort | None = None,
    ) -> WorkflowEngine:
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
                on_enter = tr.get("on_enter") or tr.get("onEnter") or []
                on_leave = tr.get("on_leave") or tr.get("onLeave") or []
                if isinstance(on_enter, str):
                    on_enter = [on_enter]
                if isinstance(on_leave, str):
                    on_leave = [on_leave]
                transitions.append(Transition(
                    from_state=str(tr.get("from", "")),
                    to_state=str(tr.get("to", "")),
                    on=str(tr.get("on", tr.get("to", ""))),
                    guard=tr.get("guard"),
                    auth_roles=tr.get("authRoles", tr.get("auth_roles", [])),
                    on_enter=list(on_enter),
                    on_leave=list(on_leave),
                ))

        return cls(
            states=states,
            transitions=transitions,
            current_state=initial,
            initial_state=initial,
            guard_port=guard_port,
            auth_port=auth_port,
        )

    def get_initial_state(self) -> str:
        """Return the initial state of the workflow."""
        return self.initial_state

    def is_valid_transition(self, from_state: str, to_state: str) -> bool:
        """Check if a direct transition from from_state to to_state is allowed."""
        return any(
            t.from_state == from_state and t.to_state == to_state
            for t in self.transitions
        )

    def get_transition_actions(
        self, from_state: str, to_state: str
    ) -> dict[str, list[str]]:
        """Get on_leave and on_enter action names for the transition."""
        for t in self.transitions:
            if t.from_state == from_state and t.to_state == to_state:
                return {"on_leave": list(t.on_leave), "on_enter": list(t.on_enter)}
        return {"on_leave": [], "on_enter": []}

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
        actor_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> FireResult:
        """Attempt to fire *event* and return a FireResult with Decision."""
        reasons: list[Reason] = []
        errors: list[Error] = []
        ctx = context or {}

        for tr in self.transitions:
            if tr.from_state != self.current_state or tr.on != event:
                continue

            # AuthPort check
            if self.auth_port is not None and actor_id is not None:
                if not self.auth_port.authorize(actor_id, tr.on):
                    reasons.append(Reason(code="R_WF_AUTH_DENIED",
                                          summary=f"Auth denied for '{event}'"))
                    return FireResult(
                        new_state=self.current_state,
                        decision=Decision(allow=False, reasons=reasons),
                        errors=errors,
                    )

            # Role-based check (built-in RBAC)
            if tr.auth_roles and actor_roles is not None:
                if not set(tr.auth_roles) & set(actor_roles):
                    reasons.append(Reason(code="R_WF_AUTH_DENIED",
                                          summary=f"Actor lacks required roles for '{event}'"))
                    errors.append(Error(
                        code="E_WF_UNKNOWN_TRANSITION",
                        message=f"Actor lacks required roles for '{event}'",
                        severity="error",
                    ))
                    continue

            # GuardPort check
            if tr.guard and self.guard_port is not None:
                if not self.guard_port.check(tr.on, ctx):
                    reasons.append(Reason(code="R_WF_GUARD_FAIL",
                                          summary=f"Guard failed for '{event}'"))
                    return FireResult(
                        new_state=self.current_state,
                        decision=Decision(allow=False, reasons=reasons),
                        errors=errors,
                    )
                reasons.append(Reason(code="R_WF_GUARD_PASS",
                                      summary=f"Guard passed for '{event}'"))

            # Transition succeeds
            self.current_state = tr.to_state
            return FireResult(
                new_state=self.current_state,
                decision=Decision(allow=True, reasons=reasons),
                errors=errors,
            )

        errors.append(Error(
            code="E_WF_UNKNOWN_TRANSITION",
            message=f"No valid transition for event '{event}' from state '{self.current_state}'",
            severity="error",
        ))
        return FireResult(
            new_state=self.current_state,
            decision=Decision(allow=False, reasons=reasons),
            errors=errors,
        )
