"""Static analysis and validation for MPC Workflow definitions."""
from __future__ import annotations
from dataclasses import dataclass, field
from mpc.kernel.contracts.models import Error
from mpc.features.workflow.fsm import WorkflowEngine, WorkflowSpec

@dataclass
class WorkflowValidator:
    """Perform static analysis on a compiled WorkflowSpec or WorkflowEngine."""
    
    def validate(self, spec: WorkflowSpec) -> list[Error]:
        """Run all validations and return a list of discovered errors."""
        errors = []
        errors.extend(self.check_unreachable_states(spec))
        errors.extend(self.check_terminal_reachability(spec))
        return errors

    def check_unreachable_states(self, spec: WorkflowSpec) -> list[Error]:
        """Find states that are not reachable from the initial state."""
        visited = set()
        queue = [spec.initial]
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            
            for tr in spec.transitions:
                if tr.from_state == current:
                    if tr.to_state not in visited:
                        queue.append(tr.to_state)
        
        all_states = {s.name for s in spec.states}
        unreachable = all_states - visited
        
        errors = []
        for s in unreachable:
            errors.append(Error(
                code="E_WF_UNREACHABLE_STATE",
                message=f"State '{s}' is unreachable from the initial state",
                severity="warning"
            ))
        return errors

    def check_terminal_reachability(self, spec: WorkflowSpec) -> list[Error]:
        """Find non-final states that cannot reach any final state (potential deadlocks)."""
        final_states = {s.name for s in spec.states if s.is_final}
        if not final_states:
            return [] # No final states defined, can't check terminal reachability
            
        can_reach_final = set(final_states)
        changed = True
        
        while changed:
            changed = False
            for tr in spec.transitions:
                if tr.from_state not in can_reach_final and tr.to_state in can_reach_final:
                    can_reach_final.add(tr.from_state)
                    changed = True
        
        all_states = {s.name for s in spec.states}
        deadlocks = all_states - can_reach_final
        
        errors = []
        for s in deadlocks:
            errors.append(Error(
                code="E_WF_DEADLOCK_STATE",
                message=f"State '{s}' cannot reach any final state",
                severity="warning"
            ))
        return errors
