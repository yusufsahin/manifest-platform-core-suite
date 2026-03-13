"""Legacy workflow compatibility exports."""

from mpc.features.workflow.fsm import (
    ActionPort,
    AuditPort,
    AuditRecord,
    AuthPort,
    FireResult,
    FSMState,
    GuardPort,
    Transition,
    WorkflowEngine,
)
from mpc.workflow.spec import TransitionSpec, WorkflowSpec

__all__ = [
    "WorkflowEngine",
    "FSMState",
    "Transition",
    "FireResult",
    "GuardPort",
    "AuthPort",
    "ActionPort",
    "AuditPort",
    "AuditRecord",
    "WorkflowSpec",
    "TransitionSpec",
]
