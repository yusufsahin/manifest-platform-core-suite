"""Canonical AST model per MASTER_SPEC section 6.

AST root: schemaVersion, namespace, name, manifestVersion, defs[]
Each node: kind, id, name(optional), properties, children, source
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.contracts.models import SourceMap


@dataclass(frozen=True)
class ASTNode:
    kind: str
    id: str
    name: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    children: list[ASTNode] = field(default_factory=list)
    source: SourceMap | None = None


@dataclass(frozen=True)
class ManifestAST:
    schema_version: int
    namespace: str
    name: str
    manifest_version: str
    defs: list[ASTNode] = field(default_factory=list)
