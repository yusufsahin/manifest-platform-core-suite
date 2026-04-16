# Contract Matrix (Studio ↔ Worker ↔ Runtime)

This document is the single reference for contract shapes, versioning, and mapping rules between:

- **Studio UI** (TypeScript / React)
- **Local runtime** (Pyodide Worker running Python `mpc`)
- **Remote runtime** (`tooling/mpc_runtime` FastAPI)

## 1) Worker envelope (Studio ⇄ Worker)

### Source of truth (Envelope)

- Envelope type: `tooling/mpc-studio/src/types/definition.ts` (`WorkerEnvelope<TPayload>`)
- Worker emitter: `tooling/mpc-studio/src/engine/worker.ts` (`postEnvelope(...)`)
- Studio unwrap + metrics: `tooling/mpc-studio/src/engine/mpc-engine.ts` (`unwrapEnvelopePayload(...)`)

### Shape

```json
{
  "contractVersion": "2.0.0",
  "requestId": "uuid-or-idem-key",
  "timestamp": "ISO-8601",
  "type": "FORM_PACKAGE|WORKFLOW_STEP|...",
  "payload": {},
  "diagnostics": [{ "code": "...", "message": "...", "severity": "info|warning|error" }],
  "durationMs": 12
}
```

### Notes

- `contractVersion` here refers to the **envelope contract** (`DEFINITION_CONTRACT_VERSION`), not the inner payload.
- Studio uses the envelope to capture metrics + diagnostics consistently across features.

## 2) Workflow simulation contract

### Source of truth (Workflow)

- Types + version: `tooling/mpc-studio/src/types/workflow.ts` (`WORKFLOW_CONTRACT_VERSION = "1.0.0"`)
- Local execution: `tooling/mpc-studio/src/engine/worker.ts` (`WORKFLOW_STEP`, `WORKFLOW_RUN`)
- Remote execution mapping: `tooling/mpc-studio/src/engine/mpc-engine.ts` (`workflowStepRemote`, `workflowRunRemote`)

### Local (Worker → Studio)

- `WORKFLOW_STEP` returns:

```json
{
  "initialState": "START",
  "currentState": "QUALIFYING",
  "step": {
    "stepId": "wf-step-...",
    "event": "begin",
    "from": "START",
    "to": "QUALIFYING",
    "allow": true,
    "guardResult": "pass|fail|not_applicable",
    "reasons": [{ "code": "R_...", "summary": "..." }],
    "errors": [{ "code": "E_...", "message": "..." }],
    "actionsExecuted": [],
    "errorCode": "INVALID_TRANSITION|...",
    "remediationHint": "..."
  },
  "availableTransitions": [{ "from": "...", "event": "...", "to": "...", "guard": "..." }]
}
```

### Remote (Runtime → Studio)

- `POST /api/v1/rule-artifacts/runtime/workflow/step|run` (via `mpc-engine.ts`) returns **snake_case** which Studio maps to camelCase.

### Error codes

- Worker normalizes some workflow codes via `toWorkflowErrorCode(...)` in `tooling/mpc-studio/src/engine/worker.ts`.

## 3) FormPackage contract

### 3.1 Remote runtime endpoint

#### Endpoint

- `POST /api/v1/rule-artifacts/runtime/forms/package`
  - Implementation: `tooling/mpc_runtime/app.py` (`form_package(...)`)
  - Tests: `tooling/mpc-runtime/tests/test_forms_package.py`

#### Authentication / Authorization (remote runtime)

Remote runtime supports two auth modes (feature-flagged):

- **Header mode (dev compatibility)**: `MPC_RUNTIME_AUTH_MODE=header` (default)
  - Tenant source: request `tenant_id` or `X-Tenant-Id`
  - Roles source: `X-Actor-Roles: role1,role2`
  - Actor id: `X-Actor-Id`
- **JWT mode (prod)**: `MPC_RUNTIME_AUTH_MODE=jwt`
  - Requires `Authorization: Bearer <JWT>`
  - Tenant is derived from token claims (`tenant_id` or `tid`) and MUST match request tenant.
  - Roles are derived from token claims (`roles` or `role`).
  - JWKS source:
    - `MPC_RUNTIME_JWKS_JSON` (inline JSON) or
    - `MPC_RUNTIME_JWKS_URL` (fetched + cached)

