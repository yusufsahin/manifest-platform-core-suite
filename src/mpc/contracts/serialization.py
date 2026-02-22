"""Bi-directional conversion between contract dataclasses and JSON-schema dicts.

Handles Python snake_case <-> JSON camelCase mapping for the handful of
multi-word field names used in the MPC schemas.
"""
from __future__ import annotations

import dataclasses
import types
import typing
from typing import Any, TypeVar, get_type_hints

T = TypeVar("T")

_PYTHON_TO_JSON: dict[str, str] = {
    "idempotency_key": "idempotencyKey",
    "span_id": "spanId",
    "parent_span_id": "parentSpanId",
    "duration_ms": "durationMs",
    "i18n_key": "i18nKey",
}

_JSON_TO_PYTHON: dict[str, str] = {v: k for k, v in _PYTHON_TO_JSON.items()}


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

def to_dict(obj: Any) -> dict[str, Any]:
    """Convert a contract dataclass instance to a JSON-schema-compatible dict.

    - Omits fields whose value is ``None``.
    - Recursively converts nested dataclasses and lists.
    """
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"Expected a dataclass instance, got {type(obj).__name__}")
    result: dict[str, Any] = {}
    for f in dataclasses.fields(obj):
        value = getattr(obj, f.name)
        if value is None:
            continue
        result[_PYTHON_TO_JSON.get(f.name, f.name)] = _ser(value)
    return result


def _ser(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_dict(value)
    if isinstance(value, list):
        return [_ser(item) for item in value]
    if isinstance(value, dict):
        return {k: _ser(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# from_dict
# ---------------------------------------------------------------------------

def from_dict(cls: type[T], data: dict[str, Any]) -> T:
    """Create a contract dataclass from a JSON-schema-compatible dict.

    - Maps JSON camelCase keys back to Python snake_case.
    - Recursively deserialises nested dataclasses and typed lists.
    """
    if not dataclasses.is_dataclass(cls):
        raise TypeError(f"Expected a dataclass type, got {cls}")

    hints = get_type_hints(cls)
    valid_names = {f.name for f in dataclasses.fields(cls)}
    kwargs: dict[str, Any] = {}

    for key, value in data.items():
        py_key = _JSON_TO_PYTHON.get(key, key)
        if py_key not in valid_names:
            continue
        kwargs[py_key] = _deser(hints.get(py_key), value)

    return cls(**kwargs)


def _unwrap_optional(hint: Any) -> Any | None:
    """Return the inner type of ``Optional[T]`` / ``T | None``, or *None*."""
    origin = getattr(hint, "__origin__", None)
    args = getattr(hint, "__args__", ())

    if isinstance(hint, types.UnionType) or origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return None


def _deser(hint: Any, value: Any) -> Any:
    if value is None:
        return None

    inner = _unwrap_optional(hint)
    if inner is not None:
        hint = inner

    origin = getattr(hint, "__origin__", None)

    if origin is list and isinstance(value, list):
        args = getattr(hint, "__args__", ())
        if args and dataclasses.is_dataclass(args[0]):
            return [
                from_dict(args[0], item) if isinstance(item, dict) else item
                for item in value
            ]
        return value

    if dataclasses.is_dataclass(hint) and isinstance(hint, type) and isinstance(value, dict):
        return from_dict(hint, value)

    return value
