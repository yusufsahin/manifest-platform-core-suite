"""Tests for UI schema generator (D5)."""
import pytest

from mpc.ast.models import ASTNode, ManifestAST
from mpc.meta.models import DomainMeta, KindDef
from mpc.uischema import generate_ui_schema, UISchemaResult


def _meta() -> DomainMeta:
    return DomainMeta(
        kinds=[
            KindDef(name="Entity", required_props=["name"]),
            KindDef(name="Policy"),
        ],
    )


def _ast() -> ManifestAST:
    return ManifestAST(
        schema_version=1,
        namespace="acme",
        name="test",
        manifest_version="1.0",
        defs=[
            ASTNode(
                kind="Entity",
                id="user",
                name="User Entity",
                properties={
                    "name": "User",
                    "maxAge": 120,
                    "active": True,
                    "tags": ["admin", "user"],
                    "config": {"retries": 3, "timeout": 30},
                },
            ),
            ASTNode(
                kind="Policy",
                id="read_policy",
                properties={
                    "effect": "allow",
                    "priority": 10,
                },
            ),
        ],
    )


class TestGenerateUISchema:
    def test_produces_schemas(self):
        result = generate_ui_schema(_ast(), _meta())
        assert isinstance(result, UISchemaResult)
        assert "Entity:user" in result.schemas
        assert "Policy:read_policy" in result.schemas

    def test_schema_structure(self):
        result = generate_ui_schema(_ast(), _meta())
        schema = result.schemas["Entity:user"]
        assert schema["type"] == "object"
        assert schema["title"] == "User Entity"
        assert schema["x-kind"] == "Entity"
        assert schema["x-id"] == "user"

    def test_required_props(self):
        result = generate_ui_schema(_ast(), _meta())
        schema = result.schemas["Entity:user"]
        assert "name" in schema.get("required", [])

    def test_property_types_inferred(self):
        result = generate_ui_schema(_ast(), _meta())
        props = result.schemas["Entity:user"]["properties"]
        assert props["name"]["type"] == "string"
        assert props["maxAge"]["type"] == "integer"
        assert props["active"]["type"] == "boolean"
        assert props["tags"]["type"] == "array"
        assert props["config"]["type"] == "object"

    def test_array_items(self):
        result = generate_ui_schema(_ast(), _meta())
        tags = result.schemas["Entity:user"]["properties"]["tags"]
        assert tags["items"]["type"] == "string"

    def test_nested_object_properties(self):
        result = generate_ui_schema(_ast(), _meta())
        config = result.schemas["Entity:user"]["properties"]["config"]
        assert "retries" in config["properties"]
        assert config["properties"]["retries"]["type"] == "integer"

    def test_deterministic_key_order(self):
        result1 = generate_ui_schema(_ast(), _meta())
        result2 = generate_ui_schema(_ast(), _meta())
        assert list(result1.schemas.keys()) == list(result2.schemas.keys())

    def test_children_included(self):
        child = ASTNode(kind="Field", id="email", properties={"type": "string"})
        parent = ASTNode(kind="Entity", id="user", properties={"name": "User"}, children=[child])
        ast = ManifestAST(
            schema_version=1, namespace="acme", name="test",
            manifest_version="1.0", defs=[parent],
        )
        meta = DomainMeta(kinds=[KindDef(name="Entity"), KindDef(name="Field")])
        result = generate_ui_schema(ast, meta)
        schema = result.schemas["Entity:user"]
        assert "x-children" in schema
        assert len(schema["x-children"]) == 1

    def test_empty_ast(self):
        ast = ManifestAST(schema_version=1, namespace="a", name="b", manifest_version="1", defs=[])
        result = generate_ui_schema(ast, DomainMeta())
        assert result.schemas == {}
