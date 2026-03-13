"""Structural validator — checks AST against DomainMeta schema rules.

Per MASTER_SPEC section 9:
  - Each def's kind MUST exist in DomainMeta.kinds
  - Each def MUST have all required properties for its kind
  - Function references MUST exist in DomainMeta.allowed_functions
  - Errors MUST be structured Error objects with registered codes
"""
from __future__ import annotations

import re

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.contracts.models import Error
from mpc.kernel.meta.models import DomainMeta

_FUNC_CALL_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")


def validate_structural(ast: ManifestAST, meta: DomainMeta) -> list[Error]:
    """Return a list of structural validation errors (empty = valid)."""
    errors: list[Error] = []

    for node in ast.defs:
        _check_node(node, meta, errors)

    return errors


def _check_node(
    node: ASTNode, meta: DomainMeta, errors: list[Error]
) -> None:
    kind_def = meta.get_kind(node.kind)

    if kind_def is None:
        errors.append(
            Error(
                code="E_META_UNKNOWN_KIND",
                message=f"Unknown kind '{node.kind}' on def '{node.id}'",
                severity="error",
                path=f"defs/{node.id}",
                source=node.source,
            )
        )
        return

    for prop in kind_def.required_props:
        if prop not in node.properties:
            errors.append(
                Error(
                    code="E_META_MISSING_REQUIRED_FIELD",
                    message=(
                        f"Kind '{node.kind}' requires property '{prop}' "
                        f"on def '{node.id}'"
                    ),
                    severity="error",
                    path=f"defs/{node.id}/{prop}",
                    source=node.source,
                )
            )

    if kind_def.allowed_types:
        allowed = set(kind_def.allowed_types)
        for prop_name, prop_val in node.properties.items():
            val_type = _typeof(prop_val)
            if val_type and val_type not in allowed:
                errors.append(
                    Error(
                        code="E_META_TYPE_NOT_ALLOWED",
                        message=(
                            f"Type '{val_type}' not allowed for kind "
                            f"'{node.kind}' (allowed: {sorted(allowed)})"
                        ),
                        severity="error",
                        path=f"defs/{node.id}/{prop_name}",
                        source=node.source,
                    )
                )

    if meta.allowed_functions:
        _check_function_refs(node, meta, errors)

    for child in node.children:
        _check_node(child, meta, errors)


def _check_function_refs(
    node: ASTNode, meta: DomainMeta, errors: list[Error]
) -> None:
    """Scan string properties for function-call patterns and reject unregistered ones."""
    allowed_fn_names = meta.function_names
    for prop_name, prop_val in node.properties.items():
        for fn_name in _extract_function_names(prop_val):
            if fn_name not in allowed_fn_names:
                errors.append(
                    Error(
                        code="E_META_FUNCTION_NOT_ALLOWED",
                        message=(
                            f"Function '{fn_name}' is not allowed "
                            f"(referenced in def '{node.id}', property '{prop_name}')"
                        ),
                        severity="error",
                        path=f"defs/{node.id}/{prop_name}",
                        source=node.source,
                    )
                )


def _extract_function_names(value: object) -> list[str]:
    """Extract function-call names from expression strings."""
    names: list[str] = []
    if isinstance(value, str):
        names.extend(m.group(1) for m in _FUNC_CALL_RE.finditer(value))
    elif isinstance(value, list):
        for item in value:
            names.extend(_extract_function_names(item))
    elif isinstance(value, dict):
        for v in value.values():
            names.extend(_extract_function_names(v))
    return names


def _typeof(value: object) -> str | None:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return None
