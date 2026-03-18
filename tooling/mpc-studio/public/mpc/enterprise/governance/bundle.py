"""Artifact bundle — compiled manifest + provenance + sbom + attestations + signature.

Per EPIC F1:
  - Immutable compiled artifact
  - Provenance metadata (who built, when, from what)
  - SBOM (software bill of materials) for dependencies
  - Attestations for compliance checks
  - Signature slot for verification
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from mpc.kernel.canonical import stable_hash
from mpc.tooling.registry.compiler import CompiledRegistry


@dataclass(frozen=True)
class BundleMetadata:
    """Provenance and build metadata for an artifact bundle."""
    builder: str
    built_at: str
    source_ref: str | None = None
    source_hash: str | None = None
    engine_version: str = "0.1.0"
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Attestation:
    """A compliance or verification attestation."""
    type: str
    issuer: str
    issued_at: str
    claims: dict[str, Any] = field(default_factory=dict)
    signature: str | None = None


@dataclass(frozen=True)
class SBOMEntry:
    """A single dependency in the software bill of materials."""
    name: str
    version: str
    license: str | None = None
    hash: str | None = None


@dataclass
class ArtifactBundle:
    """Immutable compiled artifact bundle for deployment.

    Contains the compiled registry, provenance, SBOM, attestations,
    and an optional cryptographic signature.
    """
    registry: CompiledRegistry
    metadata: BundleMetadata
    sbom: list[SBOMEntry] = field(default_factory=list)
    attestations: list[Attestation] = field(default_factory=list)
    signature: str | None = None

    @property
    def bundle_hash(self) -> str:
        """Compute a deterministic hash of the entire bundle contents."""
        payload = {
            "artifactHash": self.registry.artifact_hash,
            "metadata": {
                "builder": self.metadata.builder,
                "builtAt": self.metadata.built_at,
                "engineVersion": self.metadata.engine_version,
            },
            "sbom": [
                {"name": e.name, "version": e.version}
                for e in sorted(self.sbom, key=lambda e: e.name)
            ],
            "attestationCount": len(self.attestations),
        }
        return stable_hash(payload)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the bundle to a JSON-compatible dict."""
        return {
            "registry": {
                "astHash": self.registry.ast_hash,
                "metaHash": self.registry.meta_hash,
                "artifactHash": self.registry.artifact_hash,
                "engineVersion": self.registry.engine_version,
            },
            "metadata": {
                "builder": self.metadata.builder,
                "builtAt": self.metadata.built_at,
                "sourceRef": self.metadata.source_ref,
                "sourceHash": self.metadata.source_hash,
                "engineVersion": self.metadata.engine_version,
                "tags": self.metadata.tags,
            },
            "sbom": [
                {
                    "name": e.name,
                    "version": e.version,
                    "license": e.license,
                    "hash": e.hash,
                }
                for e in self.sbom
            ],
            "attestations": [
                {
                    "type": a.type,
                    "issuer": a.issuer,
                    "issuedAt": a.issued_at,
                    "claims": a.claims,
                }
                for a in self.attestations
            ],
            "signature": self.signature,
            "bundleHash": self.bundle_hash,
        }

    def verify_integrity(self, expected_hash: str | None = None) -> bool:
        """Verify the bundle's integrity against an expected hash."""
        if expected_hash is None:
            return True
        return self.bundle_hash == expected_hash
