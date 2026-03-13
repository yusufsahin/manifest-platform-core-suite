import pytest
from mpc.features.acl import ACLEngine
from mpc.kernel.parser import parse
from mpc.kernel.meta.models import DomainMeta, KindDef

def test_acl_rbac_hierarchy():
    dsl = """
@schema 1
@namespace "test"

def ACL r1 {
    action: "read"
    resource: "data"
    roles: ["viewer"]
    effect: "allow"
}
"""
    ast = parse(dsl)
    # Define hierarchy: admin -> editor -> viewer
    hierarchy = {
        "admin": {"editor"},
        "editor": {"viewer"}
    }
    meta = DomainMeta(kinds=[KindDef(name="ACL")])
    engine = ACLEngine(ast=ast, meta=meta, role_hierarchy=hierarchy)
    
    # Admin should inherit viewer role and be allowed
    res = engine.check("read", "data", actor_roles=["admin"])
    assert res.allowed == True
    assert any("Allowed by ACL rule 'r1'" in r.summary for r in res.reasons)

def test_acl_abac_expression():
    dsl = """
@schema 1
@namespace "test"

def ACL a1 {
    action: "write"
    resource: "document"
    condition: { expr: "actor.clearance >= 5" }
    effect: "allow"
}
"""
    ast = parse(dsl)
    meta = DomainMeta(kinds=[KindDef(name="ACL")])
    engine = ACLEngine(ast=ast, meta=meta)
    
    # Low clearance denied (default deny since it doesn't match condition as True)
    res1 = engine.check("write", "document", actor_attrs={"clearance": 3})
    assert res1.allowed == False
    
    # High clearance allowed
    res2 = engine.check("write", "document", actor_attrs={"clearance": 7})
    assert res2.allowed == True
