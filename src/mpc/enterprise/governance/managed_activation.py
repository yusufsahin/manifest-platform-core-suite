from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
from mpc.features.workflow.fsm import WorkflowEngine, FireResult
from mpc.kernel.contracts.models import Error

@dataclass
class ManagedActivation:
    """Orchestrate manifest lifecycle using a state machine with Quorum requirements."""
    
    engine: WorkflowEngine
    manifest_id: str
    # signed_approvals: {actor_id: role}
    signed_approvals: Dict[str, str] = field(default_factory=dict)
    # quorum_spec: {role: required_count}
    quorum_spec: Dict[str, int] = field(default_factory=dict)
    
    def approve(self, actor_id: str, role: str) -> None:
        """Record a unique approval from a specific actor and role."""
        self.signed_approvals[actor_id] = role
            
    def is_quorum_met(self) -> bool:
        """Check if all requirements in quorum_spec are satisfied."""
        if not self.quorum_spec:
            return True # No requirements
            
        role_counts: Dict[str, int] = {}
        for role in self.signed_approvals.values():
            role_counts[role] = role_counts.get(role, 0) + 1
            
        for role, required in self.quorum_spec.items():
            if role_counts.get(role, 0) < required:
                return False
        return True

    def request_activation(self) -> FireResult:
        """Attempt to move state towards 'Live' if quorum is met."""
        if not self.is_quorum_met():
            return FireResult(
                new_state=self.engine.current_state,
                decision=Decision(allow=False, reasons=[Reason(code="E_GOV_QUORUM_INCOMPLETE", summary="Quorum requirements not met")]),
                errors=[Error(code="E_GOV_QUORUM_INCOMPLETE", message=f"Quorum check failed. Requirements: {self.quorum_spec}")]
            )

        actor_roles = list(set(self.signed_approvals.values()))
        if "Draft" in self.engine.active_states:
             return self.engine.fire("PROMOTE", actor_roles=actor_roles)
        elif "Staging" in self.engine.active_states:
             return self.engine.fire("DEPLOY", actor_roles=actor_roles)
        
        return FireResult(
            new_state=self.engine.current_state,
            decision=Decision(allow=False),
            errors=[Error(code="E_GOV_STATE_INVALID", message="Invalid state for activation")]
        )

    @property
    def status(self) -> str:
        return self.engine.current_state
