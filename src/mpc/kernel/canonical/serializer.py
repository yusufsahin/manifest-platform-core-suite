"""Canonical JSON serialization per HASH_CANONICAL_SPEC.

Rules:
  - Object keys sorted lexicographically (Unicode codepoint order).
  - No insignificant whitespace.
  - UTF-8 encoding.
  - canonicalize(canonicalize(x)) == canonicalize(x)  (idempotent).
"""
from __future__ import annotations

import json
from typing import Any


def canonicalize(obj: Any) -> str:
    """Return canonical JSON string with sorted keys and no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonicalize_bytes(obj: Any) -> bytes:
    """Return canonical JSON as UTF-8 bytes."""
    return canonicalize(obj).encode("utf-8")
