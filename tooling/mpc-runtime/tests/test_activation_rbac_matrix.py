from __future__ import annotations

import os
import tempfile
import uuid

import pytest
import redis
from fastapi.testclient import TestClient

from tooling.mpc_runtime.app import app
from tooling.mpc_runtime.storage.redis_store import RedisRuntimeStore


DSL = """
@schema 1
@namespace "t"
@name "t"
@version "1.0.0"

def FormDef signup "Signup" { def FieldDef email { type: "string" required: true } }
""".strip()


def _client() -> TestClient:
    blobs = tempfile.TemporaryDirectory()
    url = os.environ.get("MPC_RUNTIME_REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(url, decode_responses=False)
        r.ping()
    except Exception:
        pytest.skip("Real Redis not available; set MPC_RUNTIME_REDIS_URL to run RBAC matrix tests.")
    app.state.runtime_store = RedisRuntimeStore(redis=r, prefix=f"mpc_runtime_test:{uuid.uuid4().hex}")
    os.environ["MPC_RUNTIME_BLOB_DIR"] = blobs.name
    if hasattr(app.state, "blob_store"):
        delattr(app.state, "blob_store")
    return TestClient(app)


def _published_artifact(client: TestClient) -> str:
    create = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL, "signature": None})
    artifact_id = create.json()["id"]
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1", headers={"X-Actor-Roles": "author"})
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1", headers={"X-Actor-Roles": "reviewer"})
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1", headers={"X-Actor-Roles": "publisher"})
    return artifact_id


def test_activation_mode_requires_admin() -> None:
    c = _client()
    r1 = c.post("/api/v1/tenants/t1/activation/mode", json={"mode": "policy-off"})
    assert r1.status_code == 403
    r2 = c.post("/api/v1/tenants/t1/activation/mode", json={"mode": "policy-off"}, headers={"X-Actor-Roles": "admin"})
    assert r2.status_code == 200


def test_activation_activate_requires_deployer_or_admin() -> None:
    c = _client()
    artifact_id = _published_artifact(c)
    r1 = c.post("/api/v1/tenants/t1/activation/activate", json={"artifact_id": artifact_id, "enterprise_mode": False})
    assert r1.status_code == 403
    r2 = c.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": artifact_id, "enterprise_mode": False},
        headers={"X-Actor-Roles": "deployer"},
    )
    assert r2.status_code == 200


def test_activation_audit_status_require_auditor_or_admin() -> None:
    c = _client()
    r1 = c.get("/api/v1/tenants/t1/activation/status")
    assert r1.status_code == 403
    r2 = c.get("/api/v1/tenants/t1/activation/status", headers={"X-Actor-Roles": "auditor"})
    assert r2.status_code == 200

    r3 = c.get("/api/v1/tenants/t1/activation/audit")
    assert r3.status_code == 403
    r4 = c.get("/api/v1/tenants/t1/activation/audit", headers={"X-Actor-Roles": "auditor"})
    assert r4.status_code == 200

