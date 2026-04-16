from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
import os
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

import json

from mpc.enterprise.governance.activation import ActivationMode, ActivationProtocol
from mpc.enterprise.governance.quotas import QuotaEnforcer, QuotaLimits
from mpc.features.form.engine import FormEngine
from mpc.features.form import FORM_CONTRACT_VERSION
from mpc.features.form.kinds import FORM_KINDS
from mpc.kernel.canonical.hash import stable_hash
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.kernel.parser import parse
from mpc.tooling.validator.structural import validate_structural

from tooling.mpc_runtime.storage.blob_store import LocalFsBlobStore, S3BlobStore
from tooling.mpc_runtime.storage.redis_store import RedisRuntimeStore
from tooling.mpc_runtime.storage.ports import BlobStore, RuntimeStore, StoredArtifact, CanaryConfig
from tooling.mpc_runtime.authn import AuthnConfig, parse_bearer_token, verify_jwt
from tooling.mpc_runtime.authz import ActorContext, context_from_jwt


app = FastAPI(title="mpc-runtime", version="0.1.0")

def _authn_config() -> AuthnConfig:
    mode = str(os.environ.get("MPC_RUNTIME_AUTH_MODE", "header")).lower()
    jwks_url = os.environ.get("MPC_RUNTIME_JWKS_URL") or None
    jwks_json_env = os.environ.get("MPC_RUNTIME_JWKS_JSON") or None
    jwks_json = json.loads(jwks_json_env) if jwks_json_env else None
    issuer = os.environ.get("MPC_RUNTIME_JWT_ISSUER") or None
    audience = os.environ.get("MPC_RUNTIME_JWT_AUDIENCE") or None
    return AuthnConfig(
        mode=mode,
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        jwks_json=jwks_json,
        jwks_cache_ttl_s=int(os.environ.get("MPC_RUNTIME_JWKS_CACHE_TTL_S", "300")),
    )


def _resolve_actor(
    *,
    authorization: str | None,
    x_tenant_id: str | None,
    x_actor_roles: str | None,
    x_actor_id: str | None,
    req_tenant_id: str | None,
) -> ActorContext | None:
    cfg = _authn_config()
    if cfg.mode != "jwt":
        # Header-mode (dev compatibility)
        tenant = (req_tenant_id or x_tenant_id or "").strip() or None
        roles = _parse_roles(x_actor_roles)
        actor_id = (x_actor_id or "").strip() or None
        if not tenant:
            return None
        return ActorContext(tenant_id=tenant, actor_id=actor_id, roles=roles)

    token = parse_bearer_token(authorization)
    if not token:
        raise_runtime_error("E_RUNTIME_FORBIDDEN", "Missing bearer token.", status_code=403)
    try:
        principal = verify_jwt(token=token, cfg=cfg)
    except Exception as exc:
        raise_runtime_error("E_RUNTIME_FORBIDDEN", f"Invalid bearer token: {exc}", status_code=403)
    try:
        ctx = context_from_jwt(principal)
    except Exception as exc:
        raise_runtime_error("E_RUNTIME_FORBIDDEN", f"Invalid token claims: {exc}", status_code=403)
    if req_tenant_id and str(req_tenant_id).strip() and ctx.tenant_id != str(req_tenant_id).strip():
        raise_runtime_error("E_RUNTIME_FORBIDDEN", "tenant_id does not match token tenant.", status_code=403)
    if x_tenant_id and str(x_tenant_id).strip() and ctx.tenant_id != str(x_tenant_id).strip():
        raise_runtime_error("E_RUNTIME_FORBIDDEN", "X-Tenant-Id does not match token tenant.", status_code=403)
    return ctx

def _default_blob_store() -> BlobStore:
    backend = str(os.environ.get("MPC_RUNTIME_BLOB_BACKEND", "localfs")).lower()
    if backend == "s3":
        bucket = os.environ.get("MPC_RUNTIME_S3_BUCKET") or ""
        if not bucket:
            raise RuntimeError("MPC_RUNTIME_S3_BUCKET is required when MPC_RUNTIME_BLOB_BACKEND=s3")
        prefix = os.environ.get("MPC_RUNTIME_S3_PREFIX", "mpc-runtime")
        region = os.environ.get("MPC_RUNTIME_S3_REGION") or None
        return S3BlobStore(bucket=bucket, prefix=prefix, region=region)

    root = os.environ.get("MPC_RUNTIME_BLOB_DIR") or os.path.join(os.getcwd(), ".mpc_runtime_blobs")
    return LocalFsBlobStore(root_dir=root)


