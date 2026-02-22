from mpc.ast import ManifestAST, ASTNode, normalize


class TestASTModel:
    def test_create_node(self):
        node = ASTNode(kind="Policy", id="p1", name="AllowEdit")
        assert node.kind == "Policy"
        assert node.id == "p1"
        assert node.properties == {}

    def test_node_with_properties(self):
        node = ASTNode(
            kind="Policy",
            id="p1",
            properties={"effect": "allow", "priority": 10},
        )
        assert node.properties["effect"] == "allow"

    def test_manifest_ast(self):
        ast = ManifestAST(
            schema_version=1,
            namespace="acme",
            name="rules",
            manifest_version="1.0.0",
            defs=[ASTNode(kind="Policy", id="p1")],
        )
        assert len(ast.defs) == 1
        assert ast.namespace == "acme"


class TestNormalize:
    def test_basic(self):
        raw = {
            "schemaVersion": 1,
            "namespace": "acme",
            "name": "rules",
            "manifestVersion": "1.0.0",
            "defs": [
                {"kind": "Policy", "id": "p1", "name": "AllowEdit", "effect": "allow"},
            ],
        }
        ast = normalize(raw)
        assert ast.schema_version == 1
        assert ast.namespace == "acme"
        assert len(ast.defs) == 1
        assert ast.defs[0].kind == "Policy"
        assert ast.defs[0].properties["effect"] == "allow"
        assert "kind" not in ast.defs[0].properties
        assert "id" not in ast.defs[0].properties

    def test_nested_children(self):
        raw = {
            "schemaVersion": 1,
            "namespace": "ns",
            "name": "n",
            "manifestVersion": "1.0.0",
            "defs": [
                {
                    "kind": "Group",
                    "id": "g1",
                    "children": [{"kind": "Policy", "id": "p1"}],
                }
            ],
        }
        ast = normalize(raw)
        assert len(ast.defs[0].children) == 1
        assert ast.defs[0].children[0].kind == "Policy"

    def test_defaults(self):
        ast = normalize({})
        assert ast.schema_version == 1
        assert ast.namespace == ""
        assert ast.defs == []
