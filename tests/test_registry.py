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

    def test_properties_cannot_overwrite_kind_or_id(self):
        """BUG-2 regression: properties named 'kind' or 'id' must not corrupt the hash."""
        ast_clean = ManifestAST(
            schema_version=1, namespace="ns", name="n", manifest_version="1.0.0",
            defs=[ASTNode(kind="Policy", id="p1", properties={"effect": "allow"})],
        )
        ast_tricky = ManifestAST(
            schema_version=1, namespace="ns", name="n", manifest_version="1.0.0",
            defs=[ASTNode(kind="Policy", id="p1", properties={"effect": "allow", "kind": "Evil"})],
        )
        r_clean = compile_registry(ast_clean, _simple_meta())
        r_tricky = compile_registry(ast_tricky, _simple_meta())
        assert r_clean.ast_hash != r_tricky.ast_hash

    def test_allowed_events_affects_meta_hash(self):
        """BUG-3 regression: different allowed_events must produce different meta_hash."""
        meta_a = DomainMeta(
            kinds=[KindDef(name="Policy")],
            allowed_events=["user.created"],
        )
        meta_b = DomainMeta(
            kinds=[KindDef(name="Policy")],
            allowed_events=["user.created", "user.deleted"],
        )
        ast = _simple_ast()
        r_a = compile_registry(ast, meta_a)
        r_b = compile_registry(ast, meta_b)
        assert r_a.meta_hash != r_b.meta_hash

    def test_imports_list_adds_to_dep_graph(self):
        ast = ManifestAST(
            schema_version=1, namespace="ns", name="n", manifest_version="1.0.0",
            defs=[
                ASTNode(kind="Policy", id="p1", properties={"effect": "allow"}),
                ASTNode(kind="Policy", id="p2", properties={"imports": ["p1", "p3"]}),
            ],
        )
        reg = compile_registry(ast, _simple_meta())
        assert "p1" in reg.dependency_graph["p2"]
        assert "p3" in reg.dependency_graph["p2"]

    def test_children_affect_ast_hash(self):
        ast_no_child = ManifestAST(
            schema_version=1, namespace="ns", name="n", manifest_version="1.0.0",
            defs=[ASTNode(kind="Policy", id="p1", properties={"effect": "allow"})],
        )
        ast_with_child = ManifestAST(
            schema_version=1, namespace="ns", name="n", manifest_version="1.0.0",
            defs=[ASTNode(
                kind="Policy", id="p1", properties={"effect": "allow"},
                children=[ASTNode(kind="Condition", id="c1", properties={"type": "role"})],
            )],
        )
        r1 = compile_registry(ast_no_child, _simple_meta())
        r2 = compile_registry(ast_with_child, _simple_meta())
        assert r1.ast_hash != r2.ast_hash

    def test_empty_ast_empty_dep_graph(self):
        ast = ManifestAST(schema_version=1, namespace="ns", name="n", manifest_version="1.0.0", defs=[])
        reg = compile_registry(ast, _simple_meta())
        assert reg.defs_by_id == {}
        assert reg.dependency_graph == {}

    def test_def_order_does_not_affect_ast_hash(self):
        """IMP-3 regression: different def ordering must produce same ast_hash."""
        ast_1 = ManifestAST(
            schema_version=1, namespace="ns", name="n", manifest_version="1.0.0",
            defs=[
                ASTNode(kind="Policy", id="p1", properties={"effect": "allow", "priority": 10}),
                ASTNode(kind="Policy", id="p2", properties={"effect": "deny", "priority": 5}),
            ],
        )
        ast_2 = ManifestAST(
            schema_version=1, namespace="ns", name="n", manifest_version="1.0.0",
            defs=[
                ASTNode(kind="Policy", id="p2", properties={"effect": "deny", "priority": 5}),
                ASTNode(kind="Policy", id="p1", properties={"effect": "allow", "priority": 10}),
            ],
        )
        r1 = compile_registry(ast_1, _simple_meta())
        r2 = compile_registry(ast_2, _simple_meta())
        assert r1.ast_hash == r2.ast_hash
