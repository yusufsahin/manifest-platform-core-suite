"""Canonical AST model per MASTER_SPEC section 6.

AST root: schemaVersion, namespace, name, manifestVersion, defs[]
Each node: kind, id, name(optional), properties, children, source
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
from types import MappingProxyType
from typing import Any

from mpc.kernel.contracts.models import SourceMap


@dataclass(frozen=True)
class ASTNode:
    kind: str
    id: str
    name: str | None = None
    properties: Mapping[str, Any] = field(default_factory=dict)
    children: tuple["ASTNode", ...] = field(default_factory=tuple)
    source: SourceMap | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "properties", MappingProxyType(dict(self.properties)))
        object.__setattr__(self, "children", tuple(self.children))


@dataclass(frozen=True)
class ManifestAST:
    schema_version: int
    namespace: str
    name: str
    manifest_version: str = "0.0.0"
    defs: list[ASTNode] = field(default_factory=list)
