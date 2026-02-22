"""ACL engine — RBAC + optional ABAC + maskField Intent output.

Per MASTER_SPEC section 14.
"""
from mpc.acl.engine import ACLEngine, ACLResult

__all__ = ["ACLEngine", "ACLResult"]
