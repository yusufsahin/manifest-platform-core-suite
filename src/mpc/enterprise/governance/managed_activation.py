from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
from mpc.features.workflow.fsm import WorkflowEngine, FireResult
from mpc.kernel.contracts.models import Error

@dataclass
class ManagedActivation:
    """Orchestrate manifest lifecycle using a state machine."""
    
    engine: WorkflowEngine
    manifest_id: str
    approvals: List[str] = field(default_factory=list)
    
    def approve(self, role: str) -> None:
        """Record an approval from a specific role."""
        if role not in self.approvals:
            self.approvals.append(role)
            
    def request_activation(self) -> FireResult:
        """Attempt to move state towards 'Live'."""
        # Simple simulation: trigger 'DEPLOY' if in 'Staging'
        # or 'PROMOTE' if in 'Draft'
        if "Draft" in self.engine.active_states:
             return self.engine.fire("PROMOTE", {"actor_roles": self.approvals})
        elif "Staging" in self.engine.active_states:
             return self.engine.fire("DEPLOY", {"actor_roles": self.approvals})
        
        return FireResult(
            new_state=self.engine.current_state,
            decision=None,
            errors=[Error(code="E_GOV_STATE_INVALID", message="Invalid state for activation")]
        )

    @property
    def status(self) -> str:
        return self.engine.current_state
