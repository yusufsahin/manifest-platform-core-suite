"""Tests for import resolver (E3) — alias, semver, collision, cycle detection."""
import pytest

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.tooling.imports.resolver import ImportResolver, ImportResult, ImportSpec, check_semver


def _manifest(ns: str, *defs: ASTNode) -> ManifestAST:
    return ManifestAST(
        schema_version=1, namespace=ns, name=ns,
        manifest_version="1.0", defs=list(defs),
    )


class TestImportResolver:
    def test_basic_import(self):
        lib = _manifest("lib", ASTNode(kind="Entity", id="user", properties={"name": "User"}))
        base = _manifest(
            "app",
            ASTNode(kind="Import", id="lib", properties={"source": "lib"}),
            ASTNode(kind="Entity", id="order", properties={"name": "Order"}),
        )
        resolver = ImportResolver()
        resolver.register("lib", lib)
        result = resolver.resolve(base)
        assert "lib" in result.resolved_imports
        ids = [d.id for d in result.ast.defs if d.kind == "Entity"]
        assert "user" in ids
        assert "order" in ids

    def test_import_with_alias(self):
        lib = _manifest("lib", ASTNode(kind="Entity", id="user", properties={}))
        base = _manifest(
            "app",
            ASTNode(kind="Import", id="lib", properties={"source": "lib", "alias": "ext"}),
        )
        resolver = ImportResolver()
        resolver.register("lib", lib)
        result = resolver.resolve(base)
        ids = [d.id for d in result.ast.defs]
        assert "ext.user" in ids

    def test_import_not_found(self):
        base = _manifest(
            "app",
            ASTNode(kind="Import", id="missing", properties={"source": "missing"}),
        )
        resolver = ImportResolver()
        result = resolver.resolve(base)
        assert any(e.code == "E_VALID_UNRESOLVED_REF" for e in result.errors)

    def test_collision_detected(self):
        lib = _manifest("lib", ASTNode(kind="Entity", id="user", properties={}))
        base = _manifest(
            "app",
            ASTNode(kind="Import", id="lib", properties={"source": "lib"}),
            ASTNode(kind="Entity", id="user", properties={"name": "AppUser"}),
        )
        resolver = ImportResolver()
        resolver.register("lib", lib)
        result = resolver.resolve(base)
        assert any(e.code == "E_VALID_NAMESPACE_CONFLICT" for e in result.errors)

    def test_alias_avoids_collision(self):
        lib = _manifest("lib", ASTNode(kind="Entity", id="user", properties={}))
        base = _manifest(
            "app",
            ASTNode(kind="Import", id="lib", properties={"source": "lib", "alias": "ext"}),
            ASTNode(kind="Entity", id="user", properties={"name": "AppUser"}),
        )
        resolver = ImportResolver()
        resolver.register("lib", lib)
        result = resolver.resolve(base)
        assert not any(e.code == "E_VALID_NAMESPACE_CONFLICT" for e in result.errors)
        ids = [d.id for d in result.ast.defs if d.kind == "Entity"]
        assert "user" in ids
        assert "ext.user" in ids

    def test_cycle_detected(self):
        a = _manifest(
            "a",
            ASTNode(kind="Import", id="b", properties={"source": "b"}),
        )
        b = _manifest(
            "b",
            ASTNode(kind="Import", id="a", properties={"source": "a"}),
        )
        resolver = ImportResolver()
        resolver.register("a", a)
        resolver.register("b", b)
        result = resolver.resolve(a)
        assert any(e.code == "E_VALID_CYCLE_DETECTED" for e in result.errors)


class TestSemver:
    def test_exact_match(self):
        assert check_semver("1.2.3", "1.2.3") is True
        assert check_semver("1.2.4", "1.2.3") is False

    def test_caret(self):
        assert check_semver("1.2.3", "^1.0.0") is True
        assert check_semver("1.9.0", "^1.0.0") is True
        assert check_semver("2.0.0", "^1.0.0") is False
        assert check_semver("0.9.0", "^1.0.0") is False

    def test_tilde(self):
        assert check_semver("1.2.5", "~1.2.3") is True
        assert check_semver("1.2.3", "~1.2.3") is True
        assert check_semver("1.3.0", "~1.2.3") is False

    def test_gte(self):
        assert check_semver("1.0.0", ">=1.0.0") is True
        assert check_semver("2.0.0", ">=1.0.0") is True
        assert check_semver("0.9.9", ">=1.0.0") is False

    def test_lt(self):
        assert check_semver("0.9.9", "<1.0.0") is True
        assert check_semver("1.0.0", "<1.0.0") is False

    def test_import_version_constraint(self):
        lib = _manifest("lib", ASTNode(kind="Entity", id="e1", properties={}))
        base = _manifest("app", ASTNode(
            kind="Import", id="lib",
            properties={"source": "lib", "version": "^1.0.0"},
        ))
        resolver = ImportResolver()
        resolver.register("lib", lib, version="1.5.2")
        result = resolver.resolve(base)
        assert "lib" in result.resolved_imports
        assert not result.errors

    def test_import_version_mismatch(self):
        lib = _manifest("lib", ASTNode(kind="Entity", id="e1", properties={}))
        base = _manifest("app", ASTNode(
            kind="Import", id="lib",
            properties={"source": "lib", "version": "^2.0.0"},
        ))
        resolver = ImportResolver()
        resolver.register("lib", lib, version="1.5.2")
        result = resolver.resolve(base)
        assert any(
            e.code == "E_VALID_UNRESOLVED_REF" and "satisfy" in e.message
            for e in result.errors
        )
