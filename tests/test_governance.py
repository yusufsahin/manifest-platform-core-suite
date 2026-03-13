"""Tests for enterprise governance (Epic F) — bundles, signing, activation, quotas."""
import pytest
from typing import Any

from mpc.ast.models import ASTNode, ManifestAST
from mpc.meta.models import DomainMeta, KindDef
from mpc.registry.compiler import compile_registry
from mpc.governance import (
    ArtifactBundle,
    BundleMetadata,
    SigningPort,
    VerificationPort,
    ActivationProtocol,
    ActivationResult,
    QuotaEnforcer,
    QuotaLimits,
)
from mpc.governance.bundle import Attestation, SBOMEntry
from mpc.governance.activation import ActivationMode


def _compiled():
    ast = ManifestAST(
        schema_version=1, namespace="acme", name="test",
        manifest_version="1.0",
        defs=[ASTNode(kind="Entity", id="user", properties={"name": "User"})],
    )
    meta = DomainMeta(kinds=[KindDef(name="Entity")])
    return compile_registry(ast, meta)


class TestArtifactBundle:
    def test_create_bundle(self):
        reg = _compiled()
        meta = BundleMetadata(builder="ci", built_at="2026-01-01T00:00:00Z")
        bundle = ArtifactBundle(registry=reg, metadata=meta)
        assert bundle.bundle_hash
        assert isinstance(bundle.bundle_hash, str)
        assert len(bundle.bundle_hash) == 64

    def test_to_dict(self):
        reg = _compiled()
        meta = BundleMetadata(builder="ci", built_at="2026-01-01T00:00:00Z")
        bundle = ArtifactBundle(
            registry=reg, metadata=meta,
            sbom=[SBOMEntry(name="mpc", version="0.1.0", license="MIT")],
            attestations=[Attestation(type="ci", issuer="github", issued_at="2026-01-01")],
        )
        d = bundle.to_dict()
        assert d["registry"]["artifactHash"] == reg.artifact_hash
        assert d["metadata"]["builder"] == "ci"
        assert len(d["sbom"]) == 1
        assert len(d["attestations"]) == 1
        assert d["bundleHash"] == bundle.bundle_hash

    def test_deterministic_hash(self):
        reg = _compiled()
        meta = BundleMetadata(builder="ci", built_at="2026-01-01T00:00:00Z")
        b1 = ArtifactBundle(registry=reg, metadata=meta)
        b2 = ArtifactBundle(registry=reg, metadata=meta)
        assert b1.bundle_hash == b2.bundle_hash

    def test_verify_integrity_no_expected_hash(self):
        reg = _compiled()
        meta = BundleMetadata(builder="ci", built_at="2026-01-01T00:00:00Z")
        bundle = ArtifactBundle(registry=reg, metadata=meta)
        assert bundle.verify_integrity() is True

    def test_verify_integrity_correct_hash(self):
        reg = _compiled()
        meta = BundleMetadata(builder="ci", built_at="2026-01-01T00:00:00Z")
        bundle = ArtifactBundle(registry=reg, metadata=meta)
        assert bundle.verify_integrity(bundle.bundle_hash) is True

    def test_verify_integrity_wrong_hash(self):
        reg = _compiled()
        meta = BundleMetadata(builder="ci", built_at="2026-01-01T00:00:00Z")
        bundle = ArtifactBundle(registry=reg, metadata=meta)
        assert bundle.verify_integrity("wronghash") is False


class TestSigningPort:
    def test_sign_and_verify(self):
        class MockSigner:
            def sign(self, data: bytes) -> str:
                return f"sig:{data[:8].hex()}"
            def algorithm(self) -> str:
                return "mock"

        class MockVerifier:
            def verify(self, data: bytes, signature: str) -> bool:
                return signature == f"sig:{data[:8].hex()}"

        signer = MockSigner()
        verifier = MockVerifier()
        data = b"bundle contents"
        sig = signer.sign(data)
        assert verifier.verify(data, sig) is True
        assert verifier.verify(data, "bad") is False

    def test_protocol_check(self):
        class MySigner:
            def sign(self, data: bytes) -> str:
                return ""
            def algorithm(self) -> str:
                return "none"

        assert isinstance(MySigner(), SigningPort)


