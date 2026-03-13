import pytest
from mpc.features.compose import compose_decisions
from mpc.kernel.contracts.models import Decision, Reason
from mpc.enterprise.governance.signing import HMACSigningPort
from mpc.enterprise.governance.activation import ActivationProtocol

def test_composition_strategies():
    d1 = Decision(allow=True, reasons=[Reason(code="R1", summary="S1")])
    d2 = Decision(allow=False, reasons=[Reason(code="R2", summary="S2")])
    
    # first-applicable should take d1
    res_fa = compose_decisions([d1, d2], strategy="first-applicable")
    assert res_fa.allow == True
    assert res_fa.reasons[0].code == "R1"
    
    # only-one should fail if both have reasons
    res_oo = compose_decisions([d1, d2], strategy="only-one")
    assert res_oo.allow == False
    assert res_oo.reasons[0].code == "E_COMPOSE_CONFLICT"

def test_hmac_signing():
    port = HMACSigningPort("secret-key")
    data = b"manifest-content"
    sig = port.sign(data)
    assert port.verify(data, sig) == True
    assert port.verify(data, "wrong-sig") == False

def test_activation_rollback_on_audit():
    proto = ActivationProtocol()
    proto._active_artifact_hash = "v1"
    
    def fail_audit(_h): return False # audit fails
    
    res = proto.activate("v2", audit_fn=fail_audit)
    
    assert res.success == False
    assert res.rollback_performed == True
    # Should have swapped back to v1
    assert proto.active_artifact_hash == "v1"
