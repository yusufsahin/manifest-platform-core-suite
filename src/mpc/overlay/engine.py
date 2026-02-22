"""Overlay engine core.

Per MASTER_SPEC section 15:
  - Merge ops: replace, merge, append, remove, patch
  - Conflict detection and resolution
  - Selector-based targeting
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.ast.models import ASTNode, ManifestAST
from mpc.contracts.models import Error


@dataclass(frozen=True)
class OverlayResult:
    ast: ManifestAST
    applied: list[str] = field(default_factory=list)
    conflicts: list[Error] = field(default_factory=list)


@dataclass
class OverlayEngine:
    """Apply overlay definitions to a base ManifestAST."""

    base: ManifestAST

    def apply(self, overlay_ast: ManifestAST) -> OverlayResult:
        """Apply *overlay_ast* definitions on top of the base AST."""
        base_by_id: dict[str, ASTNode] = {d.id: d for d in self.base.defs}
        applied: list[str] = []
        conflicts: list[Error] = []

        overlay_defs = [d for d in overlay_ast.defs if d.kind == "Overlay"]

        for odef in overlay_defs:
            target_id = odef.properties.get("target")
            op = odef.properties.get("op", "merge")

            if not isinstance(target_id, str):
                conflicts.append(Error(
                    code="E_OVERLAY_UNKNOWN_SELECTOR",
                    message=f"Overlay '{odef.id}' has no target selector",
                    severity="error",
                    source=odef.source,
                ))
                continue

            if op == "remove":
                if target_id in base_by_id:
                    del base_by_id[target_id]
                    applied.append(f"remove:{target_id}")
                continue

            if target_id not in base_by_id and op not in ("replace", "append"):
                conflicts.append(Error(
                    code="E_OVERLAY_UNKNOWN_SELECTOR",
                    message=f"Target '{target_id}' not found in base AST",
                    severity="error",
                    source=odef.source,
                ))
                continue

            values = odef.properties.get("values", {})
            if not isinstance(values, dict):
                values = {}

            if op == "replace":
                base_by_id[target_id] = ASTNode(
                    kind=base_by_id.get(target_id, odef).kind,
                    id=target_id,
                    properties=values,
                    source=odef.source,
                )
                applied.append(f"replace:{target_id}")

            elif op == "merge":
                existing = base_by_id[target_id]
                merged = {**existing.properties, **values}
                base_by_id[target_id] = ASTNode(
                    kind=existing.kind,
                    id=existing.id,
                    name=existing.name,
                    properties=merged,
                    children=existing.children,
                    source=existing.source,
                )
                applied.append(f"merge:{target_id}")

            elif op == "append":
                existing = base_by_id.get(target_id)
                if existing is None:
                    base_by_id[target_id] = ASTNode(
                        kind=odef.properties.get("kind", "Unknown"),
                        id=target_id,
                        properties=values,
                        source=odef.source,
                    )
                else:
                    for k, v in values.items():
                        existing_val = existing.properties.get(k)
                        if isinstance(existing_val, list) and isinstance(v, list):
                            merged_val = existing_val + v
                        else:
                            merged_val = v
                        new_props = {**existing.properties, k: merged_val}
                    base_by_id[target_id] = ASTNode(
                        kind=existing.kind,
                        id=existing.id,
                        name=existing.name,
                        properties=new_props if values else existing.properties,
                        children=existing.children,
                        source=existing.source,
                    )
                applied.append(f"append:{target_id}")

            elif op == "patch":
                existing = base_by_id[target_id]
                merged = {**existing.properties, **values}
                base_by_id[target_id] = ASTNode(
                    kind=existing.kind,
                    id=existing.id,
                    name=existing.name,
                    properties=merged,
                    children=existing.children,
                    source=existing.source,
                )
                applied.append(f"patch:{target_id}")

            else:
                conflicts.append(Error(
                    code="E_OVERLAY_INVALID_OP",
                    message=f"Unknown overlay op '{op}' on '{odef.id}'",
                    severity="error",
                    source=odef.source,
                ))

        result_defs = list(base_by_id.values())
        result_ast = ManifestAST(
            schema_version=self.base.schema_version,
            namespace=self.base.namespace,
            name=self.base.name,
            manifest_version=self.base.manifest_version,
            defs=result_defs,
        )

        return OverlayResult(ast=result_ast, applied=applied, conflicts=conflicts)
