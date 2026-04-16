from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from mpc.features.form.engine import FormEngine
from mpc.features.form import FORM_CONTRACT_VERSION
from mpc.features.form.kinds import FORM_KINDS
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.kernel.parser import parse
from mpc.tooling.validator.structural import validate_structural


app = FastAPI(title="mpc-runtime", version="0.1.0")


class RuntimeErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False


def raise_runtime_error(code: str, message: str, *, status_code: int = 400, retryable: bool = False) -> None:
    raise HTTPException(status_code=status_code, detail=RuntimeErrorBody(code=code, message=message, retryable=retryable).model_dump())


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Artifact:
    id: str
    tenant_id: str
    status: Literal["draft", "active"]
    version: int
    checksum: str
    created_at: str
    manifest_text: str
    signature: str | None = None


class InMemoryArtifacts:
    def __init__(self) -> None:
        self._items: dict[str, Artifact] = {}
        self._active_by_tenant: dict[str, str] = {}

    def list(self, tenant_id: str) -> list[Artifact]:
        return [a for a in self._items.values() if a.tenant_id == tenant_id]

    def get(self, tenant_id: str, artifact_id: str) -> Artifact:
        a = self._items.get(artifact_id)
        if a is None:
            raise_runtime_error("ARTIFACT_NOT_FOUND", f"Artifact '{artifact_id}' not found.", status_code=404)
        if a.tenant_id != tenant_id:
            raise_runtime_error("TENANT_MISMATCH", "Artifact does not belong to tenant.", status_code=403)
        return a

    def create(self, tenant_id: str, manifest_text: str, signature: str | None = None) -> Artifact:
        artifact_id = uuid.uuid4().hex
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        checksum = uuid.uuid4().hex  # MVP: deterministic checksum is out of scope here
        existing_versions = [a.version for a in self._items.values() if a.tenant_id == tenant_id]
        version = (max(existing_versions) + 1) if existing_versions else 1
        artifact = Artifact(
            id=artifact_id,
            tenant_id=tenant_id,
            status="draft",
            version=version,
            checksum=checksum,
            created_at=created_at,
            manifest_text=manifest_text,
            signature=signature,
        )
        self._items[artifact_id] = artifact
        return artifact

    def update(self, tenant_id: str, artifact_id: str, manifest_text: str, signature: str | None = None) -> Artifact:
        a = self.get(tenant_id, artifact_id)
        updated = Artifact(
            id=a.id,
            tenant_id=a.tenant_id,
            status=a.status,
            version=a.version,
            checksum=uuid.uuid4().hex,
            created_at=a.created_at,
            manifest_text=manifest_text,
            signature=signature,
        )
        self._items[artifact_id] = updated
        return updated

    def activate(self, tenant_id: str, artifact_id: str) -> Artifact:
        a = self.get(tenant_id, artifact_id)
        updated = Artifact(
            id=a.id,
            tenant_id=a.tenant_id,
            status="active",
            version=a.version,
            checksum=a.checksum,
            created_at=a.created_at,
            manifest_text=a.manifest_text,
            signature=a.signature,
        )
        self._items[artifact_id] = updated
        self._active_by_tenant[tenant_id] = artifact_id
        return updated

    def get_active(self, tenant_id: str) -> Artifact:
        artifact_id = self._active_by_tenant.get(tenant_id)
        if not artifact_id:
            raise_runtime_error("ACTIVE_ARTIFACT_REQUIRED", "Tenant has no active artifact.", status_code=409)
        return self.get(tenant_id, artifact_id)


ARTIFACTS = InMemoryArtifacts()


class ArtifactCreateRequest(BaseModel):
    tenant_id: str
    manifest_text: str
    signature: str | None = None


class ArtifactUpdateRequest(BaseModel):
    tenant_id: str
    manifest_text: str
    signature: str | None = None


class ArtifactSummary(BaseModel):
    id: str
    tenant_id: str
    status: str
    version: int
    checksum: str
    created_at: str


class ArtifactDetail(ArtifactSummary):
    manifest_text: str
    signature: str | None = None


@app.get("/api/v1/rule-artifacts")
def list_rule_artifacts(tenant_id: str = Query(...)) -> dict[str, Any]:
    items = [ArtifactSummary(**a.__dict__).model_dump() for a in ARTIFACTS.list(tenant_id)]
    return {"items": items}


