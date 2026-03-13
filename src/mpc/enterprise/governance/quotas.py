"""Quota enforcement — parse, compile, eval limits per tenant.

Per EPIC F5:
  - Per-tenant limits on parse/compile/eval operations
  - E_QUOTA_EXCEEDED on any limit breach
  - Configurable via presets or per-tenant overrides
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mpc.kernel.contracts.models import Error


@dataclass
class QuotaLimits:
    """Per-tenant or global quota limits."""
    max_parse_ops: int = 1000
    max_compile_ops: int = 100
    max_eval_ops: int = 10000
    max_manifest_nodes: int = 10000
    max_total_defs: int = 5000


@dataclass
class QuotaEnforcer:
    """Track and enforce quota usage."""

    limits: QuotaLimits
    _parse_count: int = 0
    _compile_count: int = 0
    _eval_count: int = 0
    _node_count: int = 0
    _def_count: int = 0

    def reset(self) -> None:
        self._parse_count = 0
        self._compile_count = 0
        self._eval_count = 0
        self._node_count = 0
        self._def_count = 0

    def check_parse(self, count: int = 1) -> Error | None:
        """Record parse operations and check against limit."""
        self._parse_count += count
        if self._parse_count > self.limits.max_parse_ops:
            return Error(
                code="E_QUOTA_EXCEEDED",
                message=f"Parse quota exceeded (limit: {self.limits.max_parse_ops})",
                severity="error",
            )
        return None

    def check_compile(self, count: int = 1) -> Error | None:
        self._compile_count += count
        if self._compile_count > self.limits.max_compile_ops:
            return Error(
                code="E_QUOTA_EXCEEDED",
                message=f"Compile quota exceeded (limit: {self.limits.max_compile_ops})",
                severity="error",
            )
        return None

    def check_eval(self, count: int = 1, steps: int = 0, regex_ops: int = 0) -> Error | None:
        self._eval_count += count
        if self._eval_count > self.limits.max_eval_ops:
            return Error(
                code="E_QUOTA_EXCEEDED",
                message=f"Eval quota exceeded (limit: {self.limits.max_eval_ops})",
                severity="error",
            )
        # We could also track aggregate steps/regex here if limits existed
        return None

    def check_node_budget(self, steps: int, depth: int) -> Error | None:
        """Verify if a single execution exceeded node-specific limits."""
        if steps > self.limits.max_manifest_nodes: # repurposed for example
             return Error(code="E_QUOTA_COMPLEXITY", message="Expression too complex")
        return None

    def check_nodes(self, count: int) -> Error | None:
        self._node_count += count
        if self._node_count > self.limits.max_manifest_nodes:
            return Error(
                code="E_QUOTA_EXCEEDED",
                message=f"Manifest node quota exceeded (limit: {self.limits.max_manifest_nodes})",
                severity="error",
            )
        return None

    def check_defs(self, count: int) -> Error | None:
        self._def_count += count
        if self._def_count > self.limits.max_total_defs:
            return Error(
                code="E_QUOTA_EXCEEDED",
                message=f"Definition quota exceeded (limit: {self.limits.max_total_defs})",
                severity="error",
            )
        return None

    @property
    def usage(self) -> dict[str, int]:
        return {
            "parse": self._parse_count,
            "compile": self._compile_count,
            "eval": self._eval_count,
            "nodes": self._node_count,
            "defs": self._def_count,
        }
