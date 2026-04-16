from __future__ import annotations

import os
import tempfile

import jwt
import json
import uuid
import pytest
import redis
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa

from tooling.mpc_runtime.app import app
from tooling.mpc_runtime.storage.redis_store import RedisRuntimeStore


DSL = """
@schema 1
@namespace "t"
@name "t"
@version "1.0.0"

def Policy p1 { rules: [] }
""".strip()


def _client() -> tuple[TestClient, dict]:
    blobs = tempfile.TemporaryDirectory()
    url = os.environ.get("MPC_RUNTIME_REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(url, decode_responses=False)
        r.ping()
    except Exception:
        pytest.skip("Real Redis not available; set MPC_RUNTIME_REDIS_URL to run JWKS signature tests.")

    app.state.runtime_store = RedisRuntimeStore(redis=r, prefix=f"mpc_runtime_test:{uuid.uuid4().hex}")
    os.environ["MPC_RUNTIME_BLOB_DIR"] = blobs.name
    if hasattr(app.state, "blob_store"):
        delattr(app.state, "blob_store")
    return TestClient(app), {}


def _make_rsa_jwk(kid: str) -> tuple[str, dict]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = RSAAlgorithm.to_jwk(key.public_key())
    jwk_dict = json.loads(public_jwk)
    jwk_dict["kid"] = kid
    return key, jwk_dict  # type: ignore[return-value]


def test_rs256_verify_allows_key_rotation_by_kid() -> None:
    client, _ = _client()

    priv1, jwk1 = _make_rsa_jwk("k1")
    priv2, jwk2 = _make_rsa_jwk("k2")
    jwks = {"keys": [jwk1, jwk2]}

    from mpc.kernel.canonical.hash import stable_hash

    payload_hash = stable_hash(DSL)
    token = jwt.encode({"payload_hash": payload_hash}, key=priv2, algorithm="RS256", headers={"kid": "k2"})

    create = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL, "signature": token})
    artifact_id = create.json()["id"]

    # draft -> review -> approved -> published
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1", headers={"X-Actor-Roles": "author"})
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1", headers={"X-Actor-Roles": "reviewer"})
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1", headers={"X-Actor-Roles": "publisher"})

    act = client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": artifact_id, "enterprise_mode": True, "verification": {"algorithm": "RS256", "jwks": jwks}},
        headers={"X-Actor-Roles": "deployer"},
    )
    assert act.status_code == 200


def test_rs256_verify_rejects_payload_hash_mismatch() -> None:
    client, _ = _client()

    priv, jwk = _make_rsa_jwk("k1")
    jwks = {"keys": [jwk]}

    token = jwt.encode({"payload_hash": "wrong"}, key=priv, algorithm="RS256", headers={"kid": "k1"})

    create = client.post("/api/v1/rule-artifacts", json={"tenant_id": "t1", "manifest_text": DSL, "signature": token})
    artifact_id = create.json()["id"]
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/submit_review?tenant_id=t1", headers={"X-Actor-Roles": "author"})
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/approve?tenant_id=t1", headers={"X-Actor-Roles": "reviewer"})
    client.post(f"/api/v1/rule-artifacts/{artifact_id}/lifecycle/publish?tenant_id=t1", headers={"X-Actor-Roles": "publisher"})

    act = client.post(
        "/api/v1/tenants/t1/activation/activate",
        json={"artifact_id": artifact_id, "enterprise_mode": True, "verification": {"algorithm": "RS256", "jwks": jwks}},
        headers={"X-Actor-Roles": "deployer"},
    )
    assert act.status_code == 400
    assert act.json()["detail"]["code"] == "E_GOV_SIGNATURE_INVALID"
