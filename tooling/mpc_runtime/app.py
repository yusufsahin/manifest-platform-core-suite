from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from mpc.enterprise.governance.activation import ActivationMode, ActivationProtocol
from mpc.enterprise.governance.quotas import QuotaEnforcer, QuotaLimits
from mpc.features.form.engine import FormEngine
from mpc.features.form import FORM_CONTRACT_VERSION
from mpc.features.form.kinds import FORM_KINDS
from mpc.kernel.canonical.hash import stable_hash
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

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


AUDIT_LOGS: dict[str, list[dict[str, Any]]] = {}


def _audit_record(
    tenant_id: str,
    *,
    action: str,
    request_id: str | None = None,
    artifact_id: str | None = None,
    artifact_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    record = {
        "timestamp": _now_iso(),
        "action": action,
        "request_id": request_id,
        "artifact_id": artifact_id,
        "artifact_hash": artifact_hash,
        "details": details or {},
    }
    AUDIT_LOGS.setdefault(tenant_id, []).append(record)


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
            raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{artifact_id}' not found.", status_code=404)
        if a.tenant_id != tenant_id:
            raise_runtime_error("E_RUNTIME_FORBIDDEN", "Artifact does not belong to tenant.", status_code=403)
        return a

    def create(self, tenant_id: str, manifest_text: str, signature: str | None = None) -> Artifact:
        artifact_id = uuid.uuid4().hex
        created_at = _now_iso()
        checksum = stable_hash(manifest_text)
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
            checksum=stable_hash(manifest_text),
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
            raise_runtime_error("E_RUNTIME_ACTIVE_REQUIRED", "Tenant has no active artifact.", status_code=409)
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
    _audit_record(
        req.tenant_id,
        action="artifact_create",
        artifact_id=a.id,
        artifact_hash=a.checksum,
    )
    return {"id": a.id, "status": a.status, "checksum": a.checksum}


@app.put("/api/v1/rule-artifacts/{artifact_id}")
def update_rule_artifact(artifact_id: str, req: ArtifactUpdateRequest) -> dict[str, Any]:
    a = ARTIFACTS.update(req.tenant_id, artifact_id, req.manifest_text, signature=req.signature)
    return ArtifactDetail(**a.__dict__).model_dump()


@app.post("/api/v1/rule-artifacts/{artifact_id}/activate")
def activate_rule_artifact(artifact_id: str, tenant_id: str) -> dict[str, Any]:
    a = ARTIFACTS.activate(tenant_id, artifact_id)
    _audit_record(tenant_id, action="artifact_activate_legacy", artifact_id=a.id, artifact_hash=a.checksum)
    return {"id": a.id, "status": a.status}


# ---------------------------------------------------------------------------
# Enterprise activation surface (Runtime API)
# ---------------------------------------------------------------------------


@dataclass
class TenantActivationState:
    tenant_id: str
    protocol: ActivationProtocol
    mode: ActivationMode = ActivationMode.NORMAL
    canary_artifact_id: str | None = None
    canary_weight: float = 0.0
    previous_active_artifact_id: str | None = None
    # (idempotency_key -> response payload)
    idempotency: dict[str, dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.idempotency is None:
            self.idempotency = {}

    @property
    def active_artifact_id(self) -> str | None:
        return self.protocol.active_artifact_hash


TENANT_ACTIVATION: dict[str, TenantActivationState] = {}


def _activation_state(tenant_id: str) -> TenantActivationState:
    state = TENANT_ACTIVATION.get(tenant_id)
    if state is None:
        state = TenantActivationState(tenant_id=tenant_id, protocol=ActivationProtocol())
        TENANT_ACTIVATION[tenant_id] = state
    return state

def _ensure_mutation_allowed(tenant_id: str, state: TenantActivationState) -> None:
    if state.mode == ActivationMode.KILL_SWITCH:
        raise_runtime_error("E_GOV_ACTIVATION_FAILED", "Kill switch is active; mutation blocked", status_code=409)
    if state.mode == ActivationMode.READ_ONLY:
        raise_runtime_error("E_GOV_ACTIVATION_FAILED", "Read-only mode is active; mutation blocked", status_code=409)


class ActivationRequest(BaseModel):
    artifact_id: str
    enterprise_mode: bool = False
    verification: dict[str, Any] | None = None


class CanaryRequest(BaseModel):
    artifact_id: str
    weight: float = Field(default=0.1, ge=0.0, le=1.0)


class ModeRequest(BaseModel):
    mode: Literal["normal", "policy-off", "read-only", "kill-switch"]


@app.get("/api/v1/tenants/{tenant_id}/activation/status")
def get_activation_status(tenant_id: str) -> dict[str, Any]:
    state = _activation_state(tenant_id)
    active_id = ARTIFACTS._active_by_tenant.get(tenant_id)  # MVP in-memory
    active = ARTIFACTS.get(tenant_id, active_id) if active_id else None
    canary = ARTIFACTS.get(tenant_id, state.canary_artifact_id) if state.canary_artifact_id else None
    previous = ARTIFACTS.get(tenant_id, state.previous_active_artifact_id) if state.previous_active_artifact_id else None
    return {
        "tenant_id": tenant_id,
        "mode": state.mode.value,
        "active": (ArtifactSummary(**active.__dict__).model_dump() if active else None),
        "previous_active": (ArtifactSummary(**previous.__dict__).model_dump() if previous else None),
        "canary": (ArtifactSummary(**canary.__dict__).model_dump() if canary else None),
        "canary_weight": state.canary_weight,
        "artifacts": [ArtifactSummary(**a.__dict__).model_dump() for a in ARTIFACTS.list(tenant_id)],
        "audit_tail": AUDIT_LOGS.get(tenant_id, [])[-25:],
    }


@app.get("/api/v1/tenants/{tenant_id}/activation/audit")
def export_activation_audit(tenant_id: str) -> dict[str, Any]:
    return {"tenant_id": tenant_id, "items": AUDIT_LOGS.get(tenant_id, [])}


@app.post("/api/v1/tenants/{tenant_id}/activation/mode")
def set_activation_mode(tenant_id: str, req: ModeRequest) -> dict[str, Any]:
    started = _now_ms()
    state = _activation_state(tenant_id)
    mode = req.mode
    if mode == "normal":
        state.protocol.resume_normal()
        state.mode = ActivationMode.NORMAL
    elif mode == "policy-off":
        state.protocol.set_policy_off()
        state.mode = ActivationMode.POLICY_OFF
    elif mode == "read-only":
        state.protocol.set_read_only()
        state.mode = ActivationMode.READ_ONLY
    elif mode == "kill-switch":
        state.protocol.set_kill_switch()
        state.mode = ActivationMode.KILL_SWITCH
    duration_ms = _now_ms() - started
    _audit_record(tenant_id, action="set_mode", details={"mode": state.mode.value, "duration_ms": duration_ms})
    return {"tenant_id": tenant_id, "mode": state.mode.value, "duration_ms": duration_ms}


@app.post("/api/v1/tenants/{tenant_id}/activation/activate")
def activate_artifact(
    tenant_id: str,
    req: ActivationRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    started = _now_ms()
    request_id = idempotency_key or uuid.uuid4().hex
    state = _activation_state(tenant_id)
    _ensure_mutation_allowed(tenant_id, state)
    if request_id in state.idempotency:
        return state.idempotency[request_id]

    a = ARTIFACTS.get(tenant_id, req.artifact_id)

    # Phase 1: wire protocol steps; Phase 2+ will enforce real signature verification.
    def _verify(_h: str) -> bool:
        if state.mode == ActivationMode.POLICY_OFF:
            return True
        if not req.enterprise_mode:
            return True
        if not a.signature:
            return False
        verification = req.verification or {}
        algorithm = str(verification.get("algorithm") or "hmac-sha256")
        key = verification.get("key")
        if algorithm != "hmac-sha256" or not key:
            return False
        from mpc.enterprise.governance.signing import HMACSigningPort

        port = HMACSigningPort(str(key))
        expected = port.sign(a.manifest_text.encode("utf-8"))
        return a.signature == expected

    def _attest(_h: str) -> bool:
        return True

    result = state.protocol.activate(a.checksum, verify_fn=_verify, attest_fn=_attest)
    if not result.success:
        code = result.errors[0].code if result.errors else "E_GOV_ACTIVATION_FAILED"
        msg = result.errors[0].message if result.errors else "Activation failed"
        raise_runtime_error(code, msg, status_code=400)

    # Track previous active for rollback.
    prev = ARTIFACTS._active_by_tenant.get(tenant_id)
    if prev and prev != req.artifact_id:
        state.previous_active_artifact_id = prev

    active = ARTIFACTS.activate(tenant_id, req.artifact_id)
    _audit_record(
        tenant_id,
        action="activate",
        request_id=request_id,
        artifact_id=active.id,
        artifact_hash=active.checksum,
        details={"enterprise_mode": req.enterprise_mode},
    )
    duration_ms = _now_ms() - started
    payload = {
        "request_id": request_id,
        "duration_ms": duration_ms,
        "tenant_id": tenant_id,
        "active_artifact_id": active.id,
        "artifact_hash": active.checksum,
        "completed_steps": list(result.completed_steps),
        "mode": state.mode.value,
    }
    state.idempotency[request_id] = payload
    return payload


@app.post("/api/v1/tenants/{tenant_id}/activation/canary")
def set_canary(tenant_id: str, req: CanaryRequest) -> dict[str, Any]:
    started = _now_ms()
    state = _activation_state(tenant_id)
    _ensure_mutation_allowed(tenant_id, state)
    a = ARTIFACTS.get(tenant_id, req.artifact_id)
    state.canary_artifact_id = req.artifact_id
    state.canary_weight = float(req.weight)
    duration_ms = _now_ms() - started
    _audit_record(tenant_id, action="set_canary", artifact_id=a.id, artifact_hash=a.checksum, details={"weight": state.canary_weight, "duration_ms": duration_ms})
    return {"tenant_id": tenant_id, "canary_artifact_id": req.artifact_id, "canary_weight": state.canary_weight, "duration_ms": duration_ms}


@app.post("/api/v1/tenants/{tenant_id}/activation/promote-canary")
def promote_canary(tenant_id: str) -> dict[str, Any]:
    started = _now_ms()
    state = _activation_state(tenant_id)
    _ensure_mutation_allowed(tenant_id, state)
    if not state.canary_artifact_id:
        raise_runtime_error("E_PARSE_SYNTAX", "No canary is set for tenant.", status_code=400)
    # Promote canary by activating it.
    payload = activate_artifact(tenant_id, ActivationRequest(artifact_id=state.canary_artifact_id, enterprise_mode=False), None)  # type: ignore[arg-type]
    state.canary_artifact_id = None
    state.canary_weight = 0.0
    payload["promoted_from_canary"] = True
    _audit_record(tenant_id, action="promote_canary", artifact_id=payload.get("active_artifact_id"), artifact_hash=payload.get("artifact_hash"))
    payload["duration_ms"] = _now_ms() - started
    return payload


@app.post("/api/v1/tenants/{tenant_id}/activation/rollback")
def rollback(tenant_id: str) -> dict[str, Any]:
    started = _now_ms()
    state = _activation_state(tenant_id)
    _ensure_mutation_allowed(tenant_id, state)
    prev = state.previous_active_artifact_id
    if not prev:
        raise_runtime_error("E_PARSE_SYNTAX", "No previous active artifact recorded for tenant.", status_code=400)
    payload = activate_artifact(tenant_id, ActivationRequest(artifact_id=prev, enterprise_mode=False), None)  # type: ignore[arg-type]
    payload["rolled_back"] = True
    _audit_record(tenant_id, action="rollback", artifact_id=payload.get("active_artifact_id"), artifact_hash=payload.get("artifact_hash"))
    payload["duration_ms"] = _now_ms() - started
    return payload


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
    limits: dict[str, Any] = Field(default_factory=dict)


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
        artifact_hash: str | None = None
        if req.source.manifest_text:
            manifest_text = req.source.manifest_text
            artifact_hash = stable_hash(manifest_text)
        elif req.source.artifact_id:
            if not effective_tenant:
                raise_runtime_error("E_RUNTIME_FORBIDDEN", "tenant_id is required when using artifact_id.", status_code=400)
            art = ARTIFACTS.get(effective_tenant, req.source.artifact_id)
            manifest_text = art.manifest_text
            artifact_hash = art.checksum
        else:
            if not effective_tenant:
                raise_runtime_error("E_RUNTIME_ACTIVE_REQUIRED", "tenant_id is required when using tenant active artifact.", status_code=400)
            art = ARTIFACTS.get_active(effective_tenant)
            manifest_text = art.manifest_text
            artifact_hash = art.checksum

        # Run engine
        ast = parse(manifest_text)
        limits = req.limits or {}
        quota = QuotaEnforcer(
            limits=QuotaLimits(
                max_manifest_nodes=int(limits.get("maxManifestNodes", 10000)),
                max_total_defs=int(limits.get("maxTotalDefs", 5000)),
                max_eval_ops=int(limits.get("maxEvalOps", 10000)),
            )
        )
        # MVP: treat defs count as node count as well.
        def_count = len(getattr(ast, "defs", []) or [])
        err = quota.check_defs(def_count) or quota.check_nodes(def_count)
        if err is not None:
            raise_runtime_error(err.code, err.message, status_code=400)

        kind_names = sorted({str(getattr(node, "kind", "") or "") for node in getattr(ast, "defs", [])})
        known = {k.name for k in FORM_KINDS}
        extra = [KindDef(name=name) for name in kind_names if name and name not in known]
        meta = DomainMeta(kinds=[*FORM_KINDS, *extra])

        if bool(req.strict_validation):
            errors = validate_structural(ast, meta)
            if errors:
                message = "; ".join([e.message for e in errors[:5]])
                raise_runtime_error("MANIFEST_INVALID_SHAPE", message or "Manifest failed structural validation.", status_code=400)
        engine = FormEngine(
            ast=ast,
            meta=meta,
            max_expr_steps=int(limits.get("maxExprSteps", 5000)),
            max_expr_depth=int(limits.get("maxExprDepth", 50)),
            max_eval_time_ms=float(limits.get("maxEvalTimeMs", 50.0)),
            max_regex_ops=int(limits.get("maxRegexOps", 5000)),
        )
        package = engine.get_form_package(
            req.form_id,
            req.data,
            actor_roles=req.actor_roles,
            actor_attrs=req.actor_attrs,
            fail_open=True if req.fail_open is None else bool(req.fail_open),
        )

        duration_ms = _now_ms() - started
        if effective_tenant:
            _audit_record(
                effective_tenant,
                action="form_package",
                request_id=request_id,
                artifact_hash=artifact_hash,
                details={"form_id": req.form_id, "duration_ms": duration_ms},
            )
        return {
            "request_id": request_id,
            "duration_ms": duration_ms,
            "artifact_hash": artifact_hash,
            "trace_span_id": request_id,
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
        raise_runtime_error("E_RUNTIME_INTERNAL", str(e), status_code=500, retryable=True)

