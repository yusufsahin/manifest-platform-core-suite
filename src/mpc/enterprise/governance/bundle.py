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
from mpc.kernel.canonical.ordering import order_definitions
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


@dataclass(frozen=True)
class ArtifactBundle:
    """Immutable compiled artifact bundle for deployment.

    Contains the compiled registry, provenance, SBOM, attestations,
    and an optional cryptographic signature.
    """
    registry: CompiledRegistry
    metadata: BundleMetadata
    sbom: tuple[SBOMEntry, ...] = field(default_factory=tuple)
    attestations: tuple[Attestation, ...] = field(default_factory=tuple)
    signature: str | None = None

    @property
    def bundle_hash(self) -> str:
        """Compute a deterministic hash of the entire bundle contents."""
        payload = self._to_dict(include_hash=False)
        return stable_hash(payload)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the bundle to a JSON-compatible dict."""
        return self._to_dict(include_hash=True)

    def _to_dict(self, *, include_hash: bool) -> dict[str, Any]:
        """Internal serializer that can omit bundleHash for hashing."""
        compiled_manifest = {
            "defs": order_definitions(
                [
                    {
                        "kind": n.kind,
                        "id": n.id,
                        **({"name": n.name} if n.name is not None else {}),
                        **({"properties": dict(n.properties)} if n.properties else {}),
                    }
                    for n in self.registry.defs_by_id.values()
                ]
            ),
            "dependencyGraph": {
                k: list(v) for k, v in sorted(self.registry.dependency_graph.items(), key=lambda kv: kv[0])
            },
        }

        out = {
            "registry": {
                "astHash": self.registry.ast_hash,
                "metaHash": self.registry.meta_hash,
                "artifactHash": self.registry.artifact_hash,
                "engineVersion": self.registry.engine_version,
            },
            "compiled_manifest": compiled_manifest,
            "metadata": {
                "builder": self.metadata.builder,
                "builtAt": self.metadata.built_at,
                "sourceRef": self.metadata.source_ref,
                "sourceHash": self.metadata.source_hash,
                "engineVersion": self.metadata.engine_version,
                "tags": {k: self.metadata.tags[k] for k in sorted(self.metadata.tags)},
            },
            "sbom": [
                {
                    "name": e.name,
                    "version": e.version,
                    "license": e.license,
                    "hash": e.hash,
                }
                for e in sorted(self.sbom, key=lambda e: e.name)
            ],
            "attestations": [
                {
                    "type": a.type,
                    "issuer": a.issuer,
                    "issuedAt": a.issued_at,
                    "claims": a.claims,
                }
                for a in sorted(self.attestations, key=lambda a: (a.type, a.issuer, a.issued_at))
            ],
            "signature": self.signature,
        }
        if include_hash:
            out["bundleHash"] = stable_hash(out)
        return out

    def verify_integrity(self, expected_hash: str | None = None) -> bool:
        """Verify the bundle's integrity against an expected hash."""
        if expected_hash is None:
            return True
        return self.bundle_hash == expected_hash
