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

def Policy p1 { rules: [] }
""".strip()


def _client() -> TestClient:
    blobs = tempfile.TemporaryDirectory()
    url = os.environ.get("MPC_RUNTIME_REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(url, decode_responses=False)
        r.ping()
    except Exception:
        pytest.skip("Real Redis not available; set MPC_RUNTIME_REDIS_URL to run lifecycle/RBAC tests.")

    app.state.runtime_store = RedisRuntimeStore(redis=r, prefix=f"mpc_runtime_test:{uuid.uuid4().hex}")
    os.environ["MPC_RUNTIME_BLOB_DIR"] = blobs.name
    if hasattr(app.state, "blob_store"):
        delattr(app.state, "blob_store")
    return TestClient(app)


def test_publish_requires_publisher_role() -> None:
    client = _client()
    create = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL})
    artifact_id = create.json()["id"]

    resp = client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1", headers={"X-Actor-Roles": "author"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "E_RUNTIME_FORBIDDEN"


def test_invalid_transition_is_rejected() -> None:
    client = _client()
    create = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL})
    artifact_id = create.json()["id"]

    # Draft -> approved should fail (must go review first).
    resp = client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1", headers={"X-Actor-Roles": "reviewer"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "E_GOV_ACTIVATION_FAILED"