def _default_runtime_store() -> RuntimeStore:
    import redis  # type: ignore

    url = os.environ.get("MPC_RUNTIME_REDIS_URL", "redis://localhost:6379/0")
    client = redis.Redis.from_url(url, decode_responses=False)
    return RedisRuntimeStore(redis=client)


def _get_store() -> RuntimeStore:
    store = getattr(app.state, "runtime_store", None)
    if store is None:
        store = _default_runtime_store()
        app.state.runtime_store = store
    return store


def _get_blob_store() -> BlobStore:
    bs = getattr(app.state, "blob_store", None)
    if bs is None:
        bs = _default_blob_store()
        app.state.blob_store = bs
    return bs


class RuntimeErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False


def raise_runtime_error(code: str, message: str, *, status_code: int = 400, retryable: bool = False) -> None:
    # Best-effort metrics + structured log.
    try:
        tenant = "unknown"
        # Attempt to infer tenant from message patterns is fragile; rely on caller audit where possible.
        _get_store().metrics_incr(tenant_id=tenant, name="runtime_error", value=1, labels={"code": code, "status": str(status_code)})
    except Exception:
        pass
    try:
        import json as _json
        import sys as _sys

        _sys.stderr.write(
            _json.dumps(
                {"ts": _now_iso(), "level": "error", "code": code, "status": status_code, "retryable": retryable, "message": message},
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
    except Exception:
        pass
    raise HTTPException(status_code=status_code, detail=RuntimeErrorBody(code=code, message=message, retryable=retryable).model_dump())


def _now_ms() -> int:
    return int(time.time() * 1000)

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sticky_bucket(seed: str) -> float:
    # Deterministic [0,1) bucket for canary routing.
    h = stable_hash(seed)
    # take 12 hex chars (~48 bits) for stable float.
    n = int(h[:12], 16)
    return (n % 1_000_000) / 1_000_000.0


def _select_effective_artifact_id(*, tenant_id: str, actor_key: str | None) -> str | None:
    store = _get_store()
    active_id = store.get_active_artifact_id(tenant_id=tenant_id)
    canary = store.get_canary(tenant_id=tenant_id)
    if not active_id or not canary or canary.weight <= 0.0:
        return active_id
    key = actor_key or ""
    bucket = _sticky_bucket(f"{tenant_id}:{key}")
    if bucket < float(canary.weight):
        return canary.artifact_id
    return active_id


def _quota_from_limits(limits: dict[str, Any]) -> QuotaEnforcer:
    # Central place for runtime-wide limits parsing.
    return QuotaEnforcer(
        limits=QuotaLimits(
            max_manifest_nodes=int(limits.get("maxManifestNodes", 10000)),
            max_total_defs=int(limits.get("maxTotalDefs", 5000)),
            max_eval_ops=int(limits.get("maxEvalOps", 10000)),
        )
    )


def _enforce_manifest_quota(*, ast: Any, limits: dict[str, Any]) -> None:
    quota = _quota_from_limits(limits)
    # MVP: treat defs count as node count as well.
    def_count = len(getattr(ast, "defs", []) or [])
    err = quota.check_defs(def_count) or quota.check_nodes(def_count)
    if err is not None:
        raise_runtime_error(err.code, err.message, status_code=400)
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
    _get_store().audit_append(tenant_id=tenant_id, record=record)


def _artifact_summary(a: StoredArtifact) -> dict[str, Any]:
    return {
        "id": a.id,
        "tenant_id": a.tenant_id,
        "status": a.status,
        "version": a.version,
        "checksum": a.checksum,
        "created_at": a.created_at,
    }


def _artifact_detail(a: StoredArtifact) -> dict[str, Any]:
    blob = _get_blob_store()
    return {**_artifact_summary(a), "manifest_text": blob.get_text(ref=a.manifest_ref), "signature": a.signature}


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
    items = [_artifact_summary(a) for a in _get_store().list_artifacts(tenant_id=tenant_id)]
    return {"items": items}


@app.get("/api/v1/rule-artifacts/{artifact_id}")
def get_rule_artifact(artifact_id: str, tenant_id: str = Query(...)) -> dict[str, Any]:
    try:
        a = _get_store().get_artifact(tenant_id=tenant_id, artifact_id=artifact_id)
        return _artifact_detail(a)
    except KeyError:
        raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{artifact_id}' not found.", status_code=404)


@app.post("/api/v1/rule-artifacts")
def create_rule_artifact(req: ArtifactCreateRequest) -> dict[str, Any]:
    blob = _get_blob_store()
    created_at = _now_iso()
    checksum = stable_hash(req.manifest_text)
    ref = blob.put_text(key=checksum, text=req.manifest_text)
    a = _get_store().create_artifact(
        tenant_id=req.tenant_id,
        manifest_ref=ref,
        checksum=checksum,
        signature=req.signature,
        created_at=created_at,
    )
    _audit_record(
        req.tenant_id,
        action="artifact_create",
        artifact_id=a.id,
        artifact_hash=a.checksum,
    )
    return {"id": a.id, "status": a.status, "checksum": a.checksum}


@app.put("/api/v1/rule-artifacts/{artifact_id}")
def update_rule_artifact(artifact_id: str, req: ArtifactUpdateRequest) -> dict[str, Any]:
    blob = _get_blob_store()
    store = _get_store()
    try:
        existing = store.get_artifact(tenant_id=req.tenant_id, artifact_id=artifact_id)
    except KeyError:
        raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{artifact_id}' not found.", status_code=404)
    if str(existing.status) in ("published", "active", "deprecated", "retired"):
        raise_runtime_error(
            "E_GOV_ACTIVATION_FAILED",
            f"Artifact is immutable in status '{existing.status}'.",
            status_code=409,
        )
    checksum = stable_hash(req.manifest_text)
    ref = blob.put_text(key=checksum, text=req.manifest_text)
    try:
        a = store.update_artifact(
            tenant_id=req.tenant_id,
            artifact_id=artifact_id,
            manifest_ref=ref,
            checksum=checksum,
            signature=req.signature,
        )
        _audit_record(
            req.tenant_id,
            action="artifact_update",
            artifact_id=a.id,
            artifact_hash=a.checksum,
            details={"previous_checksum": existing.checksum},
        )
        return _artifact_detail(a)
    except KeyError:
        raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{artifact_id}' not found.", status_code=404)


@app.post("/api/v1/rule-artifacts/{artifact_id}/activate")
def activate_rule_artifact(artifact_id: str, tenant_id: str) -> dict[str, Any]:
    raise_runtime_error(
        "E_RUNTIME_DEPRECATED",
        "Legacy activation endpoint is deprecated. Use /api/v1/tenants/{tenant_id}/activation/activate.",
        status_code=410,
    )


def _parse_roles(header_value: str | None) -> set[str]:
    if not header_value:
        return set()
    return {r.strip() for r in header_value.split(",") if r.strip()}


def _require_role(*, roles: set[str], required_any: set[str]) -> None:
    if roles.intersection(required_any):
        return
    raise_runtime_error("E_RUNTIME_FORBIDDEN", f"Missing required role: one of {sorted(required_any)}", status_code=403)


def _idempotent(
    *,
    tenant_id: str,
    idempotency_key: str | None,
    ttl_s: int,
    compute: Any,
) -> dict[str, Any]:
    if not idempotency_key:
        return compute()
    store = _get_store()
    cached = store.idempotency_get(tenant_id=tenant_id, key=idempotency_key)
    if cached is not None:
        return cached
    value = compute()
    store.idempotency_set(tenant_id=tenant_id, key=idempotency_key, value=value, ttl_s=int(ttl_s))
    return value


LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"review"},
    "review": {"approved", "draft"},
    "approved": {"published"},
    "published": {"active", "deprecated"},
    "active": {"deprecated"},
    "deprecated": {"retired"},
    "retired": set(),
}


