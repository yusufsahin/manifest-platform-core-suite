from __future__ import annotations

import json
import os
import tempfile
import uuid

import pytest
import redis
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from tooling.mpc_runtime.app import app
from tooling.mpc_runtime.storage.redis_store import RedisRuntimeStore


def _redis_store() -> RedisRuntimeStore:
    url = os.environ.get("MPC_RUNTIME_REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(url, decode_responses=False)
        r.ping()
    except Exception:
        pytest.skip("Real Redis not available; set MPC_RUNTIME_REDIS_URL to run JWT auth tests.")
    return RedisRuntimeStore(redis=r, prefix=f"mpc_runtime_test:{uuid.uuid4().hex}")


def _jwt_setup() -> tuple[str, dict, object]:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(priv.public_key()))
    jwk["kid"] = "k1"
    jwks = {"keys": [jwk]}
    token = jwt.encode({"tenant_id": "t1", "roles": ["admin", "deployer", "auditor"], "sub": "u1"}, key=priv, algorithm="RS256", headers={"kid": "k1"})
    return token, jwks, priv


def test_jwt_auth_allows_actions_by_claim_roles() -> None:
    token, jwks, _ = _jwt_setup()

    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    blobs = tempfile.TemporaryDirectory()
    try:
        mp.setenv("MPC_RUNTIME_AUTH_MODE", "jwt")
        mp.setenv("MPC_RUNTIME_JWKS_JSON", json.dumps(jwks))
        mp.setenv("MPC_RUNTIME_BLOB_DIR", blobs.name)
        app.state.runtime_store = _redis_store()
        if hasattr(app.state, "blob_store"):
            delattr(app.state, "blob_store")

        client = TestClient(app)

        # admin can set mode
        r = client.post(
            "/api/v1/tenants/t1/activation/mode",
            json={"mode": "policy-off"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

        # deployer can activate (requires artifact published first)
        dsl = (
            "@schema 1\n"
            "@namespace \"t\"\n"
            "@name \"t\"\n"
            "@version \"1.0.0\"\n\n"
            "def FormDef signup \"Signup\" { def FieldDef email { type: \"string\" required: true } }\n"
        )
        create = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": dsl, "signature": None})
        artifact_id = create.json()["id"]
        client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1", headers={"Authorization": f"Bearer {token}"})
        client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1", headers={"Authorization": f"Bearer {token}"})
        client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1", headers={"Authorization": f"Bearer {token}"})

        act = client.post(
            "/api/v1/tenants/t1/activation/activate",
            json={"artifact_id": artifact_id, "enterprise_mode": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert act.status_code == 200

        # auditor can read status
        st = client.get("/api/v1/tenants/t1/activation/status", headers={"Authorization": f"Bearer {token}"})
        assert st.status_code == 200
    finally:
        mp.undo()


def test_jwt_auth_rejects_wrong_tenant() -> None:
    token, jwks, _ = _jwt_setup()
    blobs = tempfile.TemporaryDirectory()
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    mp.setenv("MPC_RUNTIME_AUTH_MODE", "jwt")
    mp.setenv("MPC_RUNTIME_JWKS_JSON", json.dumps(jwks))
    mp.setenv("MPC_RUNTIME_BLOB_DIR", blobs.name)
    app.state.runtime_store = _redis_store()
    if hasattr(app.state, "blob_store"):
        delattr(app.state, "blob_store")
    client = TestClient(app)

    r = client.get("/api/v1/tenants/t2/activation/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "E_RUNTIME_FORBIDDEN"
    mp.undo()


def test_jwt_auth_rejects_missing_token() -> None:
    blobs = tempfile.TemporaryDirectory()
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    mp.setenv("MPC_RUNTIME_AUTH_MODE", "jwt")
    mp.setenv("MPC_RUNTIME_JWKS_JSON", json.dumps({"keys": []}))
    mp.setenv("MPC_RUNTIME_BLOB_DIR", blobs.name)
    app.state.runtime_store = _redis_store()
    if hasattr(app.state, "blob_store"):
        delattr(app.state, "blob_store")
    client = TestClient(app)

    r = client.get("/api/v1/tenants/t1/activation/status")
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "E_RUNTIME_FORBIDDEN"
    mp.undo()

