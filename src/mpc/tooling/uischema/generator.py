"""Deterministic UI schema generator from AST + DomainMeta.

Produces a JSON-Schema-like structure for each definition kind,
including field types, labels, ordering, and validation constraints.
Output is fully deterministic: same AST + Meta always yields the
same schema, with keys sorted lexicographically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.meta.models import DomainMeta, KindDef


@dataclass(frozen=True)
class UISchemaResult:
    schemas: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


_PY_TO_JSON_TYPE: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def generate_ui_schema(
    ast: ManifestAST,
    meta: DomainMeta,
) -> UISchemaResult:
    """Generate a deterministic UI schema for each definition in the AST."""
    schemas: dict[str, Any] = {}
    warnings: list[str] = []

    kind_defs = {k.name: k for k in meta.kinds}
    defs_sorted = sorted(ast.defs, key=lambda d: (d.kind, d.id))

    for node in defs_sorted:
        schema_key = f"{node.kind}:{node.id}"
        kind_def = kind_defs.get(node.kind)
        schema = _build_node_schema(node, kind_def, warnings)
        schemas[schema_key] = schema

    return UISchemaResult(schemas=schemas, warnings=warnings)


def _build_node_schema(
    node: ASTNode,
    kind_def: KindDef | None,
    warnings: list[str],
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "title": node.name or node.id,
        "x-kind": node.kind,
        "x-id": node.id,
    }

    properties: dict[str, Any] = {}
    required: list[str] = []

    if kind_def and kind_def.required_props:
        required = sorted(kind_def.required_props)

    for prop_name in sorted(node.properties.keys()):
        value = node.properties[prop_name]
        prop_schema = _infer_property_schema(prop_name, value)
        properties[prop_name] = prop_schema

    if properties:
        schema["properties"] = properties
    if required:
        schema["required"] = required

    if node.children:
        children_schemas = []
        for child in sorted(node.children, key=lambda c: (c.kind, c.id)):
            children_schemas.append(_build_node_schema(child, kind_def, warnings))
        schema["x-children"] = children_schemas

    return schema


def _infer_property_schema(name: str, value: Any) -> dict[str, Any]:
    """Infer a JSON Schema fragment from a property's current value."""
    if value is None:
        return {"type": "null", "x-field": name}

    if isinstance(value, bool):
        return {"type": "boolean", "x-field": name, "default": value}

    if isinstance(value, int):
        return {"type": "integer", "x-field": name, "default": value}

    if isinstance(value, float):
        return {"type": "number", "x-field": name, "default": value}

    if isinstance(value, str):
        schema: dict[str, Any] = {"type": "string", "x-field": name}
        if value:
            schema["default"] = value
        return schema

    if isinstance(value, list):
        items_schema = _infer_array_items(value)
        schema = {"type": "array", "x-field": name}
        if items_schema:
            schema["items"] = items_schema
        return schema

    if isinstance(value, dict):
        props: dict[str, Any] = {}
        for k in sorted(value.keys()):
            props[k] = _infer_property_schema(k, value[k])
        return {"type": "object", "x-field": name, "properties": props}

    return {"type": "string", "x-field": name}


def _infer_array_items(values: list[Any]) -> dict[str, Any] | None:
    """Infer the items schema from a list's contents."""
    if not values:
        return None

    types: set[str] = set()
    for v in values:
        if isinstance(v, bool):
            types.add("boolean")
        elif isinstance(v, int):
            types.add("integer")
        elif isinstance(v, float):
            types.add("number")
        elif isinstance(v, str):
            types.add("string")
        elif isinstance(v, dict):
            types.add("object")
        elif isinstance(v, list):
            types.add("array")

    if len(types) == 1:
        return {"type": types.pop()}

    return {"type": sorted(types)}
