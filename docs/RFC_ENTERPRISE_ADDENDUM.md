# RFC — Enterprise Addendum v1.0 (Normative)

## 1) Lifecycle
Draft → Review → Approved → Published → Active → Deprecated → Retired

**Enforcement (repo):**
- Conformance fixtures: `packages/core-conformance/fixtures/governance/*`
- Pytest: `tests/test_governance.py`
- Release gate (local): `tools/run-release-gate.ps1`

## 2) Immutable Compiled Artifacts
An artifact bundle MUST include:
- compiled_manifest.json
- provenance.json (astHash, metaHash, plugin list + versions, engine versions)
- attestations.json (conformance passed, security preset applied)
- signature (enterprise mode MUST)
- sbom.json (SHOULD)

**Enforcement (repo):**
- Conformance fixtures: `packages/core-conformance/fixtures/governance/*`
- Pytest: `tests/test_governance.py` (bundleHash determinism, provenance shape, sbom ordering)

## 3) Activation Protocol (Transactional)
1. Upload artifact
2. Verify signature
3. Verify attestations and policy
4. Swap active pointer atomically
5. Append audit record (WORM optional)
6. Invalidate caches by artifactHash

Activation MUST be idempotent via an idempotency key.

**Enforcement (repo):**
- Pytest: `tests/test_governance.py` (atomic swap rollback, idempotency, modes)
- Runtime surface: `tooling/mpc_runtime/app.py` (activation endpoints)
- CLI surface: `src/mpc/tooling/cli.py` (activation commands; runtime-compatible contract)

## 4) Quotas & Budgets
Tenant quotas MUST exist (counts and evaluation budgets).
Exceed MUST raise E_QUOTA_* errors.

**Enforcement (repo):**
- Conformance fixtures: `packages/core-conformance/fixtures/expr/*` + `packages/core-conformance/fixtures/governance/*`
- Pytest: `tests/test_governance.py` / budget tests as applicable

## 5) Rollout/Rollback
Canary activation SHOULD exist.
Instant rollback to previous artifactHash SHOULD exist.
Kill switch SHOULD exist (policy-off/read-only modes).

**Enforcement (repo):**
- Pytest: `tests/test_governance.py` (promote/rollback/modes)

## 6) Audit & Forensics
Decisions MUST include artifactHash and traceSpanId.
Audit records MUST include hashes + actor + timestamp.

**Enforcement (repo):**
- Pytest/E2E: workflow audit tests (see `tests/test_persistence_redis.py`, Studio E2E where applicable)
- Contracts: `docs/CONTRACT_MATRIX.md`