@app.post("/api/v1/rule-artifacts/{artifact_id}/lifecycle/{action}")
def lifecycle_action(
    artifact_id: str,
    action: Literal["submit_review", "approve", "publish", "deprecate", "retire", "revert_to_draft"],
    tenant_id: str = Query(...),
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, Any]:
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=tenant_id,
    )
    roles = ctx.roles if ctx else _parse_roles(x_actor_roles)
    # Simple RBAC policy (placeholder until real authn/authz):
    if action in ("submit_review", "revert_to_draft"):
        _require_role(roles=roles, required_any={"author", "admin"})
    elif action == "approve":
        _require_role(roles=roles, required_any={"reviewer", "admin"})
    elif action == "publish":
        _require_role(roles=roles, required_any={"publisher", "admin"})
    else:
        _require_role(roles=roles, required_any={"admin"})

    store = _get_store()
    try:
        art = store.get_artifact(tenant_id=tenant_id, artifact_id=artifact_id)
    except KeyError:
        raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{artifact_id}' not found.", status_code=404)

    if idempotency_key:
        cached = store.idempotency_get(tenant_id=tenant_id, key=idempotency_key)
        if cached is not None:
            return cached

    current = str(art.status)
    desired = {
        "submit_review": "review",
        "approve": "approved",
        "publish": "published",
        "deprecate": "deprecated",
        "retire": "retired",
        "revert_to_draft": "draft",
    }[action]

    allowed = LIFECYCLE_TRANSITIONS.get(current, set())
    if desired not in allowed:
        raise_runtime_error(
            "E_GOV_ACTIVATION_FAILED",
            f"Invalid lifecycle transition: {current} -> {desired}",
            status_code=400,
        )

    def _do() -> dict[str, Any]:
        updated = store.set_artifact_status(tenant_id=tenant_id, artifact_id=artifact_id, status=desired)
        _audit_record(
            tenant_id,
            action=f"lifecycle_{action}",
            artifact_id=updated.id,
            artifact_hash=updated.checksum,
            details={"from": current, "to": desired, "roles": sorted(roles)},
        )
        return {"id": updated.id, "status": updated.status, "checksum": updated.checksum}

    return _idempotent(tenant_id=tenant_id, idempotency_key=idempotency_key, ttl_s=60 * 10, compute=_do)


