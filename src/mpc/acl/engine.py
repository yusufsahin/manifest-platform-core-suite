"""ACL engine core.

Per MASTER_SPEC section 14:
  - RBAC minimum, optional ABAC
  - Role hierarchy, action-resource pairs
  - Deterministic evaluation order
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.ast.models import ASTNode, ManifestAST
from mpc.contracts.models import Error, Reason


@dataclass(frozen=True)
class ACLResult:
    allowed: bool
    reasons: list[Reason] = field(default_factory=list)
    errors: list[Error] = field(default_factory=list)


@dataclass
class ACLEngine:
    """Evaluate ACL definitions for access control decisions."""

    ast: ManifestAST

    def check(
        self,
        action: str,
        resource: str,
        *,
        actor_roles: list[str] | None = None,
        actor_attrs: dict[str, Any] | None = None,
    ) -> ACLResult:
        """Check if *action* on *resource* is allowed for the given actor."""
        roles = set(actor_roles or [])
        acl_defs = [d for d in self.ast.defs if d.kind == "ACL"]
        acl_defs.sort(
            key=lambda d: (-d.properties.get("priority", 0), d.id)
        )

        reasons: list[Reason] = []
        errors: list[Error] = []

        for rule in acl_defs:
            rule_action = rule.properties.get("action")
            rule_resource = rule.properties.get("resource")

            if rule_action is not None and rule_action != action and rule_action != "*":
                continue
            if rule_resource is not None and rule_resource != resource and rule_resource != "*":
                continue

            required_roles = rule.properties.get("roles", [])
            if isinstance(required_roles, list) and required_roles:
                if roles & set(required_roles):
                    effect = rule.properties.get("effect", "allow")
                    if effect == "deny":
                        reasons.append(Reason(
                            code="R_ACL_DENY_ROLE",
                            summary=f"Denied by ACL rule '{rule.id}'",
                        ))
                        return ACLResult(allowed=False, reasons=reasons, errors=errors)
                    reasons.append(Reason(
                        code="R_ACL_ALLOW_ROLE",
                        summary=f"Allowed by ACL rule '{rule.id}'",
                    ))
                    return ACLResult(allowed=True, reasons=reasons, errors=errors)

            condition = rule.properties.get("condition")
            if isinstance(condition, dict) and actor_attrs:
                if _eval_abac_condition(condition, actor_attrs):
                    effect = rule.properties.get("effect", "allow")
                    if effect == "deny":
                        reasons.append(Reason(
                            code="R_ACL_DENY_ABAC",
                            summary=f"Denied by ABAC rule '{rule.id}'",
                        ))
                        return ACLResult(allowed=False, reasons=reasons, errors=errors)
                    reasons.append(Reason(
                        code="R_ACL_ALLOW_ABAC",
                        summary=f"Allowed by ABAC rule '{rule.id}'",
                    ))
                    return ACLResult(allowed=True, reasons=reasons, errors=errors)

        reasons.append(Reason(
            code="R_ACL_DENY_ROLE",
            summary=f"No matching ACL rule for action='{action}', resource='{resource}'",
        ))
        return ACLResult(allowed=False, reasons=reasons, errors=errors)


def _eval_abac_condition(condition: dict[str, Any], attrs: dict[str, Any]) -> bool:
    """Evaluate a simple ABAC condition dict against actor attributes."""
    for key, expected in condition.items():
        if attrs.get(key) != expected:
            return False
    return True
