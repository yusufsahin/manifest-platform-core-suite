from mpc.enterprise.governance.managed_activation import ManagedActivation
from mpc.features.routing.canary import CanaryRouter
from mpc.features.workflow.fsm import WorkflowEngine, FSMState, Transition
from mpc.enterprise.governance.registry import VersionRegistry

def test_quorum_activation():
    # Setup engine
    engine = WorkflowEngine(
        states={"Draft": FSMState("Draft", is_initial=True), "Staging": FSMState("Staging")},
        transitions=[Transition(from_state="Draft", to_state="Staging", on="PROMOTE")],
        initial_state="Draft"
    )
    engine.activate()
    
    # Requirement: 1 Security, 1 Legal
    activation = ManagedActivation(
        engine=engine,
        manifest_id="m1",
        quorum_spec={"Security": 1, "Legal": 1}
    )
    
    # Approve as Security
    activation.approve("user1", "Security")
    res = activation.request_activation()
    assert res.decision.allow is False # Missing Legal
    
    # Approve as Legal
    activation.approve("user2", "Legal")
    res = activation.request_activation()
    assert res.decision.allow is True
    assert engine.current_state == "Staging"

def test_segmented_canary():
    router = CanaryRouter(
        stable_hash="v1",
        canary_hash="v2",
        weight=0.0, # Kill random traffic
        segments={"region": ["US"]}
    )
    
    # US actor should get v2
    assert router.resolve_version(attributes={"region": "US"}) == "v2"
    
    # EU actor should get v1 (weight is 0)
    assert router.resolve_version(attributes={"region": "EU"}) == "v1"

def test_registry_promotion():
    reg = VersionRegistry()
    reg.register_stable("crm", "m-0", "h-0")
    reg.register_canary("crm", "m-1", "h-1")
    
    reg.promote_canary("crm")
    versions = reg.get_versions("crm")
    assert versions["stable"].hash == "h-1"
    assert "canary" not in versions

if __name__ == "__main__":
    test_quorum_activation()
    test_segmented_canary()
    test_registry_promotion()
    print("Phase 12 verification SUCCESS")