#### Request

```json
{
  "tenant_id": "t1",
  "source": { "manifest_text": "...", "artifact_id": "..." },
  "form_id": "signup",
  "data": {},
  "actor_roles": ["user"],
  "actor_attrs": {},
  "fail_open": true
}
```

#### Response (snake_case)

```json
{
  "request_id": "idem-key-or-uuid",
  "duration_ms": 12,
  "form_contract_version": "1.0.0",
  "json_schema": { "type": "object", "properties": {} },
  "ui_schema": { "ui:order": [] },
  "field_state": [{ "field_id": "email", "visible": true, "readonly": false }],
  "validation": { "valid": true, "errors": [] },
  "diagnostics": []
}
```

### 3.2 Local worker (Pyodide) contract

#### Message

- Studio → Worker: `type: "GENERATE_FORM_PACKAGE"` in `tooling/mpc-studio/src/engine/mpc-engine.ts`

#### Payload returned (camelCase, inside envelope)

```json
{
  "formContractVersion": "1.0.0",
  "jsonSchema": { "type": "object", "properties": {} },
  "uiSchema": { "ui:order": [] },
  "fieldState": [{ "field_id": "email", "visible": true, "readonly": false }],
  "validation": { "valid": true, "errors": [] }
}
```

### 3.3 Studio mapping rules (Remote → Local)

#### Source

- `tooling/mpc-studio/src/engine/mpc-engine.ts` (`generateFormPackage(...)`)

#### Mapping

- `json_schema` → `jsonSchema`
- `ui_schema` → `uiSchema`
- `field_state` → `fieldState`
- `duration_ms/request_id` are currently **not** part of the FormPackage payload; they are tracked via the worker envelope only for local mode.

### 3.4 JSON Schema extensions used by the engine

Engine emits `x-*` fields (see `src/mpc/features/form/engine.py`):

- `x-form-id`
- `x-workflow-state`
- `x-workflow-trigger`
- Per-field extensions (in each property):
  - `x-placeholder`
  - `x-validation-expr`
  - `x-visibility-expr`
  - `x-readonly-expr`

## 4) Known drift points (must be addressed by parity gate)

1. **Case conventions**
   - Remote uses snake_case, Studio uses camelCase.
2. **Metrics location**
   - Local has envelope metrics (`durationMs`, `requestId`).
   - Remote returns metrics in body (`duration_ms`, `request_id`).
3. **Deterministic ordering**
   - `required`, `ui:order`, and `field_state` ordering should be stable.
4. **Error/diagnostics shape**
   - Worker errors are surfaced via envelope diagnostics + controlled payload.
   - Remote errors must conform to `code/message/retryable` contract used by `RemoteRuntimeError` in `mpc-engine.ts`.

## 5) Overlay compose contract (Worker → Studio)

### Source of truth (Overlay)

- Engine: `src/mpc/features/overlay/engine.py` (`OverlayEngine.apply(...)`)
- Worker bridge: `tooling/mpc-studio/src/engine/worker.ts` (`OVERLAY_COMPOSE`)
- Studio types: `tooling/mpc-studio/src/types/overlay.ts`

### Result (inside worker envelope payload)

```json
{
  "applied": ["merge:policy1", "replace:policy1:attributes.effect"],
  "conflicts": [{ "code": "E_OVERLAY_CONFLICT", "message": "..." }],
  "diffs": [
    {
      "key": "Policy:p1",
      "kind": "Policy",
      "id": "p1",
      "before": { "attributes": { "effect": "allow" } },
      "after": { "attributes": { "effect": "deny" } }
    }
  ],
  "trace": [
    {
      "overlay_id": "ov1",
      "op": "replace",
      "selector": { "kind": "Policy", "namespace": "acme", "id": "p1" },
      "target_key": "Policy:p1",
      "path": "attributes.effect",
      "before": "allow",
      "after": "deny"
    }
  ]
}
```

## 6) Strict validation (remote/runtime)

- Remote FormPackage endpoint supports `strict_validation: true` to enforce structural validation of `FormDef/FieldDef` against `FORM_KINDS` (with permissive extra kinds to avoid noise).
