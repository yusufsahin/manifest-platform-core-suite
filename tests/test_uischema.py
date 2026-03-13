import pytest
from mpc.kernel.parser import parse
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.tooling.uischema.generator import generate_ui_schema

def test_ui_schema_inference():
    dsl = """
@schema 1
@namespace "crm"

def Kind Customer "Customer Label" {
   required: ["name"]
}

def Customer main "Main" {
    name: "John Doe"
    age: 30
    tags: ["vip", "active"]
    meta: { "source": "web" }
}
"""
    ast = parse(dsl)
    meta = DomainMeta(kinds=[
        KindDef(name="Customer", required_props=["name"])
    ])
    
    res = generate_ui_schema(ast, meta)
    
    # Check "Customer:main" schema
    schema = res.schemas.get("Customer:main")
    assert schema is not None
    assert schema["type"] == "object"
    assert "name" in schema["properties"]
    assert schema["properties"]["name"]["type"] == "string"
    assert schema["properties"]["age"]["type"] == "integer"
    assert schema["properties"]["tags"]["type"] == "array"
    assert schema["properties"]["meta"]["type"] == "object"
    assert "name" in schema["required"]

def test_ui_schema_empty():
    ast = parse("@schema 1\\n@namespace \\"test\\"")
    res = generate_ui_schema(ast, DomainMeta(kinds=[]))
    assert len(res.schemas) == 0
