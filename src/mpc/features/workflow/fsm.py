"""Finite State Machine engine for workflow definitions.

Per MASTER_SPEC section 12:
  - Pure FSM: states, transitions, guards
  - Auth checks via AuthPort (optional)
  - Guard checks via GuardPort (optional)
  - Outputs Decision + Intent + Trace
  - Deterministic — same input always produces same output
"""
from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from mpc.kernel.ast.models import ASTNode
from mpc.kernel.contracts.models import Decision, Error, Intent, Reason


# ---------------------------------------------------------------------------
# Port interfaces for consuming apps
# ---------------------------------------------------------------------------

@runtime_checkable
class GuardPort(Protocol):
    """Interface for external guard logic."""
    def check(self, transition: str, context: dict[str, Any]) -> bool: ...


@runtime_checkable
class AuthPort(Protocol):
    """Interface for external authorization delegation."""
    def authorize(self, actor_id: str, transition: str) -> bool: ...


@runtime_checkable
class ActionPort(Protocol):
    """Interface for executing workflow actions."""
    def execute(self, action_name: str, context: dict[str, Any]) -> None: ...


@runtime_checkable
class AuditPort(Protocol):
    """Interface for auditing workflow transitions."""
    def record(self, record: AuditRecord) -> None: ...


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

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
    rule_type: str = "fixed"  # fixed, dynamic, internal
    timeout_ms: int | None = None


@dataclass(frozen=True)
class WorkflowSpec:
    """The compiled, serializable representation of a workflow."""
    name: str
    states: list[FSMState]
    transitions: list[Transition]
    initial: str
    ignored_triggers: list[str] = field(default_factory=list)
    namespace: str = ""
    manifest_version: str = "1.0"
    
    def to_json(self) -> str:
        """Serialize spec to JSON for designer tools."""
        return json.dumps(self.__dict__, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o))


