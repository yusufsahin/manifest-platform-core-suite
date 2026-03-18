"""Signing and verification ports — pluggable algorithm support.

Per EPIC F2:
  - SigningPort: interface for signing artifact bundles
  - VerificationPort: interface for verifying signatures
  - Algorithm-agnostic: consuming app provides the implementation
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from mpc.kernel.contracts.models import Error


@runtime_checkable
class SigningPort(Protocol):
    """Interface for signing artifact data.

    Consuming apps implement this with their chosen algorithm
    (RSA, ECDSA, Ed25519, etc.).
    """
    def sign(self, data: bytes) -> str:
        """Sign *data* and return the signature as a string (e.g. base64)."""
        ...

    def algorithm(self) -> str:
        """Return the algorithm identifier (e.g. 'ed25519', 'rsa-sha256')."""
        ...

@runtime_checkable
class VerificationPort(Protocol):
    """Interface for verifying signatures."""

    def verify(self, data: bytes, signature: str) -> bool:
        """Return True if *signature* is valid for *data*."""
        ...


@dataclass
class HMACSigningPort:
    """Standard HMAC-SHA256 signature implementation."""
    secret: str

    def sign(self, data: bytes) -> str:
        h = hmac.new(self.secret.encode(), data, hashlib.sha256)
        return h.hexdigest()

    def verify(self, data: bytes, signature: str) -> bool:
        expected = self.sign(data)
        return hmac.compare_digest(expected, signature)

    def algorithm(self) -> str:
        return "hmac-sha256"


@dataclass(frozen=True)
class SignatureResult:
    valid: bool
    algorithm: str | None = None
    signer: str | None = None
    error: Error | None = None


def sign_bundle_data(data: bytes, port: SigningPort) -> str:
    """Sign bundle data using the provided port."""
    return port.sign(data)


def verify_bundle_data(
    data: bytes, signature: str, port: VerificationPort
) -> SignatureResult:
    """Verify a bundle signature using the provided port."""
    try:
        valid = port.verify(data, signature)
        return SignatureResult(valid=valid)
    except Exception as exc:
        return SignatureResult(
            valid=False,
            error=Error(
                code="E_GOV_SIGNATURE_INVALID",
                message=str(exc),
                severity="error",
            ),
        )
