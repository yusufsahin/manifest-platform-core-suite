import os
import json
import pytest
from mpc.features.workflow.file_store import JSONFileStateStore
from mpc.features.expr import ExprEngine
from mpc.kernel.meta.models import DomainMeta

def test_file_store_persistence():
    test_file = "test_state.json"
    if os.path.exists(test_file):
        os.remove(test_file)
        
    store1 = JSONFileStateStore(test_file)
    store1.set_global_config("key1", "val1")
    
    # New instance should load the same data
    store2 = JSONFileStateStore(test_file)
    assert store2.get_global_config("key1") == "val1"
    
    os.remove(test_file)

def test_expr_logging():
    logged = []
    def log_cb(data):
        logged.append(data)
        
    meta = DomainMeta(kinds=[])
    engine = ExprEngine(meta=meta, log_callback=log_cb)
    
    engine.evaluate("1 + 1")
    assert len(logged) == 1
    assert logged[0]["expr"] == "1 + 1"
    assert logged[0]["result"] == 2

def test_multi_sig_persistence_sim():
    test_file = "test_multisig.json"
    if os.path.exists(test_file):
        os.remove(test_file)
        
    store = JSONFileStateStore(test_file)
    bundle_id = "bundle-abc"
    
    # Session 1: QA approves
    approvals = store.get_global_config(f"approvals_{bundle_id}") or []
    approvals.append("qa-lead")
    store.set_global_config(f"approvals_{bundle_id}", approvals)
    
    # Session 2: Security approves
    store2 = JSONFileStateStore(test_file)
    approvals2 = store2.get_global_config(f"approvals_{bundle_id}") or []
    approvals2.append("security-officer")
    store2.set_global_config(f"approvals_{bundle_id}", approvals2)
    
    # Final check
    final_approvals = JSONFileStateStore(test_file).get_global_config(f"approvals_{bundle_id}")
    assert "qa-lead" in final_approvals
    assert "security-officer" in final_approvals
    
    os.remove(test_file)
