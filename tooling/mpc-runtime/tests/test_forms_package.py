from __future__ import annotations

from fastapi.testclient import TestClient

from tooling.mpc_runtime.app import app


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

