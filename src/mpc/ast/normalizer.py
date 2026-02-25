"""Normalize a raw dict (from any parser frontend) into a ManifestAST.

The raw dict MUST follow the canonical JSON shape:
{
    "schemaVersion": 1,
    "namespace": "acme",
    "name": "my-rules",
    "manifestVersion": "1.0.0",
    "defs": [
        {"kind": "Policy", "id": "p1", "name": "AllowEdit", "effect": "allow", ...}
    ]
}
"""
from __future__ import annotations

from typing import Any

from mpc.ast.models import ASTNode, ManifestAST
from mpc.contracts.models import SourceMap

_RESERVED_KEYS = frozenset({"kind", "id", "name", "children", "source"})


def normalize(raw: dict[str, Any]) -> ManifestAST:
    """Convert a raw manifest dict into a canonical ManifestAST."""
    defs = [_normalize_node(d) for d in raw.get("defs", []) if isinstance(d, dict)]
    return ManifestAST(
        schema_version=raw.get("schemaVersion", 1),
        namespace=raw.get("namespace", ""),
        name=raw.get("name", ""),
        manifest_version=raw.get("manifestVersion", "0.0.0"),
        defs=defs,
    )


def _normalize_node(raw: dict[str, Any]) -> ASTNode:
    props = {k: v for k, v in raw.items() if k not in _RESERVED_KEYS}

    source_raw = raw.get("source")
    source = (
        SourceMap(
            file=source_raw.get("file"),
            line=source_raw.get("line"),
            col=source_raw.get("col"),
        )
        if isinstance(source_raw, dict)
        else None
    )

    children_raw = raw.get("children", [])
    children = [_normalize_node(c) for c in children_raw]

    return ASTNode(
        kind=raw.get("kind", ""),
        id=raw.get("id", ""),
        name=raw.get("name"),
        properties=props,
        children=children,
        source=source,
    )
