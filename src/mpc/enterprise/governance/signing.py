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


def verify_jwt_payload_hash(
    *,
    token: str,
    payload_hash: str,
    jwks: dict[str, Any],
    algorithms: list[str] | None = None,
) -> SignatureResult:
    """Verify a JWT/JWS signature against a JWKS and ensure payload_hash matches.

    Contract:
    - token MUST include a `kid` header
    - token payload MUST include `payload_hash`
    """
    try:
        import jwt  # PyJWT
        from jwt.algorithms import RSAAlgorithm

        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            return SignatureResult(
                valid=False,
                error=Error(code="E_GOV_SIGNATURE_INVALID", message="Missing kid in JWT header", severity="error"),
            )
        keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
        key_obj = None
        for k in keys:
            if isinstance(k, dict) and k.get("kid") == kid:
                key_obj = k
                break
        if not key_obj:
            return SignatureResult(
                valid=False,
                error=Error(code="E_GOV_SIGNATURE_INVALID", message=f"Unknown kid '{kid}'", severity="error"),
            )
        public_key = RSAAlgorithm.from_jwk(_json_dumps(key_obj))
        decoded = jwt.decode(
            token,
            key=public_key,
            algorithms=algorithms or ["RS256"],
            options={"verify_aud": False},
        )
        if decoded.get("payload_hash") != payload_hash:
            return SignatureResult(
                valid=False,
                error=Error(code="E_GOV_SIGNATURE_INVALID", message="payload_hash mismatch", severity="error"),
            )
        return SignatureResult(valid=True, algorithm=str(header.get("alg") or "RS256"), signer=str(kid))
    except Exception as exc:
        return SignatureResult(
            valid=False,
            error=Error(code="E_GOV_SIGNATURE_INVALID", message=str(exc), severity="error"),
        )


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, separators=(",", ":"), sort_keys=True)
