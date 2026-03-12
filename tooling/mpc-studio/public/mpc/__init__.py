"""Manifest Platform Core Suite (MPC).

A Python library suite for building manifest-driven platforms with
declarative configuration, validation, and runtime evaluation.

Hierarchical Structure:
- mpc.kernel: Core data models, AST, parser, and error system.
- mpc.features: Runtime engines (Policy, Workflow, ACL, etc.).
- mpc.tooling: Development tools (Validator, Conformance runner, etc.).
- mpc.enterprise: Governance and enterprise-grade extensions.
"""

__version__ = "0.1.0"

# Expose top-level packages for easier access if desired,
# but keep the hierarchy explicit for clarity.
from mpc import kernel
from mpc import features
from mpc import tooling
from mpc import enterprise

__all__ = ["kernel", "features", "tooling", "enterprise"]
