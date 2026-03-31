"""Semantic validator — checks for duplicates, unresolved refs, cycles.

Per MASTER_SPEC section 9:
  - No duplicate (kind, id) pairs
  - No unresolved references
  - No cycles in extends / import / workflow graphs
  - No namespace conflicts
  - Workflow structure validation (initial state, etc.)
"""
from __future__ import annotations

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.contracts.models import Error


def _find_node_source_by_id(
    node_map: dict[tuple[str, str], ASTNode],
    node_id: str,
) -> object | None:
    """Return the first source span mapped to a definition id, if any."""
    for (_kind, mapped_id), node in node_map.items():
        if mapped_id == node_id:
            return node.source
    return None


def validate_semantic(ast: ManifestAST) -> list[Error]:
    """Return a list of semantic validation errors (empty = valid)."""
    errors: list[Error] = []
    _check_duplicates(ast, errors)
    _check_namespace_conflicts(ast, errors)
    _check_workflow_refs(ast, errors)
    _check_workflow_structure(ast, errors)
    _check_dead_ends_and_reachability(ast, errors)
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


def _check_namespace_conflicts(ast: ManifestAST, errors: list[Error]) -> None:
    """Detect definitions with the same id but different kinds (cross-kind ambiguity)."""
    id_to_kinds: dict[str, list[str]] = {}
    id_to_node: dict[str, ASTNode] = {}
    for node in ast.defs:
        id_to_kinds.setdefault(node.id, []).append(node.kind)
        if node.id not in id_to_node:
            id_to_node[node.id] = node

    for def_id, kinds in id_to_kinds.items():
        unique_kinds = set(kinds)
        if len(unique_kinds) > 1:
            errors.append(
                Error(
                    code="E_VALID_NAMESPACE_CONFLICT",
                    message=(
                        f"Namespace conflict: id '{def_id}' used by multiple kinds "
                        f"({', '.join(sorted(unique_kinds))}) in namespace "
                        f"'{ast.namespace}'"
                    ),
                    severity="error",
                    path=f"defs/{def_id}",
                    source=id_to_node[def_id].source,
                )
            )


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
            for fld in ("from", "to"):
                target = tr.get(fld)
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


def _check_workflow_structure(ast: ManifestAST, errors: list[Error]) -> None:
    """Validate workflow structure: initial state, reachability."""
    for node in ast.defs:
        if getattr(node, "kind", "") != "Workflow":
            continue
        states = node.properties.get("states")
        transitions = node.properties.get("transitions")
        if not isinstance(states, list) or not isinstance(transitions, list):
            continue
        if len(states) == 0:
            errors.append(
                Error(
                    code="E_VALID_INVALID_WORKFLOW",
                    message=f"Workflow '{node.id}' has no states",
                    severity="error",
                    path=f"defs/{node.id}/states",
                    source=node.source,
                )
            )
            continue

        initial = node.properties.get("initial")
        if initial is None and states:
            errors.append(
                Error(
                    code="E_WF_NO_INITIAL",
                    message=f"Workflow '{node.id}' has no initial state",
                    severity="error",
                    path=f"defs/{node.id}/initial",
                    source=node.source,
                )
            )
        elif isinstance(initial, str) and initial not in states:
            errors.append(
                Error(
                    code="E_WF_UNKNOWN_STATE",
                    message=(
                        f"Workflow '{node.id}' initial state '{initial}' "
                        f"is not in states list"
                    ),
                    severity="error",
                    path=f"defs/{node.id}/initial",
                    source=node.source,
                )
            )

        reachable: set[str] = set()
        if isinstance(initial, str):
            reachable.add(initial)
        for tr in transitions:
            if isinstance(tr, dict):
                src = tr.get("from")
                tgt = tr.get("to")
                if isinstance(src, str):
                    reachable.add(src)
                if isinstance(tgt, str):
                    reachable.add(tgt)

        state_set = set(states)
        unreachable = state_set - reachable
        for s in sorted(unreachable):
            errors.append(
                Error(
                    code="E_VALID_INVALID_WORKFLOW",
                    message=(
                        f"State '{s}' in workflow '{node.id}' is unreachable"
                    ),
                    severity="warning",
                    path=f"defs/{node.id}/states",
                    source=node.source,
                )
            )


