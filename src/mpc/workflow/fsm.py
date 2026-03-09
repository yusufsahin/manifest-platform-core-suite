"""Finite State Machine engine for workflow definitions.

Per MASTER_SPEC section 12:
  - Pure FSM: states, transitions, guards
  - Auth checks via AuthPort (optional)
  - Guard checks via GuardPort (optional)
  - Outputs Decision (FireResult)
  - Deterministic — same input always produces same output
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from mpc.ast.models import ASTNode
from mpc.contracts.models import Decision, Error, Reason
from mpc.workflow.spec import TransitionSpec, WorkflowSpec


# ---------------------------------------------------------------------------
# Port interfaces for consuming apps
# ---------------------------------------------------------------------------

@runtime_checkable
class GuardPort(Protocol):
    """Interface for external guard logic.

    Consuming apps implement this to add custom pre-conditions
    beyond what expressions can evaluate.
    """
    def check(self, trigger: str, context: dict[str, Any]) -> bool: ...


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

    @staticmethod
    def _parse_transition(tr: dict[str, Any]) -> Transition:
        """Parse a transition dict (fixture or AST format) into Transition."""
        on_enter = tr.get("on_enter") or tr.get("onEnter") or []
        on_leave = tr.get("on_leave") or tr.get("onLeave") or []
        if isinstance(on_enter, str):
            on_enter = [on_enter]
        if isinstance(on_leave, str):
            on_leave = [on_leave]
        return Transition(
            from_state=str(tr.get("from", "")),
            to_state=str(tr.get("to", "")),
            on=str(tr.get("on", tr.get("to", ""))),
            guard=tr.get("guard"),
            auth_roles=tr.get("authRoles", tr.get("auth_roles", [])),
            on_enter=list(on_enter),
            on_leave=list(on_leave),
        )

    @classmethod
    def _build_from_data(
        cls,
        state_names: list[str],
        initial: str,
        finals: set[str],
        transitions_data: list[dict[str, Any]],
        current_state: str,
        *,
        guard_port: GuardPort | None = None,
        auth_port: AuthPort | None = None,
    ) -> WorkflowEngine:
        """Build WorkflowEngine from parsed state/transition data."""
        states: dict[str, FSMState] = {}
        for s in state_names:
            if isinstance(s, str):
                states[s] = FSMState(
                    name=s,
                    is_initial=(s == initial),
                    is_final=(s in finals),
                )
        transitions = [
            cls._parse_transition(tr)
            for tr in transitions_data
            if isinstance(tr, dict)
        ]
        return cls(
            states=states,
            transitions=transitions,
            current_state=current_state,
            initial_state=initial,
            guard_port=guard_port,
            auth_port=auth_port,
        )

    @classmethod
    def from_fixture_input(
        cls,
        data: dict[str, Any],
        *,
        guard_port: GuardPort | None = None,
        auth_port: AuthPort | None = None,
    ) -> WorkflowEngine:
        """Build a WorkflowEngine from conformance fixture input (states, transitions, optional initial, current, event)."""
        state_names = list(data.get("states") or [])
        if "initial" in data:
            iv = data["initial"]
            initial = str(iv) if iv is not None else ""
        else:
            initial = ""
        finals = set(data.get("finals") or [])
        transitions_data = list(data.get("transitions") or [])
        current = data.get("current")
        current_state = str(current) if current is not None else initial
        return cls._build_from_data(
            state_names, initial, finals, transitions_data, current_state,
            guard_port=guard_port, auth_port=auth_port,
        )

    @classmethod
    def from_ast_node(
        cls,
        node: ASTNode,
        *,
        guard_port: GuardPort | None = None,
        auth_port: AuthPort | None = None,
    ) -> WorkflowEngine:
        """Build a WorkflowEngine from a workflow ASTNode."""
        state_names = list(node.properties.get("states", []))
        initial = node.properties.get("initial", state_names[0] if state_names else "")
        finals = set(node.properties.get("finals", []))
        transitions_data = list(node.properties.get("transitions", []))
        return cls._build_from_data(
            state_names, initial, finals, transitions_data, initial,
            guard_port=guard_port, auth_port=auth_port,
        )

    def get_initial_state(self) -> str:
        """Return the initial state of the workflow."""
        return self.initial_state

    def to_spec(self) -> WorkflowSpec:
        """Export immutable WorkflowSpec for adapter consumption."""
        transitions = tuple(
            TransitionSpec(
                from_state=t.from_state,
                to_state=t.to_state,
                on=t.on,
                guard=t.guard,
                auth_roles=tuple(t.auth_roles),
                on_enter=tuple(t.on_enter),
                on_leave=tuple(t.on_leave),
            )
            for t in self.transitions
        )
        return WorkflowSpec(
            states=tuple(self.states.keys()),
            initial=self.initial_state,
            finals=frozenset(s.name for s in self.states.values() if s.is_final),
            transitions=transitions,
        )

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
        if not self.initial_state:
            errors.append(Error(
                code="E_WF_NO_INITIAL",
                message="Workflow definition must declare an initial state",
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

            # Transition succeeds — emit R_WF_GUARD_PASS (trivial when no guard)
            self.current_state = tr.to_state
            if not any(r.code == "R_WF_GUARD_PASS" for r in reasons):
                reasons = list(reasons) + [
                    Reason(code="R_WF_GUARD_PASS", summary="Guard passed"),
                ]
            return FireResult(
                new_state=self.current_state,
                decision=Decision(allow=True, reasons=reasons),
                errors=errors,
            )

        errors.append(Error(
            code="E_WF_UNKNOWN_TRANSITION",
            message=f"No transition '{event}' defined from state '{self.current_state}'",
            severity="error",
        ))
        return FireResult(
            new_state=self.current_state,
            decision=Decision(allow=False, reasons=reasons),
            errors=errors,
        )
