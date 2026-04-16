"""Import resolver for manifest definitions.

Resolves cross-manifest imports with:
  - Alias support (import "x" as alias)
  - Semver constraint checking
  - Collision detection for duplicate definitions
  - Cycle detection in import graphs
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.contracts.models import Error


@dataclass(frozen=True)
class ImportSpec:
    """A single import declaration parsed from an AST node."""
    source: str
    alias: str | None = None
    version_constraint: str | None = None


@dataclass(frozen=True)
class ImportResult:
    ast: ManifestAST
    resolved_imports: list[str] = field(default_factory=list)
    errors: list[Error] = field(default_factory=list)


@dataclass
class ImportResolver:
    """Resolve imports across manifest files."""

    manifests: dict[str, ManifestAST] = field(default_factory=dict)
    versions: dict[str, str] = field(default_factory=dict)
    allowed_sources: set[str] | None = None
    max_imports: int = 100
    max_total_defs: int = 5000

    def register(self, name: str, ast: ManifestAST, version: str = "0.0.0") -> None:
        """Register a manifest as available for import."""
        self.manifests[name] = ast
        self.versions[name] = version

    def resolve(self, base: ManifestAST) -> ImportResult:
        """Resolve all imports declared in *base* and return merged AST."""
        errors: list[Error] = []
        resolved: list[str] = []
        imported_defs: list[ASTNode] = []

        import_specs = self._extract_imports(base)
        if len(import_specs) > self.max_imports:
            errors.append(
                Error(
                    code="E_QUOTA_EXCEEDED",
                    message=f"Import quota exceeded (limit: {self.max_imports})",
                    severity="error",
                )
            )
            return ImportResult(ast=base, errors=errors)

        # Cycle detection
        visited: set[str] = {base.namespace}
        cycle_err = self._check_cycles(base.namespace, import_specs, visited, [base.namespace])
        if cycle_err:
            errors.append(cycle_err)
            return ImportResult(ast=base, errors=errors)

        base_ids: set[tuple[str, str]] = {(d.kind, d.id) for d in base.defs}

        for spec in import_specs:
            if self.allowed_sources is not None and spec.source not in self.allowed_sources:
                errors.append(
                    Error(
                        code="E_VALID_UNRESOLVED_REF",
                        message=f"Import source '{spec.source}' is not in allowlist",
                        severity="error",
                    )
                )
                continue
            source_ast = self.manifests.get(spec.source)
            if source_ast is None:
                errors.append(Error(
                    code="E_VALID_UNRESOLVED_REF",
                    message=f"Import source '{spec.source}' not found",
                    severity="error",
                ))
                continue

            if spec.version_constraint:
                source_ver = self.versions.get(spec.source, "0.0.0")
                if not check_semver(source_ver, spec.version_constraint):
                    errors.append(Error(
                        code="E_VALID_UNRESOLVED_REF",
                        message=(
                            f"Import '{spec.source}' version {source_ver} "
                            f"does not satisfy constraint '{spec.version_constraint}'"
                        ),
                        severity="error",
                    ))
                    continue

            alias = spec.alias or spec.source
            for d in source_ast.defs:
                aliased_id = f"{alias}.{d.id}" if spec.alias else d.id

                key = (d.kind, aliased_id)
                if key in base_ids:
                    errors.append(Error(
                        code="E_VALID_NAMESPACE_CONFLICT",
                        message=(
                            f"Import collision: '{d.kind}:{aliased_id}' from "
                            f"'{spec.source}' conflicts with existing definition"
                        ),
                        severity="error",
                    ))
                    continue

                base_ids.add(key)
                imported_defs.append(ASTNode(
                    kind=d.kind,
                    id=aliased_id,
                    name=d.name,
                    properties=d.properties,
                    children=d.children,
                    source=d.source,
                ))

            resolved.append(spec.source)

        merged_defs = list(base.defs) + imported_defs
        if len(merged_defs) > self.max_total_defs:
            return ImportResult(
                ast=base,
                errors=[
                    Error(
                        code="E_QUOTA_EXCEEDED",
                        message=f"Definition quota exceeded (limit: {self.max_total_defs})",
                        severity="error",
                    )
                ],
            )
        merged_ast = ManifestAST(
            schema_version=base.schema_version,
            namespace=base.namespace,
            name=base.name,
            manifest_version=base.manifest_version,
            defs=merged_defs,
        )

        return ImportResult(ast=merged_ast, resolved_imports=resolved, errors=errors)

    def _extract_imports(self, ast: ManifestAST) -> list[ImportSpec]:
        """Extract ImportSpec entries from Import-kind definitions."""
        specs: list[ImportSpec] = []
        for d in ast.defs:
            if d.kind != "Import":
                continue
            source = d.properties.get("source", d.id)
            alias = d.properties.get("alias")
            version = d.properties.get("version")
            specs.append(ImportSpec(
                source=str(source),
                alias=str(alias) if alias else None,
                version_constraint=str(version) if version else None,
            ))
        return specs

    def _check_cycles(
        self,
        current: str,
        specs: list[ImportSpec],
        visited: set[str],
        path: list[str],
    ) -> Error | None:
        """DFS cycle detection through the import graph."""
        for spec in specs:
            if spec.source in visited:
                cycle_path = " -> ".join(path + [spec.source])
                return Error(
                    code="E_VALID_CYCLE_DETECTED",
                    message=f"Import cycle detected: {cycle_path}",
                    severity="error",
                )
            source_ast = self.manifests.get(spec.source)
            if source_ast is not None:
                visited.add(spec.source)
                sub_specs = self._extract_imports(source_ast)
                err = self._check_cycles(spec.source, sub_specs, visited, path + [spec.source])
                if err:
                    return err
        return None


def check_semver(version: str, constraint: str) -> bool:
    """Check if *version* satisfies a semver *constraint*.

    Supports:
      - Exact: "1.2.3"
      - Caret: "^1.2.3" (>=1.2.3, <2.0.0)
      - Tilde: "~1.2.3" (>=1.2.3, <1.3.0)
      - Prefix: ">=1.0.0", ">1.0.0", "<=2.0.0", "<2.0.0"
    """
    ver = _parse_ver(version)
    if ver is None:
        return False

    constraint = constraint.strip()

    if constraint.startswith("^"):
        target = _parse_ver(constraint[1:])
        if target is None:
            return False
        if ver < target:
            return False
        return ver[0] == target[0]

    if constraint.startswith("~"):
        target = _parse_ver(constraint[1:])
        if target is None:
            return False
        if ver < target:
            return False
        return ver[0] == target[0] and ver[1] == target[1]

    if constraint.startswith(">="):
        target = _parse_ver(constraint[2:])
        return target is not None and ver >= target
    if constraint.startswith(">"):
        target = _parse_ver(constraint[1:])
        return target is not None and ver > target
    if constraint.startswith("<="):
        target = _parse_ver(constraint[2:])
        return target is not None and ver <= target
    if constraint.startswith("<"):
        target = _parse_ver(constraint[1:])
        return target is not None and ver < target

    target = _parse_ver(constraint)
    return target is not None and ver == target


def _parse_ver(s: str) -> tuple[int, int, int] | None:
    s = s.strip()
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d+)\.(\d+)", s)
    if m:
        return (int(m.group(1)), int(m.group(2)), 0)
    m = re.match(r"^(\d+)", s)
    if m:
        return (int(m.group(1)), 0, 0)
    return None
