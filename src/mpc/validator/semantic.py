"""Semantic validator — checks for duplicates, unresolved refs, cycles.

Per MASTER_SPEC section 9:
  - No duplicate (kind, id) pairs
  - No unresolved references
  - No cycles in extends / import / workflow graphs
"""
from __future__ import annotations

from mpc.ast.models import ASTNode, ManifestAST
from mpc.contracts.models import Error


def validate_semantic(ast: ManifestAST) -> list[Error]:
    """Return a list of semantic validation errors (empty = valid)."""
    errors: list[Error] = []
    _check_duplicates(ast, errors)
    _check_workflow_refs(ast, errors)
    _check_cycles(ast, errors)
    return errors


def _check_duplicates(ast: ManifestAST, errors: list[Error]) -> None:
    seen: dict[tuple[str, str], ASTNode] = {}
    for node in ast.defs:
        key = (node.kind, node.id)
        if key in seen:
            errors.append(
                Error(
                    code="E_VALID_DUPLICATE_DEF",
                    message=f"Duplicate definition: kind='{node.kind}', id='{node.id}'",
                    severity="error",
                    path=f"defs/{node.id}",
                    source=node.source,
                )
            )
        else:
            seen[key] = node


def _check_workflow_refs(ast: ManifestAST, errors: list[Error]) -> None:
    """For workflow-like defs, check that transition states are declared."""
    for node in ast.defs:
        states = node.properties.get("states")
        transitions = node.properties.get("transitions")
        if not isinstance(states, list) or not isinstance(transitions, list):
            continue

        state_set = set(states)
        for tr in transitions:
            if not isinstance(tr, dict):
                continue
            for field in ("from", "to"):
                target = tr.get(field)
                if isinstance(target, str) and target not in state_set:
                    errors.append(
                        Error(
                            code="E_VALID_UNRESOLVED_REF",
                            message=(
                                f"Transition references unknown state '{target}' "
                                f"in def '{node.id}'"
                            ),
                            severity="error",
                            path=f"defs/{node.id}/transitions",
                            source=node.source,
                        )
                    )


def _check_cycles(ast: ManifestAST, errors: list[Error]) -> None:
    """Detect cycles in extends references."""
    extends_map: dict[str, str] = {}
    for node in ast.defs:
        parent = node.properties.get("extends")
        if isinstance(parent, str):
            extends_map[node.id] = parent

    for start_id in extends_map:
        visited: set[str] = set()
        current = start_id
        while current in extends_map:
            if current in visited:
                errors.append(
                    Error(
                        code="E_VALID_CYCLE_DETECTED",
                        message=f"Cycle detected in extends chain starting at '{start_id}'",
                        severity="error",
                        path=f"defs/{start_id}",
                    )
                )
                break
            visited.add(current)
            current = extends_map[current]
