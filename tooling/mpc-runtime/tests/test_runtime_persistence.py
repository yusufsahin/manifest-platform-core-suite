from __future__ import annotations

import os
import tempfile

import uuid
import pytest
import redis
from fastapi.testclient import TestClient

from tooling.mpc_runtime.app import app
from tooling.mpc_runtime.storage.redis_store import RedisRuntimeStore


def _client_with_shared_store() -> tuple[TestClient, RedisRuntimeStore, tempfile.TemporaryDirectory]:
    blobs = tempfile.TemporaryDirectory()
    url = os.environ.get("MPC_RUNTIME_REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(url, decode_responses=False)
        r.ping()
    except Exception:
        pytest.skip("Real Redis not available; set MPC_RUNTIME_REDIS_URL to run runtime persistence tests.")

    store = RedisRuntimeStore(redis=r, prefix=f"mpc_runtime_test:{uuid.uuid4().hex}")
    app.state.runtime_store = store
    os.environ["MPC_RUNTIME_BLOB_DIR"] = blobs.name
    # Recreate blob store per test to simulate new process if needed.
    if hasattr(app.state, "blob_store"):
        delattr(app.state, "blob_store")
    return TestClient(app), store, blobs


DSL = """
@schema 1
@namespace "t"
@name "t"
@version "1.0.0"

def FormDef signup "Kayıt" {
  def FieldDef email { type: "string" required: true }
}
""".strip()


def test_form_package_uses_canary_routing_when_configured() -> None:
    client, _, _ = _client_with_shared_store()

    # Create stable artifact A and canary artifact B
    a = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL})
    dsl_canary = DSL.replace('def FieldDef email { type: "string" required: true }', 'def FieldDef email { type: "string" required: true }\n  def FieldDef name { type: "string" }')
    b = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": dsl_canary})
    a_id = a.json()["id"]
    b_id = b.json()["id"]
    a_checksum = a.json()["checksum"]
    b_checksum = b.json()["checksum"]
    assert a_checksum != b_checksum

    # Publish both
    for artifact_id in (a_id, b_id):
        client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1", headers={"X-Actor-Roles": "author"})
        client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1", headers={"X-Actor-Roles": "reviewer"})
        client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1", headers={"X-Actor-Roles": "publisher"})

    # Activate stable A
    client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": a_id, "enterprise_mode": False},
        headers={"X-Actor-Roles": "deployer"},
    )

    # Set canary B weight=1.0 so it always wins
    client.post(
        "/api/v1/tenants/t1/activation/canary",
        json={"artifact_id": b_id, "weight": 1.0},
        headers={"X-Actor-Roles": "deployer"},
    )

    r = client.post(
        "/api/v1/rule-artifacts/runtime/forms/package",
        json={
            "tenant_id": "t1",
            "source": {},
            "form_id": "signup",
            "data": {},
            "actor_roles": ["user"],
            "actor_attrs": {"id": "actor-1"},
        },
        headers={"X-Tenant-Id": "t1", "X-Actor-Id": "actor-1"},
    )
    assert r.status_code == 200
    body = r.json()
    # Selected artifact hash should be canary's checksum (different from stable).
    assert body["artifact_hash"] == b_checksum


def test_activation_idempotency_dedupes_response() -> None:
    client, _, _ = _client_with_shared_store()

    create = client.post(
        "/api/v1/rule-artifacts",
        json={"tenant_id": "t1", "manifest_text": DSL, "signature": None},
    )
    assert create.status_code == 200
    artifact_id = create.json()["id"]

    # Must publish before activation: draft -> review -> approved -> published.
    r1 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1",
        headers={"X-Actor-Roles": "author"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1",
        headers={"X-Actor-Roles": "reviewer"},
    )
    assert r2.status_code == 200
    r3 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1",
        headers={"X-Actor-Roles": "publisher"},
    )
    assert r3.status_code == 200

    r1 = client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": artifact_id, "enterprise_mode": False},
        headers={"Idempotency-Key": "idem-1", "X-Actor-Roles": "deployer"},
    )
    assert r1.status_code == 200
    body1 = r1.json()

    r2 = client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": artifact_id, "enterprise_mode": False},
        headers={"Idempotency-Key": "idem-1", "X-Actor-Roles": "deployer"},
    )
    assert r2.status_code == 200
    body2 = r2.json()

    assert body1 == body2


