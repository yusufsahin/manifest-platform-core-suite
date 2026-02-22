"""YAML -> ManifestAST frontend."""
from __future__ import annotations

import yaml

from mpc.ast import ManifestAST, normalize
from mpc.errors import MPCError


def parse_yaml(text: str) -> ManifestAST:
    """Parse a YAML manifest string into a ManifestAST."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise MPCError("E_PARSE_SYNTAX", f"Invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise MPCError("E_PARSE_SYNTAX", "Manifest root must be a YAML mapping")

    return normalize(raw)