# ---------------------------------------------------------------------------
# Enterprise activation surface (Runtime API)
# ---------------------------------------------------------------------------

@dataclass
class TenantActivationState:
    tenant_id: str
    protocol: ActivationProtocol
    mode: ActivationMode


def _mode_to_activation_mode(mode: str) -> ActivationMode:
    if mode == "kill-switch":
        return ActivationMode.KILL_SWITCH
    if mode == "read-only":
        return ActivationMode.READ_ONLY
    if mode == "policy-off":
        return ActivationMode.POLICY_OFF
    return ActivationMode.NORMAL


def _activation_state(tenant_id: str) -> TenantActivationState:
    store = _get_store()
    stored_mode = store.get_mode(tenant_id=tenant_id)
    mode = _mode_to_activation_mode(stored_mode)

    # Stateless protocol instance per request to avoid process-memory divergence
    # in multi-instance deployments. Persistent state is stored in RuntimeStore.
    proto = ActivationProtocol()

    # Keep protocol mode aligned with store.
    if mode == ActivationMode.KILL_SWITCH:
        proto.set_kill_switch()
    elif mode == ActivationMode.READ_ONLY:
        proto.set_read_only()
    elif mode == ActivationMode.POLICY_OFF:
        proto.set_policy_off()
    else:
        proto.resume_normal()

    return TenantActivationState(tenant_id=tenant_id, protocol=proto, mode=mode)

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
def get_activation_status(
    tenant_id: str,
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, Any]:
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=tenant_id,
    )
    roles = ctx.roles if ctx else _parse_roles(x_actor_roles)
    _require_role(roles=roles, required_any={"auditor", "admin"})
    state = _activation_state(tenant_id)
    store = _get_store()
    active_id = store.get_active_artifact_id(tenant_id=tenant_id)
    prev_id = store.get_previous_active_artifact_id(tenant_id=tenant_id)
    canary_cfg = store.get_canary(tenant_id=tenant_id)

    def _maybe_get(aid: str | None) -> dict[str, Any] | None:
        if not aid:
            return None
        try:
            return _artifact_summary(store.get_artifact(tenant_id=tenant_id, artifact_id=aid))
        except KeyError:
            return None

    items, _ = store.audit_list(tenant_id=tenant_id, limit=25, cursor=None)
    return {
        "tenant_id": tenant_id,
        "mode": state.mode.value,
        "active": _maybe_get(active_id),
        "previous_active": _maybe_get(prev_id),
        "canary": (_maybe_get(canary_cfg.artifact_id) if canary_cfg else None),
        "canary_weight": (canary_cfg.weight if canary_cfg else 0.0),
        "artifacts": [_artifact_summary(a) for a in store.list_artifacts(tenant_id=tenant_id)],
        "audit_tail": items,
    }


