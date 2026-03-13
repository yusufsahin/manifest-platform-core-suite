# MPC Backlog — v1.1

**Target:** Python library suite. See [CONSUMING_APP_MODEL.md](CONSUMING_APP_MODEL.md) for integration context.

---

## Global DoD

- Contract schema updated (if applicable)
- Conformance fixture added/updated and passes runner
- Determinism tests added (stable hash)
- Error/Reason codes registered in ERROR_CODE_REGISTRY.md
- Trace/Error redaction (denyKeys) validated where applicable; **PII is out of scope** (see [SCOPE.md](SCOPE.md))
- Public Python API + Ports documented
- Type hints complete (PEP 484)
- `pip install mpc-<package>` works

---

## EPIC A — Kernel: Contracts + Canonical (`mpc.kernel`)

- A1 `mpc.kernel.contracts`: Python dataclasses for EventEnvelope, Decision, Error, Intent, Trace
- A2 `mpc.kernel.canonical`: JSON serializer + stable SHA-256 hash
- A3 `mpc.kernel.errors`: Error code registry loader + validator
- A4 Reason code registry (R_* codes)

## EPIC B — Kernel & Tooling: AST + Parser + Validator (`mpc.kernel`, `mpc.tooling`)

- B1 `mpc.kernel.ast`: Canonical AST model + normalization
- B2 `mpc.kernel.meta`: DomainMeta engine: kind/type/function validation
- B3 `mpc.kernel.parser`: Frontends (DSL, YAML, JSON) → AST
- B4 `mpc.tooling.validator`: Structural and semantic validation rules
- B5 Deterministic registry compilation with `mpc.tooling.registry`

## EPIC C — Features: Expression Engine (`mpc.features.expr`)

- C1 Expr IR + JSON form (no host eval)
- C2 Type checker: strict typing, unknown function rejection
- C3 Evaluator + clock injection
- C4 Budget enforcer: steps, depth, timeMs, regexOps

## EPIC D — Features: Engines & Tooling (`mpc.features.*`, `mpc.tooling.uischema`)

- D1 `mpc.features.workflow`: Native FSM + Port binding
- D2 `mpc.features.policy`: Event matcher + expr + deny-wins ordering
- D3 `mpc.features.acl`: RBAC + ABAC + field masking
- D4 `mpc.tooling.uischema`: Deterministic UI schema generator
- D5 `mpc.features.compose`: Decision composition strategies

## EPIC E — Features & Tooling: Overlay & Imports (`mpc.features.overlay`, `mpc.tooling.imports`)

- E1 `mpc.features.overlay`: replace | merge | append | remove | patch ops
- E2 Stable selectors: (kind, namespace, id)
- E3 `mpc.tooling.imports`: Resolver with aliasing and semver

## EPIC F — Enterprise Governance (`mpc.enterprise.*`)

- F1 `mpc.enterprise.governance`: Artifact bundle + Provenance + SBom
- F2 Signing + verification ports (pluggable)
- F3 Activation protocol: verify → attest → swap → audit
- F4 ROLLBACK + Kill switch (policy-off / read-only)
- F5 Quota enforcer: E_QUOTA_* errors

## EPIC G — Features: Security (`mpc.features.redaction`)

- G1 `mpc.features.redaction`: **denyKeys** masking across Trace and Error
- G2 Safe regex budget policies

## EPIC H — Conformance Suite & CI Gates

- H1 Fixture pack v1.0 coverage: all 10 categories, ≥2 fixtures each
- H2 Python conformance runner (`mpc-conformance` package)
- H3 CI gate: all fixtures pass before merge
- H4 Release gates + compatibility matrix + semver bump rules

## EPIC I — Packaging & DX

- I1 Hierarchical namespaces (`mpc.kernel`, `mpc.features`, etc.)
- I2 Type stubs + py.typed markers
- I3 Getting-started example: consuming app in <50 lines
- I4 Changelog + migration guide
