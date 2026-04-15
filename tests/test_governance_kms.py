from mpc.enterprise.governance.kms import AWSKMSSigningPort, KMSVerificationPort

def test_kms_signing_placeholder():
    # Placeholder tests for Phase 11 KMS adapters
    signer = AWSKMSSigningPort(key_id="key-123", region_name="us-east-1")
    assert signer.algorithm() == "aws-kms-rsassa-pss-sha-256"
    import pytest
    with pytest.raises(NotImplementedError):
        signer.sign(b"hello")
    
    verifier = KMSVerificationPort(key_id="key-123", provider="aws")
    with pytest.raises(NotImplementedError):
        verifier.verify(b"hello", "sig")