@app.get("/api/v1/rule-artifacts/{artifact_id}")
def get_rule_artifact(artifact_id: str, tenant_id: str = Query(...)) -> dict[str, Any]:
    a = ARTIFACTS.get(tenant_id, artifact_id)
    return ArtifactDetail(**a.__dict__).model_dump()


@app.post("/api/v1/rule-artifacts")
def create_rule_artifact(req: ArtifactCreateRequest) -> dict[str, Any]:
    a = ARTIFACTS.create(req.tenant_id, req.manifest_text, signature=req.signature)
    return {"id": a.id, "status": a.status, "checksum": a.checksum}


@app.put("/api/v1/rule-artifacts/{artifact_id}")
def update_rule_artifact(artifact_id: str, req: ArtifactUpdateRequest) -> dict[str, Any]:
    a = ARTIFACTS.update(req.tenant_id, artifact_id, req.manifest_text, signature=req.signature)
    return ArtifactDetail(**a.__dict__).model_dump()


@app.post("/api/v1/rule-artifacts/{artifact_id}/activate")
def activate_rule_artifact(artifact_id: str, tenant_id: str) -> dict[str, Any]:
    a = ARTIFACTS.activate(tenant_id, artifact_id)
    return {"id": a.id, "status": a.status}


class RuntimeSource(BaseModel):
    manifest_text: str | None = None
    artifact_id: str | None = None


class FormPackageRequest(BaseModel):
    tenant_id: str | None = None
    source: RuntimeSource = Field(default_factory=RuntimeSource)
    form_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    actor_roles: list[str] = Field(default_factory=list)
    actor_attrs: dict[str, Any] = Field(default_factory=dict)
    fail_open: bool | None = None
    strict_validation: bool | None = None


@app.post("/api/v1/rule-artifacts/runtime/forms/package")
def form_package(
    req: FormPackageRequest,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    started = _now_ms()
    request_id = idempotency_key or uuid.uuid4().hex
    effective_tenant = (req.tenant_id or x_tenant_id or "").strip() or None

    try:
        # Resolve manifest text
        manifest_text: str | None = None
        if req.source.manifest_text:
            manifest_text = req.source.manifest_text
        elif req.source.artifact_id:
            if not effective_tenant:
                raise_runtime_error("TENANT_MISMATCH", "tenant_id is required when using artifact_id.", status_code=400)
            manifest_text = ARTIFACTS.get(effective_tenant, req.source.artifact_id).manifest_text
        else:
            if not effective_tenant:
                raise_runtime_error("ACTIVE_ARTIFACT_REQUIRED", "tenant_id is required when using tenant active artifact.", status_code=400)
            manifest_text = ARTIFACTS.get_active(effective_tenant).manifest_text

        # Run engine
        ast = parse(manifest_text)
        kind_names = sorted({str(getattr(node, "kind", "") or "") for node in getattr(ast, "defs", [])})
        known = {k.name for k in FORM_KINDS}
        extra = [KindDef(name=name) for name in kind_names if name and name not in known]
        meta = DomainMeta(kinds=[*FORM_KINDS, *extra])

        if bool(req.strict_validation):
            errors = validate_structural(ast, meta)
            if errors:
                message = "; ".join([e.message for e in errors[:5]])
                raise_runtime_error("MANIFEST_INVALID_SHAPE", message or "Manifest failed structural validation.", status_code=400)
        engine = FormEngine(ast=ast, meta=meta)
        package = engine.get_form_package(
            req.form_id,
            req.data,
            actor_roles=req.actor_roles,
            actor_attrs=req.actor_attrs,
            fail_open=True if req.fail_open is None else bool(req.fail_open),
        )

        duration_ms = _now_ms() - started
        return {
            "request_id": request_id,
            "duration_ms": duration_ms,
            "form_contract_version": FORM_CONTRACT_VERSION,
            "json_schema": package.jsonSchema,
            "ui_schema": package.uiSchema,
            "field_state": package.fieldState,
            "validation": package.validation,
            "diagnostics": [],
        }
    except HTTPException:
        raise
    except Exception as e:
        # Keep format Studio expects.
        raise_runtime_error("REMOTE_RUNTIME_500", str(e), status_code=500, retryable=True)