def _check_dead_ends_and_reachability(ast: ManifestAST, errors: list[Error]) -> None:
    """Identify dead-ends (non-final states with no exit) and orphaned states (cannot reach final)."""
    for node in ast.defs:
        if getattr(node, "kind", "") != "Workflow":
            continue
            
        states = node.properties.get("states")
        transitions = node.properties.get("transitions")
        finals = set(node.properties.get("final_states", []))
        
        if not isinstance(states, list) or not isinstance(transitions, list):
            continue

        # Only enforce dead-end/orphan checks when explicit finals are declared.
        if not finals:
            continue
            
        # Build adjacency
        out_edges: dict[str, list[str]] = {s: [] for s in states}
        in_edges: dict[str, list[str]] = {s: [] for s in states}
        for tr in transitions:
            if isinstance(tr, dict):
                src, tgt = tr.get("from"), tr.get("to")
                if isinstance(src, str) and src in out_edges and isinstance(tgt, str):
                    out_edges[src].append(tgt)
                    if tgt in in_edges:
                        in_edges[tgt].append(src)
        
        # Dead ends: non-final state with no out edges
        for s in states:
            if s not in finals and not out_edges[s]:
                errors.append(
                    Error(
                        code="E_WF_DEAD_END",
                        message=f"State '{s}' in workflow '{node.id}' is a dead-end (no exit and not final)",
                        severity="warning",
                        path=f"defs/{node.id}/states",
                        source=node.source,
                    )
                )

        # Orphaned states: cannot reach any final state
        if finals:
            can_reach_final: set[str] = set()
            stack = list(finals)
            while stack:
                curr = stack.pop()
                if curr not in can_reach_final:
                    can_reach_final.add(curr)
                    stack.extend(in_edges.get(curr, []))
            
            orphans = set(states) - can_reach_final
            for o in sorted(orphans):
                errors.append(
                    Error(
                        code="E_WF_ORPHANED_STATE",
                        message=f"State '{o}' in workflow '{node.id}' cannot reach any final state",
                        severity="warning",
                        path=f"defs/{node.id}/states",
                        source=node.source,
                    )
                )


def _check_cycles(ast: ManifestAST, errors: list[Error]) -> None:
    """Detect cycles in extends, imports, and workflow transition graphs."""
    node_map: dict[tuple[str, str], ASTNode] = {}
    for node in ast.defs:
        node_map[(node.kind, node.id)] = node

    _check_extends_cycles(ast, node_map, errors)
    _check_import_cycles(ast, node_map, errors)
    _check_workflow_cycles(ast, node_map, errors)


def _check_extends_cycles(
    ast: ManifestAST,
    node_map: dict[tuple[str, str], ASTNode],
    errors: list[Error],
) -> None:
    extends_map: dict[tuple[str, str], tuple[str, str]] = {}
    for node in ast.defs:
        key = (node.kind, node.id)
        parent = node.properties.get("extends")
        if isinstance(parent, str):
            extends_map[key] = (node.kind, parent)

    reported: set[tuple[str, str]] = set()
    for start_key in extends_map:
        if start_key in reported:
            continue
        visited: set[tuple[str, str]] = set()
        current = start_key
        while current in extends_map:
            if current in visited:
                errors.append(
                    Error(
                        code="E_VALID_CYCLE_DETECTED",
                        message=(
                            f"Cycle detected in extends chain starting at "
                            f"'{start_key[1]}'"
                        ),
                        severity="error",
                        path=f"defs/{start_key[1]}",
                        source=node_map[start_key].source
                        if start_key in node_map
                        else None,
                    )
                )
                reported |= visited
                break
            visited.add(current)
            current = extends_map[current]


def _check_import_cycles(
    ast: ManifestAST,
    node_map: dict[tuple[str, str], ASTNode],
    errors: list[Error],
) -> None:
    """Build a directed graph from 'imports' lists and detect cycles via DFS."""
    adj: dict[str, list[str]] = {}
    for node in ast.defs:
        imports = node.properties.get("imports")
        if isinstance(imports, list):
            adj[node.id] = [str(i) for i in imports if isinstance(i, str)]

    if not adj:
        return

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {nid: WHITE for nid in adj}
    reported: set[str] = set()

    def dfs(nid: str) -> None:
        color[nid] = GRAY
        for dep in adj.get(nid, []):
            if dep not in color:
                continue
            if color[dep] == GRAY and dep not in reported:
                errors.append(
                    Error(
                        code="E_VALID_CYCLE_DETECTED",
                        message=f"Cycle detected in import chain involving '{dep}'",
                        severity="error",
                        path=f"defs/{dep}",
                        source=_find_node_source_by_id(node_map, dep),
                    )
                )
                reported.add(dep)
            elif color[dep] == WHITE:
                dfs(dep)
        color[nid] = BLACK

    for nid in list(adj.keys()):
        if color.get(nid, WHITE) == WHITE:
            dfs(nid)


def _check_workflow_cycles(
    ast: ManifestAST,
    node_map: dict[tuple[str, str], ASTNode],
    errors: list[Error],
) -> None:
    """Detect self-loops in workflow transition graphs (from == to)."""
    for node in ast.defs:
        transitions = node.properties.get("transitions")
        if not isinstance(transitions, list):
            continue
        for tr in transitions:
            if not isinstance(tr, dict):
                continue
            src = tr.get("from")
            tgt = tr.get("to")
            if isinstance(src, str) and src == tgt:
                errors.append(
                    Error(
                        code="E_VALID_CYCLE_DETECTED",
                        message=(
                            f"Self-loop in workflow '{node.id}': "
                            f"state '{src}' transitions to itself"
                        ),
                        severity="warning",
                        path=f"defs/{node.id}/transitions",
                        source=node.source,
                    )
                )
