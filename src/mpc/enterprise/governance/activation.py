"""Activation protocol — upload, verify, attest, swap, audit, invalidate.

Per EPIC F3:
  - Atomic activation: new artifact replaces old only on full success
  - Rollback on any step failure
  - Kill switch: policy-off / read-only modes
  - Canary deployment support
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mpc.kernel.contracts.models import Error


class ActivationMode(Enum):
    NORMAL = "normal"
    POLICY_OFF = "policy-off"
    READ_ONLY = "read-only"
    KILL_SWITCH = "kill-switch"


class ActivationStep(Enum):
    UPLOAD = "upload"
    VERIFY = "verify"
    ATTEST = "attest"
    SWAP = "swap"
    AUDIT = "audit"
    INVALIDATE_CACHE = "invalidate_cache"


@dataclass(frozen=True)
class ActivationResult:
    success: bool
    completed_steps: list[str] = field(default_factory=list)
    errors: list[Error] = field(default_factory=list)
    rollback_performed: bool = False
    mode: str = "normal"


@dataclass
class ActivationProtocol:
    """Orchestrate the activation of a new artifact bundle.

    Steps: upload → verify → attest → atomic swap → audit → cache invalidate.
    On failure at any step, previous steps are rolled back.
    """
    mode: ActivationMode = ActivationMode.NORMAL
    _active_artifact_hash: str | None = field(default=None, init=False, repr=False)

    @property
    def active_artifact_hash(self) -> str | None:
        return self._active_artifact_hash

    def is_active(self) -> bool:
        return self.mode == ActivationMode.NORMAL

    def set_kill_switch(self) -> None:
        """Activate kill switch — all policy evaluation returns default-deny."""
        self.mode = ActivationMode.KILL_SWITCH

    def set_read_only(self) -> None:
        """Set read-only mode — mutations are rejected."""
        self.mode = ActivationMode.READ_ONLY

    def set_policy_off(self) -> None:
        """Disable policy evaluation — all requests pass through."""
        self.mode = ActivationMode.POLICY_OFF

    def resume_normal(self) -> None:
        self.mode = ActivationMode.NORMAL

    def activate(
        self,
        bundle_hash: str,
        *,
        verify_fn=None,
        attest_fn=None,
        audit_fn=None,
    ) -> ActivationResult:
        """Execute the activation protocol.

        Each *_fn takes the bundle_hash and returns True on success.
        """
        if self.mode == ActivationMode.KILL_SWITCH:
            return ActivationResult(
                success=False,
                errors=[Error(
                    code="E_GOV_ACTIVATION_FAILED",
                    message="Kill switch is active; activation blocked",
                    severity="error",
                )],
                mode=self.mode.value,
            )

        completed: list[str] = []
        errors: list[Error] = []

        # Step 1: Upload (implicit — caller provides bundle_hash)
        completed.append(ActivationStep.UPLOAD.value)

        # Step 2: Verify
        if verify_fn is not None:
            try:
                if not verify_fn(bundle_hash):
                    return self._rollback(completed, Error(
                        code="E_GOV_SIGNATURE_INVALID",
                        message="Bundle verification failed",
                        severity="error",
                    ))
            except Exception as exc:
                return self._rollback(completed, Error(
                    code="E_GOV_SIGNATURE_INVALID",
                    message=str(exc),
                    severity="error",
                ))
        completed.append(ActivationStep.VERIFY.value)

        # Step 3: Attest
        if attest_fn is not None:
            try:
                if not attest_fn(bundle_hash):
                    return self._rollback(completed, Error(
                        code="E_GOV_ATTESTATION_MISSING",
                        message="Attestation check failed",
                        severity="error",
                    ))
            except Exception as exc:
                return self._rollback(completed, Error(
                    code="E_GOV_ATTESTATION_MISSING",
                    message=str(exc),
                    severity="error",
                ))
        completed.append(ActivationStep.ATTEST.value)

        # Step 4: Atomic swap
        prev_hash = self._active_artifact_hash
        self._active_artifact_hash = bundle_hash
        completed.append(ActivationStep.SWAP.value)

        # Step 5: Audit
        if audit_fn is not None:
            try:
                if not audit_fn(bundle_hash):
                    # Late stage failure - ROLLBACK SWAP
                    self._active_artifact_hash = prev_hash
                    return self._rollback(completed, Error(
                        code="E_GOV_AUDIT_FAILED",
                        message="Post-activation audit failed, rolled back.",
                        severity="error",
                    ))
            except Exception as exc:
                self._active_artifact_hash = prev_hash
                return self._rollback(completed, Error(
                    code="E_GOV_AUDIT_FAILED",
                    message=f"Audit error: {exc}",
                    severity="error",
                ))
        completed.append(ActivationStep.AUDIT.value)

        # Step 6: Cache invalidation (consuming app responsibility)
        completed.append(ActivationStep.INVALIDATE_CACHE.value)

        return ActivationResult(
            success=True,
            completed_steps=completed,
            mode=self.mode.value,
        )

    def _rollback(
        self, completed: list[str], error: Error
    ) -> ActivationResult:
        return ActivationResult(
            success=False,
            completed_steps=completed,
            errors=[error],
            rollback_performed=True,
            mode=self.mode.value,
        )
