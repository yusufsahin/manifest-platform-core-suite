# Changelog

All notable changes to MPC (Manifest Platform Core Suite) will be documented here.

## [0.1.0] — 2026-02-22

### Added

**Epic A — Contracts + Canonicalization**
- Immutable Python dataclasses for EventEnvelope, Decision, Error, Intent, Trace
- Canonical JSON serializer with deterministic key sorting + stable SHA-256 hash
- Error code registry with E_* codes and validation enforcement
- Reason code registry with R_* codes
- Intent kind taxonomy (maskField, notify, audit, etc.)

**Epic B — AST + Meta + Parser + Validator + Registry**
- Canonical AST model (ManifestAST, ASTNode) with normalization
- DomainMeta engine: kind/type/function validation + breaking-change diff
- Parser frontends: JSON, YAML, and custom DSL (Lark LALR)
- Structural validator (meta schema rules, function ref checks)
- Semantic validator: duplicates, namespace conflicts, cycle detection, workflow structure
- Deterministic registry compile with astHash + metaHash + engineVersion

**Epic C — Expression Engine**
- Typed IR with JSON form: lit, ref, fn, op, not, neg, if/then/else
- Type checker with strict typing and type compatibility
- Evaluator with 14 built-in functions (len, lower, upper, contains, etc.)
- Clock injection for deterministic `now()` evaluation
- Full budget enforcement: steps, depth, timeMs, regexOps

**Epic D — Engines + Composition**
- Workflow FSM engine with GuardPort and AuthPort interfaces
- Policy engine with event matching, deny-wins ordering, intent collection
- ACL engine with RBAC, ABAC, role hierarchy, and maskField Intent output
- Decision compose: deny-wins strategy + intent deduplication by (kind, target, idempotencyKey)
- Deterministic UI schema generator from AST + DomainMeta

**Epic E — Overlay / Imports / Namespaces**
- Overlay engine with replace, merge, append, remove, patch operations
- Stable selectors: (kind, namespace, id) with both dict and shorthand formats
- Conflict detection for same-path operations
- Deep merge support for nested objects
- Import resolver with alias support, semver constraints (^, ~, >=, <)
- Import cycle detection and collision errors

**Epic F — Enterprise Governance**
- Artifact bundle format: compiled registry + provenance + SBOM + attestations
- Signing and verification ports (pluggable algorithm)
- Activation protocol: upload → verify → attest → swap → audit → invalidate
- Kill switch, read-only, and policy-off modes
- Per-tenant quota enforcement: parse/compile/eval/node/def limits

**Epic G — Security Hardening**
- Redaction engine: denyKeys masking across all data structures
- Default deny keys: password, token, apiKey, ssn, etc.
- Pattern-based key matching with glob support
- Case-insensitive key matching
- Safe regex budget enforcement in expression engine

**Epic H — Conformance Suite & CI**
- Fixture packs: 10 categories with ≥2 fixtures each
- Conformance runner with category filtering and CLI entry point
- GitHub Actions CI: multi-Python matrix, conformance gate, release gate

**Epic I — Packaging & Developer Experience**
- py.typed markers for all packages
- Getting-started example in under 50 lines
- Changelog and migration guide