@app.get("/api/v1/tenants/{tenant_id}/activation/audit")
def export_activation_audit(
    tenant_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    cursor: str | None = Query(default=None),
    start_ts: str | None = Query(default=None),
    end_ts: str | None = Query(default=None),
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, Any]:
    """Append-only audit export with pagination.

    cursor is an opaque offset (stringified int) for the underlying list.
    Optional start_ts/end_ts are ISO-8601 timestamps used for client-side filtering.
    """
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=tenant_id,
    )
    roles = ctx.roles if ctx else _parse_roles(x_actor_roles)
    _require_role(roles=roles, required_any={"auditor", "admin"})
    store = _get_store()
    page, next_cursor = store.audit_list(tenant_id=tenant_id, limit=int(limit), cursor=cursor)
    if start_ts or end_ts:
        def _in_range(item: dict[str, Any]) -> bool:
            ts = str(item.get("timestamp") or "")
            if start_ts and ts < start_ts:
                return False
            if end_ts and ts > end_ts:
                return False
            return True
        page = [row for row in page if _in_range(row)]
    _audit_record(
        tenant_id,
        action="audit_export",
        details={"limit": int(limit), "cursor": cursor, "next_cursor": next_cursor, "start_ts": start_ts, "end_ts": end_ts},
    )
    return {"tenant_id": tenant_id, "items": page, "next_cursor": next_cursor}


@app.post("/api/v1/tenants/{tenant_id}/activation/mode")
def set_activation_mode(
    tenant_id: str,
    req: ModeRequest,
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, Any]:
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=tenant_id,
    )
    roles = ctx.roles if ctx else _parse_roles(x_actor_roles)
    _require_role(roles=roles, required_any={"admin"})

    def _do() -> dict[str, Any]:
        started = _now_ms()
        state = _activation_state(tenant_id)
        store = _get_store()
        mode = req.mode
        if mode == "normal":
            state.protocol.resume_normal()
            state.mode = ActivationMode.NORMAL
            store.set_mode(tenant_id=tenant_id, mode="normal")
        elif mode == "policy-off":
            state.protocol.set_policy_off()
            state.mode = ActivationMode.POLICY_OFF
            store.set_mode(tenant_id=tenant_id, mode="policy-off")
        elif mode == "read-only":
            state.protocol.set_read_only()
            state.mode = ActivationMode.READ_ONLY
            store.set_mode(tenant_id=tenant_id, mode="read-only")
        elif mode == "kill-switch":
            state.protocol.set_kill_switch()
            state.mode = ActivationMode.KILL_SWITCH
            store.set_mode(tenant_id=tenant_id, mode="kill-switch")
        duration_ms = _now_ms() - started
        _audit_record(tenant_id, action="set_mode", details={"mode": state.mode.value, "duration_ms": duration_ms, "roles": sorted(roles)})
        return {"tenant_id": tenant_id, "mode": state.mode.value, "duration_ms": duration_ms}

    return _idempotent(tenant_id=tenant_id, idempotency_key=idempotency_key, ttl_s=60 * 10, compute=_do)


