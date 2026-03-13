# Changelog

All notable changes to MPC (Manifest Platform Core Suite) will be documented here.

## [0.1.0] — 2026-02-22

### Added

**Epic A — Kernel (`mpc.kernel`)**
- `mpc.kernel.contracts`: Immutable Python dataclasses for EventEnvelope, Decision, Error, Intent, Trace
- `mpc.kernel.canonical`: Canonical JSON serializer with deterministic key sorting + stable SHA-256 hash
- `mpc.kernel.errors`: Error code registry with E_* codes and validation enforcement
- `mpc.kernel.meta`: Domain metadata and kind definitions
- Reason code registry with R_* codes
- Intent kind taxonomy (maskField, notify, audit, etc.)

**Epic B — Kernel & Tooling (`mpc.kernel`, `mpc.tooling`)**
- `mpc.kernel.ast`: Canonical AST model (ManifestAST, ASTNode) with normalization
- `mpc.kernel.parser`: DSL (Lark), YAML, and JSON frontends
- `mpc.tooling.validator`: Structural and semantic validation rules
- `mpc.tooling.registry`: Deterministic artifact compilation

**Epic C — Features (`mpc.features.expr`)**
- Typed IR with JSON form: lit, ref, fn, op, not, neg, if/then/else
- Type checker with strict typing and type compatibility
- Evaluator with 14 built-in functions (len, lower, upper, contains, etc.)
- Clock injection for deterministic `now()` evaluation
- Full budget enforcement: steps, depth, timeMs, regexOps

**Epic D — Features & Tooling (`mpc.features.*`, `mpc.tooling.uischema`)**
- `mpc.features.workflow`: Native FSM engine with Port interfaces
- `mpc.features.policy`: Event matching, deny-wins ordering, intent collection
- `mpc.features.acl`: RBAC, ABAC, role hierarchy
- `mpc.tooling.uischema`: Deterministic UI schema generator

**Epic E — Features & Tooling (`mpc.features.overlay`, `mpc.tooling.imports`)**
- `mpc.features.overlay`: replace, merge, append, remove, patch operations
- Stable selectors: (kind, namespace, id) with both dict and shorthand formats
- `mpc.tooling.imports`: Resolver with aliasing and semver

**Epic F — Enterprise Governance (`mpc.enterprise.governance`)**
- Artifact bundle format: compiled registry + provenance + SBOM + attestations
- Signing and verification ports (pluggable algorithm)
- Activation protocol: upload → verify → attest → swap → audit → invalidate
- Per-tenant quota enforcement: parse/compile/eval/node/def limits

**Epic G — Features (`mpc.features.redaction`)**
- Redaction engine: denyKeys masking across all data structures
- Default deny keys: password, token, apiKey, ssn, etc.
- Pattern-based key matching with glob support

**Epic H — Tooling (`mpc.tooling.conformance`)**
- `mpc.tooling.conformance`: Fixture packs with runner
- GitHub Actions CI: multi-Python matrix, conformance gate, release gate

**Epic I — Packaging & Developer Experience**
- Hierarchical namespaces (`mpc.kernel`, `mpc.features`, etc.)
- Getting-started example in under 50 lines
- Changelog and migration guide
