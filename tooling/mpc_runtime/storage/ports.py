from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


ArtifactStatus = Literal[
    "draft",
    "review",
    "approved",
    "published",
    "active",
    "deprecated",
    "retired",
]


@dataclass(frozen=True)
class StoredArtifact:
    id: str
    tenant_id: str
    status: ArtifactStatus
    version: int
    checksum: str
    created_at: str
    manifest_ref: str
    signature: str | None = None


@dataclass(frozen=True)
class CanaryConfig:
    artifact_id: str
    weight: float


@dataclass(frozen=True)
class ActivationStatusView:
    tenant_id: str
    mode: str
    active_artifact_id: str | None
    previous_active_artifact_id: str | None
    canary: CanaryConfig | None


class BlobStore(Protocol):
    def put_text(self, *, key: str, text: str) -> str:
        """Persist text and return a stable reference (ref string)."""

    def get_text(self, *, ref: str) -> str:
        """Load previously stored text by ref. Raises on missing."""


class RuntimeStore(Protocol):
    # -- artifacts ---------------------------------------------------------
    def create_artifact(self, *, tenant_id: str, manifest_ref: str, checksum: str, signature: str | None, created_at: str) -> StoredArtifact: ...
    def update_artifact(self, *, tenant_id: str, artifact_id: str, manifest_ref: str, checksum: str, signature: str | None) -> StoredArtifact: ...
    def get_artifact(self, *, tenant_id: str, artifact_id: str) -> StoredArtifact: ...
    def list_artifacts(self, *, tenant_id: str) -> list[StoredArtifact]: ...
    def set_artifact_status(self, *, tenant_id: str, artifact_id: str, status: ArtifactStatus) -> StoredArtifact: ...

    # -- pointers ----------------------------------------------------------
    def set_active_artifact(self, *, tenant_id: str, artifact_id: str) -> None: ...
    def get_active_artifact_id(self, *, tenant_id: str) -> str | None: ...
    def set_previous_active_artifact(self, *, tenant_id: str, artifact_id: str | None) -> None: ...
    def get_previous_active_artifact_id(self, *, tenant_id: str) -> str | None: ...

    def set_canary(self, *, tenant_id: str, artifact_id: str | None, weight: float | None) -> None: ...
    def get_canary(self, *, tenant_id: str) -> CanaryConfig | None: ...

    # -- activation mode ---------------------------------------------------
    def set_mode(self, *, tenant_id: str, mode: str) -> None: ...
    def get_mode(self, *, tenant_id: str) -> str: ...

    # -- idempotency -------------------------------------------------------
    def idempotency_get(self, *, tenant_id: str, key: str) -> dict[str, Any] | None: ...
    def idempotency_set(self, *, tenant_id: str, key: str, value: dict[str, Any], ttl_s: int) -> None: ...

    # -- audit -------------------------------------------------------------
    def audit_append(self, *, tenant_id: str, record: dict[str, Any]) -> None: ...
    def audit_list(self, *, tenant_id: str, limit: int = 100, cursor: str | None = None) -> tuple[list[dict[str, Any]], str | None]: ...

    # -- metrics -----------------------------------------------------------
    def metrics_incr(self, *, tenant_id: str, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None: ...

