from __future__ import annotations

import os
import tempfile
import uuid

import pytest
import redis
from fastapi.testclient import TestClient

_tmp_blobs = tempfile.TemporaryDirectory()
os.environ.setdefault("MPC_RUNTIME_BLOB_DIR", _tmp_blobs.name)

from tooling.mpc_runtime.app import app  # noqa: E402
from tooling.mpc_runtime.storage.redis_store import RedisRuntimeStore  # noqa: E402


def _configure_real_redis_store() -> None:
    url = os.environ.get("MPC_RUNTIME_REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(url, decode_responses=False)
        r.ping()
    except Exception:
        pytest.skip("Real Redis not available; set MPC_RUNTIME_REDIS_URL to run runtime tests.", allow_module_level=True)
    app.state.runtime_store = RedisRuntimeStore(redis=r, prefix=f"mpc_runtime_test:{uuid.uuid4().hex}")


_configure_real_redis_store()
client = TestClient(app)


DSL = """
@schema 1
@namespace "t"
@name "t"
@version "1.0.0"

def FormDef signup "Kayıt" {
  def FieldDef email { type: "string" required: true }
}
""".strip()


def test_forms_package_manifest_text_ok() -> None:
    response = client.post(
        "/api/v1/rule-artifacts/runtime/forms/package",
        json={
            "tenant_id": "t1",
            "source": {"manifest_text": DSL},
            "form_id": "signup",
            "data": {},
            "actor_roles": ["user"],
            "actor_attrs": {},
        },
        headers={"Idempotency-Key": "req-1", "X-Tenant-Id": "t1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-1"
    assert "duration_ms" in body
    assert body["form_contract_version"] == "1.0.0"
    assert body["json_schema"]["type"] == "object"
    assert "email" in body["json_schema"]["properties"]


def test_forms_package_missing_active_artifact() -> None:
    response = client.post(
        "/api/v1/rule-artifacts/runtime/forms/package",
        json={
            "tenant_id": "t2",
            "source": {},
            "form_id": "signup",
            "data": {},
        },
        headers={"X-Tenant-Id": "t2"},
    )
    assert response.status_code in (409, 400)
    detail = response.json()["detail"]
    assert detail["code"] in ("E_RUNTIME_ACTIVE_REQUIRED",)


def test_forms_package_quota_breach_returns_e_quota_code() -> None:
    response = client.post(
        "/api/v1/rule-artifacts/runtime/forms/package",
        json={
            "tenant_id": "t1",
            "source": {"manifest_text": DSL},
            "form_id": "signup",
            "data": {},
            "limits": {"maxTotalDefs": 0},
        },
        headers={"X-Tenant-Id": "t1"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert str(detail["code"]).startswith("E_QUOTA_")