def test_restart_simulation_keeps_active_pointer_and_audit() -> None:
    client, store, _ = _client_with_shared_store()

    create = client.post(
        "/api/v1/rule-artifacts",
        json={"tenant_id": "t1", "manifest_text": DSL, "signature": None},
    )
    artifact_id = create.json()["id"]

    r1 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1",
        headers={"X-Actor-Roles": "author"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1",
        headers={"X-Actor-Roles": "reviewer"},
    )
    assert r2.status_code == 200
    r3 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1",
        headers={"X-Actor-Roles": "publisher"},
    )
    assert r3.status_code == 200

    act = client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": artifact_id, "enterprise_mode": False},
        headers={"X-Actor-Roles": "deployer"},
    )
    assert act.status_code == 200

    # Simulate process restart: new client, same store instance.
    app.state.runtime_store = store
    if hasattr(app.state, "activation_protocols"):
        delattr(app.state, "activation_protocols")

    client2 = TestClient(app)
    status = client2.get("/api/v1/tenants/t1/activation/status", headers={"X-Actor-Roles": "auditor"})
    assert status.status_code == 200
    body = status.json()
    assert body["active"]["id"] == artifact_id
    assert len(body["audit_tail"]) >= 1


def test_audit_export_supports_pagination() -> None:
    client, _, _ = _client_with_shared_store()

    # Create and activate twice to produce multiple audit records.
    create = client.post(
        "/api/v1/rule-artifacts",
        json={"tenant_id": "t1", "manifest_text": DSL, "signature": None},
    )
    artifact_id = create.json()["id"]

    r1 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1",
        headers={"X-Actor-Roles": "author"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1",
        headers={"X-Actor-Roles": "reviewer"},
    )
    assert r2.status_code == 200
    r3 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1",
        headers={"X-Actor-Roles": "publisher"},
    )
    assert r3.status_code == 200

    client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": artifact_id, "enterprise_mode": False},
        headers={"X-Actor-Roles": "deployer"},
    )
    client.post(
        "/api/v1/tenants/t1/activation/mode",
        json={"mode": "policy-off"},
        headers={"X-Actor-Roles": "admin"},
    )

    p1 = client.get("/api/v1/tenants/t1/activation/audit?limit=1", headers={"X-Actor-Roles": "auditor"})
    assert p1.status_code == 200
    body1 = p1.json()
    assert len(body1["items"]) == 1
    assert body1["next_cursor"] is not None

    p2 = client.get(
        f"/api/v1/tenants/t1/activation/audit?limit=10&cursor={body1['next_cursor']}",
        headers={"X-Actor-Roles": "auditor"},
    )
    assert p2.status_code == 200
    body2 = p2.json()
    assert len(body2["items"]) >= 1


def test_legacy_activate_endpoint_is_deprecated() -> None:
    client, _, _ = _client_with_shared_store()
    create = client.post(
        "/api/v1/rule-artifacts",
        json={"tenant_id": "t1", "manifest_text": DSL, "signature": None},
    )
    artifact_id = create.json()["id"]
    resp = client.post(f"/api/v1/rule-artifacts/{artifact_id}/activate", params={"tenant_id": "t1"})
    assert resp.status_code == 410
    assert resp.json()["detail"]["code"] == "E_RUNTIME_DEPRECATED"


