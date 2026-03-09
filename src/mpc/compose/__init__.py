"""Decision composition — deny-wins strategy + intent deduplication.

Per MASTER_SPEC section 16.
"""
from mpc.compose.engine import compose_decisions, ComposeResult

__all__ = ["compose_decisions", "ComposeResult"]
