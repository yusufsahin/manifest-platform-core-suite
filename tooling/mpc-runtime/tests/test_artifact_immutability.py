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
        pytest.skip("Real Redis not available; set MPC_RUNTIME_REDIS_URL to run immutability tests.")
    app.state.runtime_store = RedisRuntimeStore(redis=r, prefix=f"mpc_runtime_test:{uuid.uuid4().hex}")
    os.environ["MPC_RUNTIME_BLOB_DIR"] = blobs.name
    if hasattr(app.state, "blob_store"):
        delattr(app.state, "blob_store")
    return TestClient(app)


def test_published_artifact_cannot_be_updated() -> None:
    c = _client()
    create = c.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL, "signature": None})
    artifact_id = create.json()["id"]

    c.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1", headers={"X-Actor-Roles": "author"})
    c.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1", headers={"X-Actor-Roles": "reviewer"})
    c.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1", headers={"X-Actor-Roles": "publisher"})

    updated_dsl = DSL + "\n"
    resp = c.put(
        f"/api/v1/rule-artifacts/{artifact_id}",
        json={"tenant_id": "t1", "manifest_text": updated_dsl, "signature": None},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "E_GOV_ACTIVATION_FAILED"

