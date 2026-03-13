import pytest
from mpc.features.policy import PolicyEngine
from mpc.kernel.parser import parse
from mpc.kernel.meta.models import DomainMeta, KindDef

def test_advanced_policy_expression():
    dsl = """
@schema 1
@namespace "test"
@name "policy_logic"

def Policy admin_only "Admin Only" {
    match: { expr: "event.user.role == 'admin'" }
    effect: "allow"
}

def Policy block_banned "Block Banned" {
    match: { user_id: 666 }
    effect: "deny"
}
"""
    ast = parse(dsl)
    meta = DomainMeta(kinds=[KindDef(name="Policy")])
    engine = PolicyEngine(ast=ast, meta=meta)
    
    # Test case 1: Admin allowed by expression
    res1 = engine.evaluate({"user": {"role": "admin"}, "user_id": 1})
    assert res1.allow == True
    
    # Test case 2: Normal user not matching admin policy (default logic might be tricky here depending on other policies)
    # If no policy matches and no global deny, it stays True?
    # Actually our engine iterates all policies. If none match, allow=True (default).
    res2 = engine.evaluate({"user": {"role": "user"}})
    assert res2.allow == True
    
    # Test case 3: Banned user (static match)
    res3 = engine.evaluate({"user": {"role": "user"}, "user_id": 666})
    assert res3.allow == False
    assert any("Block Banned" in r.summary for r in res3.reasons)

def test_policy_deny_wins():
    dsl = """
@schema 1
@namespace "test"

def Policy p1 { effect: "allow", priority: 1 }
def Policy p2 { effect: "deny", priority: 10 }
"""
    ast = parse(dsl)
    meta = DomainMeta(kinds=[KindDef(name="Policy")])
    engine = PolicyEngine(ast=ast, meta=meta)
    
    # Deny wins because it's higher priority OR just because it exists
    res = engine.evaluate({})
    assert res.allow == False
