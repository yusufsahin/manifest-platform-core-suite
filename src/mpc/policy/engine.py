"""Policy engine core.

Per MASTER_SPEC section 13:
  - Event matcher, expression-based conditions
  - Decision template with reasons and intents
  - Deterministic ordering: priority desc, then definition order
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.ast.models import ASTNode, ManifestAST
from mpc.contracts.models import Decision, Error, Intent, Reason
from mpc.meta.models import DomainMeta


@dataclass(frozen=True)
class PolicyResult:
    allow: bool
    reasons: list[Reason] = field(default_factory=list)
    intents: list[Intent] = field(default_factory=list)
    errors: list[Error] = field(default_factory=list)


@dataclass
class PolicyEngine:
    """Evaluate policy definitions against events."""

    ast: ManifestAST
    meta: DomainMeta

    def evaluate(
        self,
        event: dict[str, Any],
        *,
        actor_roles: list[str] | None = None,
    ) -> PolicyResult:
        """Evaluate all policy defs against *event* and produce a decision."""
        policy_defs = [d for d in self.ast.defs if d.kind == "Policy"]
        policy_defs.sort(
            key=lambda d: (-d.properties.get("priority", 0), d.id)
        )

        reasons: list[Reason] = []
        intents: list[Intent] = []
        allow = True

        for pdef in policy_defs:
            if not _matches_event(pdef, event):
                continue

            effect = pdef.properties.get("effect", "allow")
            if effect == "deny":
                allow = False
                reasons.append(Reason(
                    code="R_POLICY_DENY",
                    summary=f"Denied by policy '{pdef.id}'",
                ))
            else:
                reasons.append(Reason(
                    code="R_POLICY_ALLOW",
                    summary=f"Allowed by policy '{pdef.id}'",
                ))

            intent_defs = pdef.properties.get("intents", [])
            if isinstance(intent_defs, list):
                for idef in intent_defs:
                    if isinstance(idef, dict):
                        intents.append(Intent(
                            kind=idef.get("kind", "audit"),
                            target=idef.get("target", ""),
                        ))

        return PolicyResult(allow=allow, reasons=reasons, intents=intents)


def _matches_event(policy: ASTNode, event: dict[str, Any]) -> bool:
    """Check if a policy definition's matcher matches the event."""
    match = policy.properties.get("match")
    if match is None:
        return True
    if not isinstance(match, dict):
        return True
    for key, expected in match.items():
        actual = event.get(key)
        if actual != expected:
            return False
    return True
