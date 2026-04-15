"""KMS-based signing and verification adapters.

Requires: boto3 (for AWS), google-cloud-kms (for GCP)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mpc.enterprise.governance.signing import SigningPort, VerificationPort
from mpc.kernel.contracts.models import Error

@dataclass
class AWSKMSSigningPort:
    """AWS KMS signing adapter."""
    key_id: str
    region_name: str | None = None
    
    def sign(self, data: bytes) -> str:
        raise NotImplementedError(
            "AWSKMSSigningPort.sign() requires boto3 and a real AWS KMS integration. "
            "Install boto3 and implement: "
            "client.sign(KeyId=..., Message=..., SigningAlgorithm='RSASSA_PSS_SHA_256')."
        )

    def algorithm(self) -> str:
        return "aws-kms-rsassa-pss-sha-256"

@dataclass
class KMSVerificationPort:
    """Generic KMS verification port."""
    key_id: str
    provider: str # 'aws', 'gcp', 'azure'

    def verify(self, data: bytes, signature: str) -> bool:
        raise NotImplementedError(
            f"KMSVerificationPort ({self.provider!r}) requires a real KMS integration. "
            "Implement this method using the appropriate SDK (boto3, google-cloud-kms, etc.)."
        )
