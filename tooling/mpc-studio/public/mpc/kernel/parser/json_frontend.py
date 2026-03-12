"""JSON -> ManifestAST frontend."""
from __future__ import annotations

import json

from mpc.kernel.ast import ManifestAST, normalize
from mpc.kernel.errors import MPCError


def parse_json(text: str) -> ManifestAST:
    """Parse a JSON manifest string into a ManifestAST."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MPCError(
            "E_PARSE_SYNTAX",
            f"Invalid JSON at line {exc.lineno}, col {exc.colno}: {exc.msg}",
        ) from exc

    if not isinstance(raw, dict):
        raise MPCError("E_PARSE_SYNTAX", "Manifest root must be a JSON object")

    return normalize(raw)