@app.post("/api/v1/tenants/{tenant_id}/activation/activate")
def activate_artifact(
    tenant_id: str,
    req: ActivationRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, Any]:
    started = _now_ms()
    request_id = idempotency_key or uuid.uuid4().hex
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=tenant_id,
    )
    roles = ctx.roles if ctx else _parse_roles(x_actor_roles)
    _require_role(roles=roles, required_any={"deployer", "admin"})
    state = _activation_state(tenant_id)
    _ensure_mutation_allowed(tenant_id, state)
    store = _get_store()
    cached = store.idempotency_get(tenant_id=tenant_id, key=request_id)
    if cached is not None:
        return cached

    try:
        a = store.get_artifact(tenant_id=tenant_id, artifact_id=req.artifact_id)
    except KeyError:
        raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{req.artifact_id}' not found.", status_code=404)
    if str(a.status) != "published":
        raise_runtime_error(
            "E_GOV_ACTIVATION_FAILED",
            f"Artifact must be 'published' before activation (current: {a.status})",
            status_code=400,
        )
    manifest_text = _get_blob_store().get_text(ref=a.manifest_ref)

    # Phase 1: wire protocol steps; Phase 2+ will enforce real signature verification.
    def _verify(_h: str) -> bool:
        if state.mode == ActivationMode.POLICY_OFF:
            return True
        if not req.enterprise_mode:
            return True
        if not a.signature:
            return False
        verification = req.verification or {}
        algorithm = str(verification.get("algorithm") or "hmac-sha256").upper()
        if algorithm in ("HMAC-SHA256", "HMAC_SHA256", "HMAC"):
            key = verification.get("key")
            if not key:
                return False
            from mpc.enterprise.governance.signing import HMACSigningPort

            port = HMACSigningPort(str(key))
            expected = port.sign(manifest_text.encode("utf-8"))
            return a.signature == expected

        if algorithm in ("RS256", "JWT-RS256"):
            jwks = verification.get("jwks")
            if not isinstance(jwks, dict):
                return False
            from mpc.enterprise.governance.signing import verify_jwt_payload_hash

            payload_hash = stable_hash(manifest_text)
            res = verify_jwt_payload_hash(token=str(a.signature), payload_hash=payload_hash, jwks=jwks, algorithms=["RS256"])
            return bool(res.valid)

        return False

    def _attest(_h: str) -> bool:
        return True

    result = state.protocol.activate(a.checksum, verify_fn=_verify, attest_fn=_attest)
    if not result.success:
        code = result.errors[0].code if result.errors else "E_GOV_ACTIVATION_FAILED"
        msg = result.errors[0].message if result.errors else "Activation failed"
        raise_runtime_error(code, msg, status_code=400)

    # Track previous active for rollback.
    prev = store.get_active_artifact_id(tenant_id=tenant_id)
    if prev and prev != req.artifact_id:
        store.set_previous_active_artifact(tenant_id=tenant_id, artifact_id=prev)

    store.set_active_artifact(tenant_id=tenant_id, artifact_id=req.artifact_id)
    active = store.get_artifact(tenant_id=tenant_id, artifact_id=req.artifact_id)
    _audit_record(
        tenant_id,
        action="activate",
        request_id=request_id,
        artifact_id=active.id,
        artifact_hash=active.checksum,
        details={"enterprise_mode": req.enterprise_mode, "roles": sorted(roles)},
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
    store.idempotency_set(tenant_id=tenant_id, key=request_id, value=payload, ttl_s=60 * 10)
    return payload


@app.post("/api/v1/tenants/{tenant_id}/activation/canary")
def set_canary(
    tenant_id: str,
    req: CanaryRequest,
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, Any]:
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=tenant_id,
    )
    roles = ctx.roles if ctx else _parse_roles(x_actor_roles)
    _require_role(roles=roles, required_any={"deployer", "admin"})

    def _do() -> dict[str, Any]:
        started = _now_ms()
        state = _activation_state(tenant_id)
        _ensure_mutation_allowed(tenant_id, state)
        store = _get_store()
        try:
            a = store.get_artifact(tenant_id=tenant_id, artifact_id=req.artifact_id)
        except KeyError:
            raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{req.artifact_id}' not found.", status_code=404)
        store.set_canary(tenant_id=tenant_id, artifact_id=req.artifact_id, weight=float(req.weight))
        duration_ms = _now_ms() - started
        _audit_record(
            tenant_id,
            action="set_canary",
            artifact_id=a.id,
            artifact_hash=a.checksum,
            details={"weight": float(req.weight), "duration_ms": duration_ms, "roles": sorted(roles)},
        )
        return {"tenant_id": tenant_id, "canary_artifact_id": req.artifact_id, "canary_weight": float(req.weight), "duration_ms": duration_ms}

    return _idempotent(tenant_id=tenant_id, idempotency_key=idempotency_key, ttl_s=60 * 10, compute=_do)


