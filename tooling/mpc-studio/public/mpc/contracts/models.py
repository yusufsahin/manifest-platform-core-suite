"""Immutable contract dataclasses mirroring packages/core-contracts/schemas/*.

Every public model here maps 1-to-1 to a JSON Schema in core-contracts.
Field names use Python snake_case; serialization handles camelCase mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# EventEnvelope components
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Actor:
    id: str
    type: str  # user | service | system
    roles: list[str] = field(default_factory=list)
    claims: dict[str, Any] | None = None


@dataclass(frozen=True)
class Object:
    type: str
    id: str
    state: str | None = None
    attributes: dict[str, Any] | None = None


@dataclass(frozen=True)
class EventEnvelope:
    name: str
    kind: str  # create | update | delete | transition | custom
    timestamp: str
    actor: Actor
    object: Object
    id: str | None = None
    context: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None
    previous: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceSpan:
    line2: int | None = None
    col2: int | None = None


@dataclass(frozen=True)
class SourceMap:
    file: str | None = None
    line: int | None = None
    col: int | None = None
    span: SourceSpan | None = None


@dataclass(frozen=True)
class Error:
    code: str
    message: str
    severity: str  # info | warn | error | fatal
    path: str | None = None
    source: SourceMap | None = None
    details: dict[str, Any] | None = None
    causes: list[Error] | None = None


# ---------------------------------------------------------------------------
# Intent
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Intent:
    kind: str
    target: str | None = None
    params: dict[str, Any] | None = None
    idempotency_key: str | None = None


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Reason:
    code: str
    summary: str | None = None
    path: str | None = None
    data: dict[str, Any] | None = None


@dataclass(frozen=True)
class Message:
    level: str  # info | warn | error
    text: str
    i18n_key: str | None = None
    params: dict[str, Any] | None = None


@dataclass(frozen=True)
class Decision:
    allow: bool
    reasons: list[Reason] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    intents: list[Intent] = field(default_factory=list)
    trace: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TraceEvent:
    t: str
    at: str | None = None
    data: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    duration_ms: float | None = None


@dataclass(frozen=True)
class Trace:
    span_id: str
    engine: str
    events: list[TraceEvent] = field(default_factory=list)
    parent_span_id: str | None = None
