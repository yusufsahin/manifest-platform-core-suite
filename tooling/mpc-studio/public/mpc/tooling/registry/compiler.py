"""Deterministic registry compile.

Per MASTER_SPEC section 10:
  - Registry build MUST be deterministic and cacheable by
    astHash + metaHash + engineVersion
  - SHOULD provide: resolved types, dependency graph, ref resolver
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.canonical import stable_hash
from mpc.kernel.canonical.ordering import order_definitions
from mpc.kernel.meta.models import DomainMeta


@dataclass(frozen=True)
class CompiledRegistry:
    artifact_hash: str
    ast_hash: str
    meta_hash: str
    engine_version: str
    defs_by_id: dict[str, ASTNode] = field(default_factory=dict)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)


def compile_registry(
    ast: ManifestAST,
    meta: DomainMeta,
    *,
    engine_version: str = "0.1.0",
) -> CompiledRegistry:
    """Compile *ast* + *meta* into a deterministic, cacheable registry."""
    ordered_defs = order_definitions([_node_to_dict(d) for d in ast.defs])
    ast_dict = {
        "schemaVersion": ast.schema_version,
        "namespace": ast.namespace,
        "name": ast.name,
        "manifestVersion": ast.manifest_version,
        "defs": ordered_defs,
    }
    ast_hash = stable_hash(ast_dict)
    meta_hash = stable_hash(_meta_to_dict(meta))
    artifact_hash = stable_hash(
        {"astHash": ast_hash, "metaHash": meta_hash, "engineVersion": engine_version}
    )

    defs_by_id: dict[str, ASTNode] = {}
    dep_graph: dict[str, list[str]] = {}

    for node in ast.defs:
        defs_by_id[node.id] = node
        deps: list[str] = []
        extends = node.properties.get("extends")
        if isinstance(extends, str):
            deps.append(extends)
        imports = node.properties.get("imports")
        if isinstance(imports, list):
            deps.extend(str(i) for i in imports if isinstance(i, str))
        dep_graph[node.id] = deps

    return CompiledRegistry(
        artifact_hash=artifact_hash,
        ast_hash=ast_hash,
        meta_hash=meta_hash,
        engine_version=engine_version,
        defs_by_id=defs_by_id,
        dependency_graph=dep_graph,
    )


def _node_to_dict(node: ASTNode) -> dict[str, Any]:
    d: dict[str, Any] = {"kind": node.kind, "id": node.id}
    if node.name is not None:
        d["name"] = node.name
    if node.properties:
        d["properties"] = dict(node.properties)
    if node.children:
        d["children"] = [_node_to_dict(c) for c in node.children]
    return d


def _meta_to_dict(meta: DomainMeta) -> dict[str, Any]:
    return {
        "schemaVersion": meta.schema_version,
        "kinds": [
            {
                "name": k.name,
                "requiredProps": k.required_props,
                "allowedTypes": k.allowed_types,
            }
            for k in meta.kinds
        ],
        "allowedTypes": meta.allowed_types,
        "allowedEvents": meta.allowed_events,
        "allowedFunctions": [
            {"name": f.name, "args": f.args, "returns": f.returns, "cost": f.cost}
            for f in meta.allowed_functions
        ],
    }
