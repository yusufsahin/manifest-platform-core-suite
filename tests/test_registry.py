from mpc.ast import ASTNode, ManifestAST
from mpc.meta import DomainMeta, KindDef, FunctionDef
from mpc.registry import compile_registry


def _simple_ast() -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="acme",
        name="rules",
        manifest_version="1.0.0",
        defs=[
            ASTNode(kind="Policy", id="p1", properties={"effect": "allow"}),
            ASTNode(kind="Policy", id="p2", properties={"extends": "p1"}),
        ],
    )


def _simple_meta() -> DomainMeta:
    return DomainMeta(
        kinds=[KindDef(name="Policy", required_props=["effect"])],
        allowed_functions=[FunctionDef(name="len", args=["string"], returns="int")],
    )


class TestCompileRegistry:
    def test_produces_hashes(self):
        reg = compile_registry(_simple_ast(), _simple_meta())
        assert len(reg.artifact_hash) == 64
        assert len(reg.ast_hash) == 64
        assert len(reg.meta_hash) == 64

    def test_deterministic(self):
        r1 = compile_registry(_simple_ast(), _simple_meta())
        r2 = compile_registry(_simple_ast(), _simple_meta())
        assert r1.artifact_hash == r2.artifact_hash
        assert r1.ast_hash == r2.ast_hash

    def test_defs_by_id(self):
        reg = compile_registry(_simple_ast(), _simple_meta())
        assert "p1" in reg.defs_by_id
        assert "p2" in reg.defs_by_id

    def test_dependency_graph(self):
        reg = compile_registry(_simple_ast(), _simple_meta())
        assert reg.dependency_graph["p2"] == ["p1"]
        assert reg.dependency_graph["p1"] == []

    def test_different_engine_version_different_hash(self):
        r1 = compile_registry(_simple_ast(), _simple_meta(), engine_version="0.1.0")
        r2 = compile_registry(_simple_ast(), _simple_meta(), engine_version="0.2.0")
        assert r1.artifact_hash != r2.artifact_hash
        assert r1.ast_hash == r2.ast_hash
