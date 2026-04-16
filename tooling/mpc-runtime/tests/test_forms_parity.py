from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from mpc.features.form import FORM_CONTRACT_VERSION
from mpc.features.form.engine import FormEngine
from mpc.features.form.kinds import FORM_KINDS
from mpc.kernel.meta.models import DomainMeta
from mpc.kernel.parser import parse
from tooling.mpc_runtime.app import app


client = TestClient(app)


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "packages" / "core-conformance" / "fixtures" / "form"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _local_form_package(payload: dict[str, Any]) -> dict[str, Any]:
    dsl = payload["dsl"]
    form_id = payload["form_id"]
    data = payload.get("data") or {}
    actor_roles = payload.get("actor_roles") or []
    actor_attrs = payload.get("actor_attrs") or {}
    fail_open = bool(payload.get("fail_open", True))

    ast = parse(dsl)
    meta = DomainMeta(kinds=[*FORM_KINDS])
    engine = FormEngine(ast=ast, meta=meta)
    pkg = engine.get_form_package(
        form_id,
        data,
        actor_roles=actor_roles,
        actor_attrs=actor_attrs,
        fail_open=fail_open,
    )
    return {
        "json_schema": pkg.jsonSchema,
        "ui_schema": pkg.uiSchema,
        "field_state": pkg.fieldState,
        "validation": pkg.validation,
    }


def _remote_form_package(payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/rule-artifacts/runtime/forms/package",
        json={
            "tenant_id": "t-parity",
            "source": {"manifest_text": payload["dsl"]},
            "form_id": payload["form_id"],
            "data": payload.get("data") or {},
            "actor_roles": payload.get("actor_roles") or [],
            "actor_attrs": payload.get("actor_attrs") or {},
            "fail_open": payload.get("fail_open", True),
        },
        headers={"Idempotency-Key": "req-parity", "X-Tenant-Id": "t-parity"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("form_contract_version") == FORM_CONTRACT_VERSION
    return {
        "json_schema": body["json_schema"],
        "ui_schema": body["ui_schema"],
        "field_state": body["field_state"],
        "validation": body["validation"],
    }


def _assert_parity_case(case_dir: Path) -> None:
    input_payload = _read_json(case_dir / "input.json")
    expected = _read_json(case_dir / "expected.json")

    local_pkg = _local_form_package(input_payload)
    remote_pkg = _remote_form_package(input_payload)

    assert local_pkg == expected
    assert remote_pkg == expected
    assert remote_pkg == local_pkg


def test_forms_parity_basic_required() -> None:
    _assert_parity_case(FIXTURES / "01_basic_required")


def test_forms_parity_visibility_readonly_expr() -> None:
    _assert_parity_case(FIXTURES / "02_visibility_readonly_expr")


def test_forms_parity_acl_mask_readonly() -> None:
    _assert_parity_case(FIXTURES / "03_acl_mask_readonly")


def test_forms_strict_validation_unknown_prop() -> None:
    dsl = (
        "@schema 1\n"
        "@namespace \"t\"\n"
        "@name \"t\"\n"
        "@version \"1.0.0\"\n\n"
        "def FormDef profile \"Profile\" {\n"
        "  def FieldDef nickname \"Nickname\" { type: \"string\" bogusProp: 1 }\n"
        "}\n"
    )
    payload = {"dsl": dsl, "form_id": "profile", "data": {}, "actor_roles": ["user"], "actor_attrs": {}, "fail_open": True}

    # Remote should reject the manifest shape in strict mode.
    response = client.post(
        "/api/v1/rule-artifacts/runtime/forms/package",
        json={
            "tenant_id": "t-parity",
            "source": {"manifest_text": dsl},
            "form_id": payload["form_id"],
            "data": payload["data"],
            "actor_roles": payload["actor_roles"],
            "actor_attrs": payload["actor_attrs"],
            "fail_open": payload["fail_open"],
            "strict_validation": True,
        },
        headers={"Idempotency-Key": "req-parity", "X-Tenant-Id": "t-parity"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] in ("MANIFEST_INVALID_SHAPE",)