@dataclass(frozen=True)
class FireResult:
    """Result of firing a transition."""
    new_state: str
    decision: Decision
    intent: Intent | None = None
    trace: list[str] = field(default_factory=list)
    errors: list[Error] = field(default_factory=list)
    actions_executed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditRecord:
    """Detailed record of a transition event."""
    workflow_name: str
    event: str
    source_state: str
    destination_state: str
    actor_id: str | None
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    context_keys: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: time.time())


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class WorkflowEngine:
    """Execute workflow definitions as finite state machines."""

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
        """Convenience property for single-state compatibility."""
        return ",".join(sorted(self.active_states))

    @classmethod
    def from_fixture_input(
        cls,
        data: dict[str, Any],
        *,
        guard_port: GuardPort | None = None,
        auth_port: AuthPort | None = None,
        action_port: ActionPort | None = None,
        audit_port: AuditPort | None = None,
        expr_engine: Any | None = None,
    ) -> WorkflowEngine:
        """Build a WorkflowEngine from conformance fixture input."""
        state_names = list(data.get("states") or [])
        initial = str(data.get("initial", ""))
        initials = set(data.get("initials", [initial] if initial else []))
        finals = set(data.get("finals") or [])

        states: dict[str, FSMState] = {}
        for s in state_names:
            parent = data.get("parents", {}).get(s)
            is_p = False
            p_data = data.get("parallels", [])
            if isinstance(p_data, list): is_p = (s in p_data)
            elif isinstance(p_data, dict): is_p = p_data.get(s, False)

            states[s] = FSMState(
                name=s,
                is_initial=(s in initials),
                is_final=(s in finals),
                parent=parent,
                on_enter=data.get("on_enter", {}).get(s, []),
                on_leave=data.get("on_leave", {}).get(s, []),
                on_activate=data.get("on_activate", {}).get(s, []),
                on_deactivate=data.get("on_deactivate", {}).get(s, []),
                is_parallel=is_p,
            )

        transitions: list[Transition] = []
        for tr in data.get("transitions") or []:
            if isinstance(tr, dict):
                on_enter = tr.get("on_enter") or tr.get("onEnter") or []
                on_leave = tr.get("on_leave") or tr.get("onLeave") or []
                if isinstance(on_enter, str): on_enter = [on_enter]
                if isinstance(on_leave, str): on_leave = [on_leave]
                transitions.append(Transition(
                    from_state=str(tr.get("from", "")),
                    to_state=str(tr.get("to", "")),
                    on=str(tr.get("on", tr.get("to", ""))),
                    guard=tr.get("guard"),
                    auth_roles=tr.get("authRoles", tr.get("auth_roles", [])),
                    on_enter=list(on_enter),
                    on_leave=list(on_leave),
                    rule_type=tr.get("rule_type", "fixed"),
                    timeout_ms=tr.get("timeout_ms", tr.get("timeout")),
                ))

        engine = cls(
            states=states,
            transitions=transitions,
            initial_state=initial,
            ignored_triggers=set(data.get("ignored_triggers", data.get("ignore", []))),
            guard_port=guard_port,
            auth_port=auth_port,
            action_port=action_port,
            audit_port=audit_port,
            expr_engine=expr_engine,
        )
        
        current = data.get("current")
        if current:
            if isinstance(current, list): engine.active_states = set(str(s) for s in current)
            else: engine.active_states = {str(current)}
        else:
            engine._set_initial_active_states()
        return engine

    @classmethod
    def from_ast_node(
        cls,
        node: ASTNode,
        *,
        guard_port: GuardPort | None = None,
        auth_port: AuthPort | None = None,
        action_port: ActionPort | None = None,
        audit_port: AuditPort | None = None,
        expr_engine: Any | None = None,
    ) -> WorkflowEngine:
        """Build a WorkflowEngine from an ASTNode."""
        state_objs = node.properties.get("states", [])
        states: dict[str, FSMState] = {}
        state_names = []
        for s in state_objs:
            name = s if isinstance(s, str) else s.get("name")
            parent = None if isinstance(s, str) else s.get("parent")
            state_names.append(name)
            states[name] = FSMState(
                name=name, parent=parent,
                on_enter=s.get("on_enter", []) if not isinstance(s, str) else [],
                on_leave=s.get("on_leave", []) if not isinstance(s, str) else [],
                on_activate=s.get("on_activate", []) if not isinstance(s, str) else [],
                on_deactivate=s.get("on_deactivate", []) if not isinstance(s, str) else [],
                is_parallel=s.get("is_parallel", False) if not isinstance(s, str) else False,
            )

        initial = node.properties.get("initial", state_names[0] if state_names else "")
        initials = set(node.properties.get("initials", [initial] if initial else []))
        finals = set(node.properties.get("finals", []))

        for name in states:
            states[name] = FSMState(
                name=name, is_initial=(name in initials), is_final=(name in finals),
                parent=states[name].parent, on_enter=states[name].on_enter, 
                on_leave=states[name].on_leave, is_parallel=states[name].is_parallel
            )

        transitions: list[Transition] = []
        for tr in node.properties.get("transitions", []):
            if isinstance(tr, dict):
                on_enter = tr.get("on_enter") or []
                on_leave = tr.get("on_leave") or []
                transitions.append(Transition(
                    from_state=str(tr.get("from", "")),
                    to_state=str(tr.get("to", "")),
                    on=str(tr.get("on", tr.get("to", ""))),
                    guard=tr.get("guard"),
                    auth_roles=tr.get("auth_roles", tr.get("authRoles", [])),
                    on_enter=list(on_enter),
                    on_leave=list(on_leave),
                    rule_type=tr.get("rule_type", "fixed"),
                ))

        engine = cls(
            states=states, transitions=transitions,
            initial_state=initial, ignored_triggers=set(node.properties.get("ignored_triggers", [])),
            guard_port=guard_port, auth_port=auth_port, action_port=action_port,
            audit_port=audit_port, expr_engine=expr_engine,
        )
        engine._set_initial_active_states()
        return engine

    def _set_initial_active_states(self) -> None:
        """Initialize active_states by finding all starting states in hierarchy."""
        if not self.initial_state: return
        self.active_states = set()
        self._add_state_and_children_initials(self.initial_state)

    def _add_state_and_children_initials(self, state_name: str) -> None:
        """Recursively add a state and its descendants' initial states (entry logic)."""
        if state_name in self.active_states: return
        self.active_states.add(state_name)
        st = self.states.get(state_name)
        if not st: return
        
        # If this state is parallel, we must enter initial states of ALL its children
        if st.is_parallel:
            for c_name, c_st in self.states.items():
                if c_st.parent == state_name and c_st.is_initial:
                    self._add_state_and_children_initials(c_name)
        else:
            # If not parallel, just find the one initial child if any
            for c_name, c_st in self.states.items():
                if c_st.parent == state_name and c_st.is_initial:
                    self._add_state_and_children_initials(c_name)
                    break

    def _get_path_to_root(self, state_name: str) -> list[str]:
        path, curr = [], state_name
        while curr:
            path.append(curr)
            st = self.states.get(curr)
            curr = st.parent if st else None
        return path

    def activate(self, context: dict[str, Any] | None = None) -> None:
        if self.is_active: return
        self.state_entry_time = time.time()
        ctx = context or {}
        for s_name in self.active_states:
            st = self.states.get(s_name)
            if st and self.action_port:
                for a in st.on_activate: self.action_port.execute(a, ctx)
        self.is_active = True

    def deactivate(self, context: dict[str, Any] | None = None) -> None:
        if not self.is_active: return
        ctx = context or {}
        for s_name in self.active_states:
            st = self.states.get(s_name)
            if st and self.action_port:
                for a in st.on_deactivate: self.action_port.execute(a, ctx)
        self.is_active = False

    def fire(self, event: str, *, actor_roles: list[str]|None=None, actor_id: str|None=None, context: dict[str, Any]|None=None) -> FireResult:
        if self._is_firing:
            self._event_queue.append({"event": event, "actor_roles": actor_roles, "actor_id": actor_id, "context": context})
            return FireResult(new_state=self.current_state, decision=Decision(allow=True, reasons=[Reason(code="R_WF_QUEUED", summary="Queued")]))
        self._is_firing = True
        try:
            result = self._process_fire(event, actor_roles=actor_roles, actor_id=actor_id, context=context)
            while self._event_queue:
                q = self._event_queue.pop(0)
                self._process_fire(q["event"], actor_roles=q["actor_roles"], actor_id=q["actor_id"], context=q["context"])
            return result
        finally: self._is_firing = False

    def available_transitions(self) -> list[Transition]:
        """Return transitions currently available from active states (including inherited paths)."""
        available: list[Transition] = []
        seen: set[tuple[str, str, str]] = set()

        for active in self.active_states:
            curr = active
            while curr:
                for tr in self.transitions:
                    if tr.from_state != curr:
                        continue
                    key = (tr.from_state, tr.on, tr.to_state)
                    if key not in seen:
                        seen.add(key)
                        available.append(tr)
                st = self.states.get(curr)
                curr = st.parent if st else None

        return available

    def validate(self) -> list[Error]:
        """Validate workflow structure for missing initial state and invalid references."""
        errors: list[Error] = []

        if not self.initial_state:
            errors.append(
                Error(
                    code="E_WF_NO_INITIAL",
                    message="Workflow definition must declare an initial state",
                    severity="error",
                )
            )

        if self.initial_state and self.initial_state not in self.states:
            errors.append(
                Error(
                    code="E_WF_INVALID_INITIAL",
                    message=f"Initial state '{self.initial_state}' is not declared in states",
                    severity="error",
                )
            )

        for tr in self.transitions:
            if tr.from_state not in self.states:
                errors.append(
                    Error(
                        code="E_WF_INVALID_TRANSITION",
                        message=f"Transition source state '{tr.from_state}' is not declared",
                        severity="error",
                    )
                )
            if tr.to_state not in self.states:
                errors.append(
                    Error(
                        code="E_WF_INVALID_TRANSITION",
                        message=f"Transition destination state '{tr.to_state}' is not declared",
                        severity="error",
                    )
                )

        return errors

    def _process_fire(self, event: str, *, actor_roles: list[str]|None=None, actor_id: str|None=None, context: dict[str, Any]|None=None) -> FireResult:
        reasons, errors, ctx = [], [], context or {}
        active_transitions = {}
        actor_roles = actor_roles or []
        
        # 1. Find all applicable transitions across all active states
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

        if not active_transitions:
            if event in self.ignored_triggers:
                return FireResult(new_state=self.current_state, decision=Decision(allow=True, reasons=[Reason(code="R_WF_IGNORED", summary="Ignored")]))
            errors.append(
                Error(
                    code="E_WF_UNKNOWN_TRANSITION",
                    message=f"No transition '{event}' defined from state '{self.current_state}'",
                    severity="error",
                )
            )
            result = FireResult(new_state=self.current_state, decision=Decision(allow=False), errors=errors)
            self._audit(event, actor_id, result, [])
            return result

        # 2. Filter by Auth and Guards
        final_executions = []
        for source, tr in active_transitions.items():
            if tr.auth_roles and not set(actor_roles).intersection(tr.auth_roles):
                reasons.append(Reason(code="R_WF_AUTH_DENIED", summary=f"Role denied for {source}"))
                continue
            if self.auth_port and actor_id and not self.auth_port.authorize(actor_id, tr.on):
                reasons.append(Reason(code="R_WF_AUTH_DENIED", summary=f"Auth denied for {source}"))
                continue
            allowed = True
            if tr.guard:
                if self.guard_port: allowed = self.guard_port.check(tr.on, ctx)
                if allowed and self.expr_engine:
                    try: allowed = bool(self.expr_engine.evaluate(tr.guard, ctx).value)
                    except Exception: allowed = False
            if not allowed:
                reasons.append(Reason(code="R_WF_GUARD_FAIL", summary=f"Guard fail for {source}"))
                continue
            reasons.append(Reason(code="R_WF_GUARD_PASS", summary=f"Guard pass for {source}"))
            final_executions.append((source, tr))

        if not final_executions:
            result = FireResult(new_state=self.current_state, decision=Decision(allow=False, reasons=reasons), errors=errors)
            self._audit(event, actor_id, result, list(ctx.keys()))
            return result

        # 3. Execute transitions
        total_actions, new_states = [], set(self.active_states)
        for src, tr in final_executions:
            src_path, dest = self._get_path_to_root(src), tr.to_state
            if tr.rule_type == "dynamic" and self.expr_engine:
                try: dest = str(self.expr_engine.evaluate(tr.to_state, ctx).value)
                except Exception as e: errors.append(Error(code="E_WF_DYN_FAIL", message=str(e))); continue
            
            dest_path = self._get_path_to_root(dest)
            lca = next((s for s in src_path if s in dest_path), None)
            
            def _exec(name):
                total_actions.append(name)
                if self.action_port: self.action_port.execute(name, ctx)

            # Exit logic
            for s in src_path:
                if s == lca and src != dest and tr.rule_type != "internal": break
                st = self.states.get(s)
                if st:
                    for a in st.on_leave: _exec(a)
                new_states.discard(s)

            # Transition actions
            for a in tr.on_leave + tr.on_enter: _exec(a)

            # Entry logic
            entry_path = []
            for s in dest_path:
                if s == lca and src != dest and tr.rule_type != "internal": break
                entry_path.append(s)
            for s in reversed(entry_path):
                st = self.states.get(s)
                if st:
                    for a in st.on_enter: _exec(a)
                new_states.add(s)
            
            self._add_child_initials_to_set(dest, new_states)

        self.active_states = new_states
        self.state_entry_time = time.time()
        
        result = FireResult(
            new_state=self.current_state, decision=Decision(allow=True, reasons=reasons),
            intent=Intent(kind=event, target=self.current_state),
            trace=[f"{s} -> {t.to_state}" for s, t in final_executions],
            errors=errors, actions_executed=total_actions
        )
        self._audit(event, actor_id, result, list(ctx.keys()))
        return result

    def _add_child_initials_to_set(self, state_name: str, target_set: set[str], depth: int = 0) -> None:
        """Helper for parallel entry logic."""
        if depth > 50: return # Safety
        st = self.states.get(state_name)
        if not st: return
        
        if st.is_parallel:
            for c_name, c_st in self.states.items():
                if c_st.parent == state_name and c_st.is_initial:
                    if c_name not in target_set:
                        target_set.add(c_name); self._add_child_initials_to_set(c_name, target_set, depth + 1)
        else:
            for c_name, c_st in self.states.items():
                if c_st.parent == state_name and c_st.is_initial:
                    if c_name not in target_set:
                        target_set.add(c_name); self._add_child_initials_to_set(c_name, target_set, depth + 1)
                    break

    def _audit(self, event: str, actor_id: str|None, result: FireResult, context_keys: list[str]) -> None:
        if not self.audit_port: return
        source = result.trace[0].split(" -> ")[0] if result.trace else self.current_state
        self.audit_port.record(AuditRecord(
            workflow_name="workflow", event=event, source_state=source,
            destination_state=result.new_state, actor_id=actor_id, allowed=result.decision.allow,
            reasons=[r.summary for r in result.decision.reasons], errors=[e.message for e in result.errors],
            actions=result.actions_executed, context_keys=context_keys
        ))

    async def fire_async(self, event: str, **kwargs) -> FireResult:
        """Async version of fire()."""
        return self.fire(event, **kwargs)

    def check_timeouts(self, context: dict[str, Any]|None=None) -> FireResult|None:
        """Check if any transitions from active states have timed out."""
        if not self.is_active: return None
        elapsed = (time.time() - self.state_entry_time) * 1000
        for tr in self.transitions:
            if tr.from_state in self.active_states and tr.timeout_ms is not None:
                if elapsed >= tr.timeout_ms: return self.fire(tr.on, context=context)
        return None

    def serialize_state(self) -> dict[str, Any]:
        """Serialize the current runtime state for persistence."""
        return {"active_states": list(self.active_states), "is_active": self.is_active, "queue_size": len(self._event_queue)}

    def restore_state(self, state_data: dict[str, Any]) -> None:
        """Restore the runtime state from serialized data."""
        active = state_data.get("active_states", state_data.get("current_state", []))
        self.active_states = set(active) if isinstance(active, list) else {str(active)}
        self.is_active = state_data.get("is_active", False)

    def to_mermaid(self) -> str:
        """Export the workflow as a Mermaid diagram with parallel support."""
        lines, sub = ["graph TD"], {}
        for s_name, st in self.states.items():
            p = st.parent or "root"
            if p not in sub: sub[p] = []
            sub[p].append(s_name)
        
        def _render(p_name, indent):
            if p_name not in sub: return
            for c in sub[p_name]:
                st = self.states[c]
                if c in sub:
                    lines.append(f"{indent}subgraph {'[Parallel] ' if st.is_parallel else ''}{c}")
                    _render(c, indent + "  ")
                    lines.append(f"{indent}end")
                else: lines.append(f"{indent}{c}")
        
        _render("root", "  ")
        for tr in self.transitions: lines.append(f"  {tr.from_state} -- {tr.on} --> {tr.to_state}")
        return "\n".join(lines)
