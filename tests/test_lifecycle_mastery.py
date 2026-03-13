import pytest
import random
from mpc.features.routing.canary import CanaryRouter
from mpc.enterprise.governance.managed_activation import ManagedActivation
from mpc.features.workflow.fsm import WorkflowEngine, FSMState, Transition

def test_canary_distribution():
    router = CanaryRouter(stable_hash="v1", canary_hash="v2", weight=0.2)
    
    results = {"v1": 0, "v2": 0}
    for i in range(1000):
        ver = router.resolve_version(actor_id=f"user-{i}")
        results[ver] += 1
        
    # v2 should be roughly 200 (+/- jitter if not sticky, but sticky is better)
    # With actor_id, it is deterministic per user.
    print(f"\n[CANARY] v1: {results['v1']} | v2: {results['v2']}")
    assert 150 < results["v2"] < 250

def test_managed_activation_flow():
    # Simple setup for activation workflow
    states = {
        "Draft": FSMState("Draft", is_initial=True),
        "Staging": FSMState("Staging"),
        "Live": FSMState("Live", is_final=True)
    }
    transitions = [
        Transition("Draft", "Staging", on="PROMOTE", auth_roles=["dev"]),
        Transition("Staging", "Live", on="DEPLOY", auth_roles=["mgr"])
    ]
    engine = WorkflowEngine(states=states, transitions=transitions, active_states={"Draft"})
    
    managed = ManagedActivation(engine=engine, manifest_id="m1")
    
    # 1. Promote to Staging (requires 'dev')
    managed.approve("dev")
    res = managed.request_activation()
    assert "Staging" in res.new_state
    
    # 2. Deploy to Live (requires 'mgr')
    res_fail = managed.request_activation() # Fails because no 'mgr' approval
    managed.approve("mgr")
    res_ok = managed.request_activation()
    assert "Live" in res_ok.new_state
