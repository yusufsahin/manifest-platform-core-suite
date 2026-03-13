"""Deterministic ordering rules for definition-like lists.

Per HASH_CANONICAL_SPEC:
  1. priority DESC  (higher priority first)
  2. name    ASC
  3. id      ASC
"""
from __future__ import annotations

from typing import Any


def order_definitions(defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return *defs* sorted by the canonical definition ordering rule."""

    def _key(d: dict[str, Any]) -> tuple[int, str, str]:
        return (-d.get("priority", 0), d.get("name", ""), d.get("id", ""))

    return sorted(defs, key=_key)
