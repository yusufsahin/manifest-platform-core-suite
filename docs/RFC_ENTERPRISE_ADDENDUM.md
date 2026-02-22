# RFC — Enterprise Addendum v1.0 (Normative)

## 1) Lifecycle
Draft → Review → Approved → Published → Active → Deprecated → Retired

## 2) Immutable Compiled Artifacts
An artifact bundle MUST include:
- compiled_manifest.json
- provenance.json (astHash, metaHash, plugin list + versions, engine versions)
- attestations.json (conformance passed, security preset applied)
- signature (enterprise mode MUST)
- sbom.json (SHOULD)

## 3) Activation Protocol (Transactional)
1. Upload artifact
2. Verify signature
3. Verify attestations and policy
4. Swap active pointer atomically
5. Append audit record (WORM optional)
6. Invalidate caches by artifactHash

Activation MUST be idempotent via an idempotency key.

## 4) Quotas & Budgets
Tenant quotas MUST exist (counts and evaluation budgets).
Exceed MUST raise E_QUOTA_* errors.

## 5) Rollout/Rollback
Canary activation SHOULD exist.
Instant rollback to previous artifactHash SHOULD exist.
Kill switch SHOULD exist (policy-off/read-only modes).

## 6) Audit & Forensics
Decisions MUST include artifactHash and traceSpanId.
Audit records MUST include hashes + actor + timestamp.
