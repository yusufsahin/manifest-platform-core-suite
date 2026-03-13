# Implementation Checklist Pack (Cursor-ready)

## 1) Must-Implement First
- `mpc.kernel.contracts` schemas (Event/Decision/Error/Intent/Trace)
- `mpc.kernel.canonical` (canonical JSON + stable hash)
- `mpc.kernel.errors` registry enforcement
- `mpc.tooling.conformance` runner behavior + minimal fixtures

## 2) Next
- `mpc.kernel.meta` (meta-metadata + diff)
- `mpc.kernel.parser` (DSL/YAML/JSON normalize)
- `mpc.tooling.validator` (structural + semantic)
- `mpc.features.overlay` (merge semantics)
- `mpc.features.expr` (IR + typecheck + eval + budgets)

## 3) Engines
- `mpc.features.workflow` (FSM + Binding)
- `mpc.features.policy`
- `mpc.features.acl`
- `mpc.features.compose`

## 4) Enterprise
- `mpc.enterprise.governance` (bundle/provenance/attest/sbom/signature)
- signing/verification ports
- activation protocol + audit + rollback + canary
- quotas + kill switch
- `mpc.features.redaction`

## 5) Release Gates
- conformance suite 100% pass
- compatibility matrix
- semver bump rules for breaking changes
