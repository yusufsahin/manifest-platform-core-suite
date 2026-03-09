"""Workflow engine — pure FSM + workflow binding with guards/auth.

Per MASTER_SPEC section 12.
"""
from mpc.workflow.fsm import (
    WorkflowEngine,
    FSMState,
    Transition,
    FireResult,
    GuardPort,
    AuthPort,
)
from mpc.workflow.spec import WorkflowSpec, TransitionSpec

__all__ = [
    "WorkflowEngine",
    "FSMState",
    "Transition",
    "FireResult",
    "GuardPort",
    "AuthPort",
    "WorkflowSpec",
    "TransitionSpec",
]
