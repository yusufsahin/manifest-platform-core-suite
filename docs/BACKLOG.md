# MPC Backlog — v1.1

**Target:** Python library suite. See [CONSUMING_APP_MODEL.md](CONSUMING_APP_MODEL.md) for integration context.

---

## Global DoD

- Contract schema updated (if applicable)
- Conformance fixture added/updated and passes runner
- Determinism tests added (stable hash)
- Error/Reason codes registered in ERROR_CODE_REGISTRY.md
- Trace + Error redaction validated
- Public Python API + Ports documented
- Type hints complete (PEP 484)
- `pip install mpc-<package>` works

---

## EPIC A — Contracts + Canonicalization

- A1 Python dataclasses for EventEnvelope, Decision, Error, Intent, Trace (from JSON Schemas)
- A2 Canonical JSON serializer + stable SHA-256 hash
- A3 Error code registry loader + validator (fails on unknown codes)
- A4 Reason code registry loader + validator

## EPIC B — AST + Meta + Parser + Validator + Registry

- B1 Canonical AST model + normalization (Python dataclasses)
- B2 DomainMeta engine: kind/type/function validation + breaking-change diff
- B3 Parser frontends: YAML → AST, JSON → AST, DSL → AST
- B4 Structural validator (meta schema rules)
- B5 Semantic validator: duplicates, unresolved refs, cycle detection
- B6 Deterministic registry compile + cache key (astHash + metaHash + engineVersion)

## EPIC C — Expression Engine

- C1 Expr IR + JSON form (no host eval)
- C2 Type checker: strict typing, unknown function rejection
- C3 Evaluator + clock injection
- C4 Budget enforcer: steps, depth, timeMs, regexOps — deterministic failures

## EPIC D — Engines + Composition

- D1 core-fsm: pure FSM + E_WF_* validations
- D2 core-workflow: GuardPort + AuthPort binding, Decision output
- D3 core-policy: event matcher + expr + deny-wins ordering
- D4 core-acl: RBAC + optional ABAC + maskField Intent output
- D5 core-ui-schema: deterministic UI schema generator from AST
- D6 core-decision-compose: deny-wins + Intent dedupe by (kind, target, idempotencyKey)

## EPIC E — Overlay / Imports / Namespaces

- E1 core-overlay: replace | merge | append | remove | patch ops + conflict hard errors
- E2 Stable selectors: (kind, namespace, id)
- E3 Imports + alias + semver constraints + collision errors

## EPIC F — Enterprise Governance

- F1 Artifact bundle: compiled + provenance + sbom + attestations + signature
- F2 Signing + verification ports (pluggable algorithm)
- F3 Activation protocol: upload → verify → attest → atomic swap → audit → cache invalidate
- F4 Rollout/rollback + kill switch (policy-off / read-only modes)
- F5 Tenant quota enforcement: parse/compile/eval + E_QUOTA_* errors

## EPIC G — Security Hardening

- G1 Redaction engine: denyKeys masking across Trace, Error.details, log outputs
- G2 Safe regex policy: maxRegexOps budget + ReDoS detection
- G3 Plugin governance: trust levels, declarative capabilities, signing

## EPIC H — Conformance Suite & CI Gates

- H1 Fixture pack v1.0 coverage: all 10 categories, ≥2 fixtures each
- H2 Python conformance runner (`mpc-conformance` package)
- H3 CI gate: all fixtures pass before merge
- H4 Release gates + compatibility matrix + semver bump rules

## EPIC I — Python Packaging & Developer Experience

- I1 `mpc-core-contracts` PyPI package (dataclasses + JSON Schema validation)
- I2 `mpc-core-canonical` PyPI package
- I3 Feature packages: mpc-core-parser, mpc-core-validator, mpc-core-expr, mpc-core-policy, mpc-core-acl, mpc-core-workflow, mpc-core-overlay, mpc-core-decision-compose, mpc-core-trace
- I4 `mpc-enterprise-*` packages (governance, activation, quotas)
- I5 `mpc-conformance` CLI package
- I6 Type stubs + py.typed markers for all packages
- I7 Getting-started example: consuming app in <50 lines
- I8 Changelog + migration guide for breaking schema/API changes
