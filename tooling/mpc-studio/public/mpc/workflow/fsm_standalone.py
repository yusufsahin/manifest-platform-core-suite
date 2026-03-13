"""Finite State Machine engine for workflow definitions.
DEBUG STANDALONE VERSION
"""
from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# MOCKED MODELS for standalone testing
@dataclass
class Decision:
    allow: bool
    reasons: list[Any] = field(default_factory=list)

@dataclass
class Error:
    code: str
    message: str
    severity: str = "error"

@dataclass
class Intent:
    action: str
    target: str

@dataclass
class Reason:
    code: str
    summary: str

# ----------------- COPIED CODE -----------------

@runtime_checkable
class GuardPort(Protocol):
    def check(self, transition: str, context: dict[str, Any]) -> bool: ...

@runtime_checkable
class AuthPort(Protocol):
    def authorize(self, actor_id: str, transition: str) -> bool: ...

@runtime_checkable
class ActionPort(Protocol):
    def execute(self, action_name: str, context: dict[str, Any]) -> None: ...

@runtime_checkable
class AuditPort(Protocol):
    def record(self, record: Any) -> None: ...

@dataclass(frozen=True)
class FSMState:
    name: str
    is_initial: bool = False
    is_final: bool = False
    parent: str | None = None
    on_enter: list[str] = field(default_factory=list)
    on_leave: list[str] = field(default_factory=list)
    on_activate: list[str] = field(default_factory=list)
    on_deactivate: list[str] = field(default_factory=list)
    is_parallel: bool = False

@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    on: str
    guard: str | None = None
    auth_roles: list[str] = field(default_factory=list)
    on_enter: list[str] = field(default_factory=list)
    on_leave: list[str] = field(default_factory=list)
    rule_type: str = "fixed"
    timeout_ms: int | None = None

@dataclass
class WorkflowEngine:
    states: dict[str, FSMState] = field(default_factory=dict)
    transitions: list[Transition] = field(default_factory=list)
    active_states: set[str] = field(default_factory=set)
    initial_state: str = ""
    ignored_triggers: set[str] = field(default_factory=set)
    guard_port: GuardPort | None = None
    auth_port: AuthPort | None = None
    action_port: ActionPort | None = None
    audit_port: AuditPort | None = None
    expr_engine: Any | None = None
    _event_queue: list[dict[str, Any]] = field(default_factory=list, init=False)
    _is_firing: bool = field(default=False, init=False)
    is_active: bool = field(default=False, init=False)
    state_entry_time: float = field(default_factory=lambda: 0.0, init=False)

    @property
    def current_state(self) -> str:
        return ",".join(sorted(self.active_states))

    @classmethod
    def from_fixture_input(cls, data: dict[str, Any], **kwargs) -> WorkflowEngine:
        state_names = list(data.get("states") or [])
        initial = str(data.get("initial", ""))
        initials = set(data.get("initials", [initial] if initial else []))
        finals = set(data.get("finals") or [])
        states = {}
        for s in state_names:
            p = data.get("parents", {}).get(s)
            is_p = False
            p_data = data.get("parallels", [])
            if isinstance(p_data, list): is_p = (s in p_data)
            elif isinstance(p_data, dict): is_p = p_data.get(s, False)
            states[s] = FSMState(name=s, is_initial=(s in initials), is_final=(s in finals), parent=p, is_parallel=is_p)
        
        transitions = []
        for tr in data.get("transitions") or []:
            transitions.append(Transition(
                from_state=str(tr.get("from", "")), to_state=str(tr.get("to", "")), on=str(tr.get("on", tr.get("to", ""))),
                timeout_ms=tr.get("timeout_ms", tr.get("timeout"))
            ))
        engine = cls(states=states, transitions=transitions, initial_state=initial, **kwargs)
        engine._set_initial_active_states()
        return engine

    def _set_initial_active_states(self) -> None:
        if not self.initial_state: return
        self.active_states = set()
        self._add_state_and_children_initials(self.initial_state)

    def _add_state_and_children_initials(self, state_name: str) -> None:
        if state_name in self.active_states: return
        self.active_states.add(state_name)
        st = self.states.get(state_name)
        if not st: return
        for c_name, c_st in self.states.items():
            if c_st.parent == state_name and c_st.is_initial:
                self._add_state_and_children_initials(c_name)
                if not st.is_parallel: break

    def fire(self, event: str, **kwargs) -> Any:
        self._is_firing = True
        try:
            return self._process_fire(event, **kwargs)
        finally: self._is_firing = False

    def _process_fire(self, event: str, **kwargs) -> Any:
        active_transitions = {}
        for active in self.active_states:
            curr, tr_found = active, None
            while curr:
                for tr in self.transitions:
                    if tr.from_state == curr and tr.on == event:
                        tr_found = tr; break
                if tr_found: break
                st = self.states.get(curr)
                curr = st.parent if st else None
            if tr_found: active_transitions[active] = tr_found

        if not active_transitions: return None
        
        new_states = set(self.active_states)
        for src, tr in active_transitions.items():
            new_states.discard(src); new_states.add(tr.to_state)
            self._add_child_initials_to_set(tr.to_state, new_states)
        self.active_states = new_states
        return self.current_state

    def _add_child_initials_to_set(self, state_name: str, target_set: set[str]) -> None:
        st = self.states.get(state_name)
        if not st: return
        for c_name, c_st in self.states.items():
            if c_st.parent == state_name and c_st.is_initial:
                if c_name not in target_set:
                    target_set.add(c_name); self._add_child_initials_to_set(c_name, target_set)
                if not st.is_parallel: break

print("DEBUG: Standalone fsm.py LOADED")
