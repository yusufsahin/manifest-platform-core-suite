"""Immutable workflow spec used by the legacy compatibility surface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransitionSpec:
    """Immutable transition definition."""

    from_state: str
    to_state: str
    on: str
    guard: str | None = None
    auth_roles: tuple[str, ...] = ()
    on_enter: tuple[str, ...] = ()
    on_leave: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowSpec:
    """Immutable workflow definition for adapter consumption."""

    states: tuple[str, ...]
    initial: str
    finals: frozenset[str]
    transitions: tuple[TransitionSpec, ...]