def test_mode_idempotency_dedupes() -> None:
    client, _, _ = _client_with_shared_store()
    r1 = client.post(
        "/api/v1/tenants/t1/activation/mode",
        json={"mode": "policy-off"},
        headers={"X-Actor-Roles": "admin", "Idempotency-Key": "mode-1"},
    )
    assert r1.status_code == 200
    body1 = r1.json()
    r2 = client.post(
        "/api/v1/tenants/t1/activation/mode",
        json={"mode": "policy-off"},
        headers={"X-Actor-Roles": "admin", "Idempotency-Key": "mode-1"},
    )
    assert r2.status_code == 200
    assert r2.json() == body1


def test_lifecycle_idempotency_dedupes() -> None:
    client, _, _ = _client_with_shared_store()
    create = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL, "signature": None})
    artifact_id = create.json()["id"]

    r1 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1",
        headers={"X-Actor-Roles": "author", "Idempotency-Key": "lc-1"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1",
        headers={"X-Actor-Roles": "author", "Idempotency-Key": "lc-1"},
    )
    assert r2.status_code == 200
    assert r2.json() == r1.json()


def _publish_two_artifacts(client: TestClient) -> tuple[str, str]:
    a = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL})
    dsl_b = DSL.replace('def FieldDef email { type: "string" required: true }', 'def FieldDef email { type: "string" required: true }\n  def FieldDef name { type: "string" }')
    b = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": dsl_b})
    a_id = a.json()["id"]
    b_id = b.json()["id"]
    for artifact_id in (a_id, b_id):
        client.post(
            f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1",
            headers={"X-Actor-Roles": "author"},
        )
        client.post(
            f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1",
            headers={"X-Actor-Roles": "reviewer"},
        )
        client.post(
            f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1",
            headers={"X-Actor-Roles": "publisher"},
        )
    return a_id, b_id


def test_canary_idempotency_dedupes() -> None:
    client, _, _ = _client_with_shared_store()
    a_id, b_id = _publish_two_artifacts(client)
    client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": a_id, "enterprise_mode": False},
        headers={"X-Actor-Roles": "deployer"},
    )
    h = {"X-Actor-Roles": "deployer", "Idempotency-Key": "canary-idem-1"}
    body = {"artifact_id": b_id, "weight": 0.5}
    r1 = client.post("/api/v1/tenants/t1/activation/canary", json=body, headers=h)
    assert r1.status_code == 200
    r2 = client.post("/api/v1/tenants/t1/activation/canary", json=body, headers=h)
    assert r2.status_code == 200
    assert r2.json() == r1.json()


def test_promote_canary_idempotency_dedupes() -> None:
    client, _, _ = _client_with_shared_store()
    a_id, b_id = _publish_two_artifacts(client)
    client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": a_id, "enterprise_mode": False},
        headers={"X-Actor-Roles": "deployer"},
    )
    client.post(
        "/api/v1/tenants/t1/activation/canary",
        json={"artifact_id": b_id, "weight": 1.0},
        headers={"X-Actor-Roles": "deployer"},
    )
    h = {"X-Actor-Roles": "deployer", "Idempotency-Key": "promote-idem-1"}
    r1 = client.post("/api/v1/tenants/t1/activation/promote-canary", headers=h)
    assert r1.status_code == 200
    r2 = client.post("/api/v1/tenants/t1/activation/promote-canary", headers=h)
    assert r2.status_code == 200
    assert r2.json() == r1.json()


def test_rollback_idempotency_dedupes() -> None:
    client, _, _ = _client_with_shared_store()
    a_id, b_id = _publish_two_artifacts(client)
    client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": a_id, "enterprise_mode": False},
        headers={"X-Actor-Roles": "deployer"},
    )
    client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": b_id, "enterprise_mode": False},
        headers={"X-Actor-Roles": "deployer"},
    )
    h = {"X-Actor-Roles": "deployer", "Idempotency-Key": "rollback-idem-1"}
    r1 = client.post("/api/v1/tenants/t1/activation/rollback", headers=h)
    assert r1.status_code == 200
    r2 = client.post("/api/v1/tenants/t1/activation/rollback", headers=h)
    assert r2.status_code == 200
    assert r2.json() == r1.json()