@app.post("/api/v1/tenants/{tenant_id}/activation/promote-canary")
def promote_canary(
    tenant_id: str,
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, Any]:
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=tenant_id,
    )
    roles = ctx.roles if ctx else _parse_roles(x_actor_roles)
    _require_role(roles=roles, required_any={"deployer", "admin"})

    def _do() -> dict[str, Any]:
        started = _now_ms()
        state = _activation_state(tenant_id)
        _ensure_mutation_allowed(tenant_id, state)
        store = _get_store()
        canary_cfg = store.get_canary(tenant_id=tenant_id)
        if not canary_cfg:
            raise_runtime_error("E_PARSE_SYNTAX", "No canary is set for tenant.", status_code=400)
        # Promote canary by activating it.
        payload = activate_artifact(
            tenant_id,
            ActivationRequest(artifact_id=canary_cfg.artifact_id, enterprise_mode=False),
            idempotency_key=None,
            x_actor_roles=x_actor_roles,
            authorization=None,
            x_tenant_id=None,
            x_actor_id=None,
        )
        store.set_canary(tenant_id=tenant_id, artifact_id=None, weight=None)
        payload["promoted_from_canary"] = True
        _audit_record(
            tenant_id,
            action="promote_canary",
            artifact_id=payload.get("active_artifact_id"),
            artifact_hash=payload.get("artifact_hash"),
            details={"roles": sorted(roles)},
        )
        payload["duration_ms"] = _now_ms() - started
        return payload

    return _idempotent(tenant_id=tenant_id, idempotency_key=idempotency_key, ttl_s=60 * 10, compute=_do)


@app.post("/api/v1/tenants/{tenant_id}/activation/rollback")
def rollback(
    tenant_id: str,
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, Any]:
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=tenant_id,
    )
    roles = ctx.roles if ctx else _parse_roles(x_actor_roles)
    _require_role(roles=roles, required_any={"deployer", "admin"})

    def _do() -> dict[str, Any]:
        started = _now_ms()
        state = _activation_state(tenant_id)
        _ensure_mutation_allowed(tenant_id, state)
        store = _get_store()
        prev = store.get_previous_active_artifact_id(tenant_id=tenant_id)
        if not prev:
            raise_runtime_error("E_PARSE_SYNTAX", "No previous active artifact recorded for tenant.", status_code=400)
        payload = activate_artifact(
            tenant_id,
            ActivationRequest(artifact_id=prev, enterprise_mode=False),
            idempotency_key=None,
            x_actor_roles=x_actor_roles,
            authorization=None,
            x_tenant_id=None,
            x_actor_id=None,
        )
        payload["rolled_back"] = True
        _audit_record(
            tenant_id,
            action="rollback",
            artifact_id=payload.get("active_artifact_id"),
            artifact_hash=payload.get("artifact_hash"),
            details={"roles": sorted(roles)},
        )
        payload["duration_ms"] = _now_ms() - started
        return payload

    return _idempotent(tenant_id=tenant_id, idempotency_key=idempotency_key, ttl_s=60 * 10, compute=_do)


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
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    x_actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    started = _now_ms()
    request_id = idempotency_key or uuid.uuid4().hex
    ctx = _resolve_actor(
        authorization=authorization,
        x_tenant_id=x_tenant_id,
        x_actor_roles=x_actor_roles,
        x_actor_id=x_actor_id,
        req_tenant_id=req.tenant_id,
    )
    effective_tenant = (ctx.tenant_id if ctx else (req.tenant_id or x_tenant_id or "").strip() or None)

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
            store = _get_store()
            try:
                art = store.get_artifact(tenant_id=effective_tenant, artifact_id=req.source.artifact_id)
            except KeyError:
                raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{req.source.artifact_id}' not found.", status_code=404)
            manifest_text = _get_blob_store().get_text(ref=art.manifest_ref)
            artifact_hash = art.checksum
        else:
            if not effective_tenant:
                raise_runtime_error("E_RUNTIME_ACTIVE_REQUIRED", "tenant_id is required when using tenant active artifact.", status_code=400)
            store = _get_store()
            actor_key = (ctx.actor_id if ctx and ctx.actor_id else None) or x_actor_id or str((req.actor_attrs or {}).get("id") or "")
            active_id = _select_effective_artifact_id(tenant_id=effective_tenant, actor_key=actor_key)
            if not active_id:
                raise_runtime_error("E_RUNTIME_ACTIVE_REQUIRED", "Tenant has no active artifact.", status_code=409)
            try:
                art = store.get_artifact(tenant_id=effective_tenant, artifact_id=active_id)
            except KeyError:
                raise_runtime_error("E_RUNTIME_NOT_FOUND", f"Artifact '{active_id}' not found.", status_code=404)
            manifest_text = _get_blob_store().get_text(ref=art.manifest_ref)
            artifact_hash = art.checksum

        # Run engine
        ast = parse(manifest_text)
        limits = req.limits or {}
        _enforce_manifest_quota(ast=ast, limits=limits)

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