class TestActivationProtocol:
    def test_successful_activation(self):
        proto = ActivationProtocol()
        result = proto.activate("hash123")
        assert result.success is True
        assert "upload" in result.completed_steps
        assert "swap" in result.completed_steps
        assert proto.active_artifact_hash == "hash123"

    def test_verify_failure_rollback(self):
        proto = ActivationProtocol()
        result = proto.activate("hash123", verify_fn=lambda h: False)
        assert result.success is False
        assert result.rollback_performed is True
        assert any(e.code == "E_GOV_SIGNATURE_INVALID" for e in result.errors)

    def test_attest_failure_rollback(self):
        proto = ActivationProtocol()
        result = proto.activate("hash123", attest_fn=lambda h: False)
        assert result.success is False
        assert result.rollback_performed is True
        assert any(e.code == "E_GOV_ATTESTATION_MISSING" for e in result.errors)

    def test_kill_switch(self):
        proto = ActivationProtocol()
        proto.set_kill_switch()
        assert proto.mode == ActivationMode.KILL_SWITCH
        result = proto.activate("hash123")
        assert result.success is False
        assert any(e.code == "E_GOV_ACTIVATION_FAILED" for e in result.errors)

    def test_mode_transitions(self):
        proto = ActivationProtocol()
        assert proto.is_active() is True

        proto.set_read_only()
        assert proto.mode == ActivationMode.READ_ONLY
        assert proto.is_active() is False

        proto.set_policy_off()
        assert proto.mode == ActivationMode.POLICY_OFF

        proto.resume_normal()
        assert proto.is_active() is True

    def test_sequential_activations(self):
        proto = ActivationProtocol()
        proto.activate("v1")
        assert proto.active_artifact_hash == "v1"
        proto.activate("v2")
        assert proto.active_artifact_hash == "v2"


class TestQuotaEnforcer:
    def test_within_limits(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits(max_parse_ops=10))
        for _ in range(10):
            assert enforcer.check_parse() is None

    def test_exceeds_parse_limit(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits(max_parse_ops=2))
        assert enforcer.check_parse() is None
        assert enforcer.check_parse() is None
        error = enforcer.check_parse()
        assert error is not None
        assert error.code == "E_QUOTA_EXCEEDED"
        assert "parse" in error.message.lower()

    def test_exceeds_compile_limit(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits(max_compile_ops=1))
        assert enforcer.check_compile() is None
        error = enforcer.check_compile()
        assert error is not None
        assert error.code == "E_QUOTA_EXCEEDED"

    def test_exceeds_eval_limit(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits(max_eval_ops=1))
        assert enforcer.check_eval() is None
        error = enforcer.check_eval()
        assert error is not None

    def test_node_limit(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits(max_manifest_nodes=5))
        assert enforcer.check_nodes(3) is None
        error = enforcer.check_nodes(5)
        assert error is not None
        assert error.code == "E_QUOTA_EXCEEDED"

    def test_reset(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits(max_parse_ops=1))
        enforcer.check_parse()
        assert enforcer.check_parse() is not None
        enforcer.reset()
        assert enforcer.check_parse() is None

    def test_usage_tracking(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits())
        enforcer.check_parse(5)
        enforcer.check_compile(2)
        usage = enforcer.usage
        assert usage["parse"] == 5
        assert usage["compile"] == 2

    def test_exceeds_defs_limit(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits(max_total_defs=3))
        assert enforcer.check_defs(3) is None
        error = enforcer.check_defs(1)
        assert error is not None
        assert error.code == "E_QUOTA_EXCEEDED"

    def test_usage_nodes_and_defs(self):
        enforcer = QuotaEnforcer(limits=QuotaLimits())
        enforcer.check_nodes(10)
        enforcer.check_defs(4)
        assert enforcer.usage["nodes"] == 10
        assert enforcer.usage["defs"] == 4


class TestActivationExceptions:
    def test_verify_exception_triggers_rollback(self):
        proto = ActivationProtocol()
        def boom(h: str) -> bool:
            raise RuntimeError("verify service down")
        result = proto.activate("hash123", verify_fn=boom)
        assert result.success is False
        assert result.rollback_performed is True
        assert any(e.code == "E_GOV_SIGNATURE_INVALID" for e in result.errors)
        assert "verify service down" in result.errors[0].message

    def test_attest_exception_triggers_rollback(self):
        proto = ActivationProtocol()
        def boom(h: str) -> bool:
            raise ValueError("attestation service unavailable")
        result = proto.activate("hash123", attest_fn=boom)
        assert result.success is False
        assert result.rollback_performed is True
        assert any(e.code == "E_GOV_ATTESTATION_MISSING" for e in result.errors)

    def test_audit_exception_does_not_fail_activation(self):
        proto = ActivationProtocol()
        def bad_audit(h: str) -> None:
            raise RuntimeError("audit log unavailable")
        result = proto.activate("hash123", audit_fn=bad_audit)
        assert result.success is True
        assert proto.active_artifact_hash == "hash123"
