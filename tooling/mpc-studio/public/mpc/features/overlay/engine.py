"""Overlay engine core.

Per MASTER_SPEC section 15:
  - Merge ops: replace, merge, append, remove, patch
  - Conflicts MUST hard error unless explicitly resolved
  - Selectors MUST be stable: prefer (kind, namespace, id)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.contracts.models import Error


@dataclass(frozen=True)
class Selector:
    """Stable selector: (kind, namespace, id). Any field can be None for wildcard."""

    kind: str | None = None
    namespace: str | None = None
    id: str | None = None

    def matches(self, node: ASTNode, ns: str) -> bool:
        if self.id is not None and self.id != node.id:
            return False
        if self.kind is not None and self.kind != node.kind:
            return False
        if self.namespace is not None and self.namespace != ns:
            return False
        return True


@dataclass(frozen=True)
class OverlayResult:
    ast: ManifestAST
    applied: list[str] = field(default_factory=list)
    conflicts: list[Error] = field(default_factory=list)


def parse_selector(props: dict[str, Any]) -> Selector | None:
    """Extract a Selector from overlay properties."""
    sel_dict = props.get("selector")
    if isinstance(sel_dict, dict):
        return Selector(
            kind=sel_dict.get("kind"),
            namespace=sel_dict.get("namespace"),
            id=sel_dict.get("id"),
        )
    target = props.get("target")
    if isinstance(target, str):
        return Selector(id=target)
    return None


def _node_key(node: ASTNode) -> str:
    return f"{node.kind}:{node.id}"


@dataclass
class OverlayEngine:
    """Apply overlay definitions to a base ManifestAST."""

    base: ManifestAST

    def apply(self, overlay_ast: ManifestAST) -> OverlayResult:
        """Apply *overlay_ast* definitions on top of the base AST."""
        base_by_key: dict[str, ASTNode] = {_node_key(node): node for node in self.base.defs}
        applied: list[str] = []
        conflicts: list[Error] = []
        path_ops: dict[str, list[str]] = {}

        overlay_defs = [node for node in overlay_ast.defs if node.kind == "Overlay"]

        for overlay_def in overlay_defs:
            selector = parse_selector(overlay_def.properties)
            op = overlay_def.properties.get("op", "merge")
            path = overlay_def.properties.get("path")

            if selector is None:
                conflicts.append(
                    Error(
                        code="E_OVERLAY_UNKNOWN_SELECTOR",
                        message=f"Overlay '{overlay_def.id}' has no target selector",
                        severity="error",
                        source=overlay_def.source,
                    )
                )
                continue

            matched_keys = self._find_matches(selector, base_by_key)

            if op == "remove":
                if path:
                    parts = path.split(".")
                    for key in matched_keys:
                        existing = base_by_key[key]
                        new_props = dict(existing.properties)
                        _del_nested(new_props, parts)
                        base_by_key[key] = ASTNode(
                            kind=existing.kind,
                            id=existing.id,
                            name=existing.name,
                            properties=new_props,
                            children=existing.children,
                            source=existing.source,
                        )
                        applied.append(f"remove-path:{existing.id}:{path}")
                else:
                    for key in matched_keys:
                        node = base_by_key.pop(key)
                        applied.append(f"remove:{node.id}")
                continue

            if not matched_keys and op not in ("replace", "append"):
                conflicts.append(
                    Error(
                        code="E_OVERLAY_UNKNOWN_SELECTOR",
                        message=f"No target found for selector {_sel_str(selector)}",
                        severity="error",
                        source=overlay_def.source,
                    )
                )
                continue

            if path and op == "replace":
                for key in matched_keys:
                    conflict_key = f"{key}:{path}"
                    path_ops.setdefault(conflict_key, []).append(overlay_def.id)
                    if len(path_ops[conflict_key]) > 1:
                        conflicts.append(
                            Error(
                                code="E_OVERLAY_CONFLICT",
                                message=(
                                    f"Conflicting overlays on path '{path}': "
                                    "more than one replace op targets the same path"
                                ),
                                severity="error",
                                source=overlay_def.source,
                            )
                        )
                        continue

            values = overlay_def.properties.get(
                "values", overlay_def.properties.get("value")
            )
            if values is None:
                values = {}
            if not isinstance(values, dict):
                values = {path: values} if path else {}

            if op == "replace":
                for key in matched_keys:
                    existing = base_by_key[key]
                    if path:
                        _apply_path_op(
                            base_by_key,
                            key,
                            existing,
                            path,
                            values,
                            op,
                            applied,
                        )
                    else:
                        base_by_key[key] = ASTNode(
                            kind=existing.kind,
                            id=existing.id,
                            properties=values,
                            source=overlay_def.source,
                        )
                        applied.append(f"replace:{existing.id}")

                if not matched_keys and selector and selector.id:
                    kind = overlay_def.properties.get("kind", selector.kind or "Unknown")
                    new_node = ASTNode(
                        kind=kind,
                        id=selector.id,
                        properties=values,
                        source=overlay_def.source,
                    )
                    base_by_key[_node_key(new_node)] = new_node
                    applied.append(f"replace:{selector.id}")

            elif op == "merge":
                for key in matched_keys:
                    existing = base_by_key[key]
                    if path:
                        _apply_path_op(
                            base_by_key,
                            key,
                            existing,
                            path,
                            values,
                            op,
                            applied,
                        )
                    else:
                        merged = _deep_merge(existing.properties, values)
                        base_by_key[key] = ASTNode(
                            kind=existing.kind,
                            id=existing.id,
                            name=existing.name,
                            properties=merged,
                            children=existing.children,
                            source=existing.source,
                        )
                        applied.append(f"merge:{existing.id}")

            elif op == "append":
                for key in matched_keys:
                    existing = base_by_key[key]
                    if path:
                        _apply_path_op(
                            base_by_key,
                            key,
                            existing,
                            path,
                            values,
                            op,
                            applied,
                        )
                    else:
                        new_props = dict(existing.properties)
                        for prop_key, value in values.items():
                            existing_value = new_props.get(prop_key)
                            if isinstance(existing_value, list) and isinstance(value, list):
                                new_props[prop_key] = existing_value + value
                            else:
                                new_props[prop_key] = value
                        base_by_key[key] = ASTNode(
                            kind=existing.kind,
                            id=existing.id,
                            name=existing.name,
                            properties=new_props,
                            children=existing.children,
                            source=existing.source,
                        )
                        applied.append(f"append:{existing.id}")

                if not matched_keys and selector and selector.id:
                    kind = overlay_def.properties.get("kind", selector.kind or "Unknown")
                    new_node = ASTNode(
                        kind=kind,
                        id=selector.id,
                        properties=values if isinstance(values, dict) else {},
                        source=overlay_def.source,
                    )
                    base_by_key[_node_key(new_node)] = new_node
                    applied.append(f"append:{selector.id}")

            elif op == "patch":
                for key in matched_keys:
                    existing = base_by_key[key]
                    merged = dict(existing.properties)
                    for prop_key, prop_val in values.items():
                        existing_val = merged.get(prop_key)
                        if isinstance(existing_val, dict) and isinstance(prop_val, dict):
                            merged[prop_key] = {**existing_val, **prop_val}
                        else:
                            merged[prop_key] = prop_val
                    base_by_key[key] = ASTNode(
                        kind=existing.kind,
                        id=existing.id,
                        name=existing.name,
                        properties=merged,
                        children=existing.children,
                        source=existing.source,
                    )
                    applied.append(f"patch:{existing.id}")

            else:
                conflicts.append(
                    Error(
                        code="E_OVERLAY_INVALID_OP",
                        message=f"Unknown overlay op '{op}' on '{overlay_def.id}'",
                        severity="error",
                        source=overlay_def.source,
                    )
                )

        result_ast = ManifestAST(
            schema_version=self.base.schema_version,
            namespace=self.base.namespace,
            name=self.base.name,
            manifest_version=self.base.manifest_version,
            defs=list(base_by_key.values()),
        )
        return OverlayResult(ast=result_ast, applied=applied, conflicts=conflicts)

    def _find_matches(
        self, selector: Selector, base_by_key: dict[str, ASTNode]
    ) -> list[str]:
        return [
            key
            for key, node in base_by_key.items()
            if selector.matches(node, self.base.namespace)
        ]


def _apply_path_op(
    base_by_key: dict[str, ASTNode],
    key: str,
    existing: ASTNode,
    path: str,
    values: dict[str, Any],
    op: str,
    applied: list[str],
) -> None:
    """Apply an operation at a specific dotted path within a node's properties."""
    new_props = dict(existing.properties)
    parts = path.split(".")

    if op == "replace":
        value = values.get(path, next(iter(values.values())) if values else None)
        _set_nested(new_props, parts, value)
    elif op == "merge":
        current = _get_nested(new_props, parts)
        if isinstance(current, dict) and isinstance(values, dict):
            _set_nested(new_props, parts, {**current, **values})
        else:
            _set_nested(new_props, parts, values)
    elif op == "append":
        value = values.get(path, next(iter(values.values())) if values else None)
        current = _get_nested(new_props, parts)
        if isinstance(current, list) and isinstance(value, list):
            _set_nested(new_props, parts, current + value)
        else:
            _set_nested(new_props, parts, value)

    base_by_key[key] = ASTNode(
        kind=existing.kind,
        id=existing.id,
        name=existing.name,
        properties=new_props,
        children=existing.children,
        source=existing.source,
    )
    applied.append(f"{op}:{existing.id}:{path}")


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _get_nested(obj: dict[str, Any], parts: list[str]) -> Any:
    current: Any = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _del_nested(obj: dict[str, Any], parts: list[str]) -> None:
    """Delete the key at the end of *parts* from a nested dict. No-op if missing."""
    for part in parts[:-1]:
        if not isinstance(obj, dict) or part not in obj:
            return
        obj = obj[part]
    if isinstance(obj, dict):
        obj.pop(parts[-1], None)


def _set_nested(obj: dict[str, Any], parts: list[str], value: Any) -> None:
    for part in parts[:-1]:
        obj = obj.setdefault(part, {})
    obj[parts[-1]] = value


def _sel_str(sel: Selector) -> str:
    parts = []
    if sel.kind:
        parts.append(f"kind={sel.kind}")
    if sel.namespace:
        parts.append(f"namespace={sel.namespace}")
    if sel.id:
        parts.append(f"id={sel.id}")
    return f"({', '.join(parts)})"
