# MPC Studio Enterprise Baseline

## Scope

This baseline anchors the "enterprise-ready" rollout for MPC Studio workflow simulation and governance.

## KPI Baseline

- Gate health: `test:contracts` + `test:conformance` + `test:e2e` as release gate path.
- Workflow simulator parity: separate workflow state-transition panel exists (not policy-coupled).
- Explainability: step-level reasons, errors, and remediation hints are visible in UI.
- Auditability: every user action writes an in-memory audit event with actor/tenant/run metadata.
- Contract governance: workflow error/reason codes are validated against a registry via gate.
- Benchmark automation: `npm run test:benchmark` reports step/run/export p50-p95 metrics.

## Performance Thresholds

- Step p95 target: `< 120ms`
- Run p95 target: `< 300ms`
- Export p95 target: `< 500ms`
- Enforcement mode: `npm run test:benchmark:enforce`

## Ownership Matrix

- Product owner: define simulator UX acceptance and release bar.
- Platform engineer: maintain worker/runtime stability and contract versioning.
- Frontend engineer: maintain Workflow/Policy simulator UX and E2E reliability.
- QA owner: own release gate execution and fixture/golden trace hygiene.

## Phase RACI

| Phase | Owner | Reviewer | On-call |
|---|---|---|---|
| Phase 0 Alignment | Product owner | QA owner | Platform engineer |
| Phase 1 Runtime stabilization | Platform engineer | Frontend engineer | Platform engineer |
| Phase 2 Workflow trace UX | Frontend engineer | Product owner | Frontend engineer |
| Phase 3 Explainability UX | Frontend engineer | Product owner | Frontend engineer |
| Phase 4 Audit/versioning MVP | Platform engineer | QA owner | Platform engineer |
| Phase 5 Type/contract hygiene | Platform engineer | Frontend engineer | Platform engineer |
| Phase 6 Tests/gates | QA owner | Platform engineer | QA owner |
| Phase 7 Contract governance | Platform engineer | QA owner | Platform engineer |

## Risk and Dependency Matrix

- Runtime dependency risk: Pyodide package drift (`lark`, `pyyaml`) can break parser load.
- Contract drift risk: new error codes without registry update must fail in contract gate.
- UX drift risk: step traces can regress if simulator UI and runtime schema diverge.
- Test flakiness risk: cold-start engine boot timing requires robust waits in E2E.

## Release Criteria (MVP+)

- Contract gate passes with no unknown error/reason codes.
- Conformance gate passes for required fixture categories.
- Workflow E2E covers step, run, permission deny, limits, export, and snapshot restore.
- Kill switch is validated: `VITE_WORKFLOW_TRACE_V2=false` keeps simulator in legacy trace mode.

## Rollout and Kill Switch

- Feature flag: `VITE_WORKFLOW_TRACE_V2`
  - default: enabled (`true`)
  - emergency rollback: set to `false` to disable trace v2 details/snapshot controls
- Canary recommendation:
  - enable in internal tenant first
  - then pilot tenant
  - then general release
