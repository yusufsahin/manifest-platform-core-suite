"""Unified parse entry point.

Auto-detects format (JSON / YAML / DSL) and normalizes to ManifestAST.
Per MASTER_SPEC section 8: all frontends MUST produce the same canonical
AST given semantically identical input.
"""
from __future__ import annotations

from mpc.ast import ManifestAST


def parse(text: str, *, format: str | None = None) -> ManifestAST:
    """Parse *text* into a ManifestAST.

    *format* can be ``"json"``, ``"yaml"``, or ``"dsl"``.
    When *None*, the format is auto-detected.
    """
    if format is None:
        format = _detect_format(text)

    if format == "json":
        from mpc.parser.json_frontend import parse_json
        return parse_json(text)
    elif format == "yaml":
        from mpc.parser.yaml_frontend import parse_yaml
        return parse_yaml(text)
    elif format == "dsl":
        from mpc.parser.dsl_frontend import parse_dsl
        return parse_dsl(text)
    else:
        from mpc.errors import MPCError
        raise MPCError("E_PARSE_UNSUPPORTED_FORMAT", f"Unknown format: '{format}'")


def _detect_format(text: str) -> str:
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return "json"
    if stripped.startswith("@") or stripped.startswith("def "):
        return "dsl"
    significant = _skip_line_comments(stripped)
    if significant.startswith("@") or significant.startswith("def "):
        return "dsl"
    return "yaml"


def _skip_line_comments(text: str) -> str:
    """Skip leading ``//`` comment lines and return the first significant line."""
    for line in text.splitlines():
        s = line.lstrip()
        if s and not s.startswith("//"):
            return s
    return ""
