"""Decision composition engine.

Per MASTER_SPEC section 16:
  - Default strategy: deny-wins
  - Intent dedupe by (kind, target, idempotencyKey)
  - All reasons are collected in deterministic order
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.contracts.models import Decision, Intent, Reason


@dataclass(frozen=True)
class ComposeResult:
    allow: bool
    reasons: list[Reason] = field(default_factory=list)
    intents: list[Intent] = field(default_factory=list)


def compose_decisions(
    decisions: list[Decision],
    *,
    strategy: str = "deny-wins",
) -> ComposeResult:
    """Compose multiple Decision objects into one final result.

    Strategies:
      - "deny-wins": if ANY decision denies, the final result denies.
        Only deny-reasons are included in that case.
      - "allow-wins": if ANY decision allows, the final result allows.
    """
    if not decisions:
        return ComposeResult(allow=True)

    if strategy == "deny-wins":
        return _deny_wins(decisions)

    if strategy == "allow-wins":
        return _allow_wins(decisions)

    return _deny_wins(decisions)


def _deny_wins(decisions: list[Decision]) -> ComposeResult:
    has_deny = any(not d.allow for d in decisions)

    if has_deny:
        reasons = []
        for d in decisions:
            if not d.allow:
                reasons.extend(d.reasons)
    else:
        reasons = []
        for d in decisions:
            reasons.extend(d.reasons)

    all_intents: list[Intent] = []
    for d in decisions:
        all_intents.extend(d.intents)

    deduped = _dedupe_intents(all_intents)

    return ComposeResult(
        allow=not has_deny,
        reasons=reasons,
        intents=deduped,
    )


def _allow_wins(decisions: list[Decision]) -> ComposeResult:
    has_allow = any(d.allow for d in decisions)

    reasons = []
    for d in decisions:
        reasons.extend(d.reasons)

    all_intents: list[Intent] = []
    for d in decisions:
        all_intents.extend(d.intents)

    deduped = _dedupe_intents(all_intents)

    return ComposeResult(
        allow=has_allow,
        reasons=reasons,
        intents=deduped,
    )


def _dedupe_intents(intents: list[Intent]) -> list[Intent]:
    """Deduplicate intents by (kind, target, idempotencyKey).

    Preserves the order of first occurrence.
    """
    seen: set[tuple[str, str | None, str | None]] = set()
    result: list[Intent] = []
    for intent in intents:
        key = (intent.kind, intent.target, intent.idempotency_key)
        if key not in seen:
            seen.add(key)
            result.append(intent)
    return result
