# MASTER SPEC — Manifest Platform Core Suite (MPC) v1.0

## 0. Scope

MPC is a Python library suite for building manifest-driven platforms.
Consuming applications embed MPC libraries; end users interact with the consuming application.

```text
End User  →  Consuming App  →  MPC Libraries  →  Decision + Intent + Trace
              (your code)       (this suite)
```

- Inputs: DSL/YAML/JSON manifests authored by end users
- Compile output: Canonical AST → deterministic compile → immutable signed artifacts
- Runtime: engines evaluate EventEnvelope, produce Decision/Intent/Trace

**Non-goals:** Turing-complete scripting; in-engine side effects; storage; UI; transport.

## 1. Normative Keywords
MUST / MUST NOT / SHOULD / MAY are used in RFC sense.

## 2. Core Principles
1) Canonical AST is the single source of truth.  
2) Deterministic by default (clock/random injected).  
3) Engines are side-effect free; only produce Decision + Intent.  
4) Runtime loads only immutable compiled artifacts (enterprise: signed+attested).  
5) Conformance fixtures define behavior (tests are the constitution).

## 3. Package Structure

### Kernel (`mpc.kernel`)
- `mpc.kernel.contracts`: Event/Decision/Error/Intent/Trace schemas.
- `mpc.kernel.canonical`: Canonical JSON + stable hash rules.
- `mpc.kernel.ast`: Canonical AST model.
- `mpc.kernel.parser`: DSL/YAML/JSON → AST.
- `mpc.kernel.errors`: Error code registry.
- `mpc.kernel.meta`: Domain metadata and kind definitions.

### Features (`mpc.features`)
- `mpc.features.workflow`: Native pure FSM + Port binding.
- `mpc.features.expr`: Typed expression engine with time/step budgets.
- `mpc.features.policy`: Event-based rule evaluation (deny-wins).
- `mpc.features.acl`: RBAC / ABAC and field masking.
- `mpc.features.overlay`: Manifest merge and variant operations.
- `mpc.features.redaction`: PII and data privacy controls.

### Tooling (`mpc.tooling`)
- `mpc.tooling.validator`: Structural and semantic validation.
- `mpc.tooling.registry`: Hashed, immutable artifact compilation.
- `mpc.tooling.uischema`: Auto-generated UI schemas from manifests.
- `mpc.tooling.conformance`: Behavior-defining test fixtures.

### Enterprise (`mpc.enterprise`)
- `mpc.enterprise.governance`: Signing, attestation, and lifecycle management.

## 4. Contracts (MUST)
Implementations MUST comply with JSON Schemas:
- EventEnvelope
- Decision (+Reason/Message)
- Error (+SourceMap)
- Intent (taxonomy v1)
- Trace (+TraceEvent)

Decision (enterprise mode) MUST include in meta:
- artifactHash, engine, engineVersion

## 5. Canonicalization & Hashing (MUST)
- Canonical JSON: lexicographic object keys, deterministic list ordering.
- Stable hash computed on canonical JSON bytes (default SHA-256).
- Definition ordering rule (if applicable): priority desc, then name asc, then id asc.

## 6. Canonical AST (MUST)
AST root MUST include:
- schemaVersion (int), namespace (string), name (string), manifestVersion (string), defs[]

Each node MUST include:
- kind, id
name SHOULD exist where meaningful.
SourceMap SHOULD be propagated in errors.

## 7. Meta-Metadata (MUST)
Meta schema MUST define:
- allowed kinds and required properties
- allowed types, events, functions (signature + cost)
Meta diff MUST detect breaking vs non-breaking changes.

## 8. Parsing & Normalization (MUST)
- DSL/YAML/JSON MUST normalize into the same canonical AST given same semantics.
- Parser errors MUST produce E_PARSE_* with SourceMap.

## 9. Validation (MUST)
Validator MUST enforce:
- structural rules via meta schema
- semantic rules: duplicates, unresolved refs, cycle detection (extends/import/workflow), invalid workflow defs
Errors MUST be structured Error objects with codes in registry.

## 10. Registry Compile (MUST)
Registry build MUST be deterministic and cacheable by:
- astHash + metaHash + engineVersion

Registry SHOULD provide:
- resolved types, dependency graph, ref resolver

## 11. Expression Engine (MUST)
- No host-language eval.
- Typed IR + typecheck.
- Budgets MUST be enforced: steps, depth, timeMs, regexOps.
Exceed MUST return E_BUDGET_EXCEEDED.

## 12. Workflow (MUST)
- `mpc.features.workflow`: Pure FSM and port-bound engine.
- Guards via `GuardPort`; auth via `AuthPort`.

## 13. Policy (MUST)
- Event matcher + expr + decision template.
- Ordering deterministic (priority/name/id).
- Default conflict strategy: deny-wins.

## 14. ACL (MUST)
- RBAC minimum.
- Optional ABAC via expr adapter.
- Field masking must be representable as Intent(maskField).

## 15. Overlay (MUST)
Merge ops MUST: replace|merge|append|remove|patch.
Conflicts MUST hard error unless explicitly resolved.
Selectors MUST be stable: prefer (kind, namespace, id).

## 16. Decision Composition (MUST)
Default: deny-wins.
Intent dedupe deterministic: (kind, target, idempotencyKey?).

## 17. Enterprise Addendum (MUST in enterprise mode)
- Lifecycle: Draft → Review → Approved → Published → Active → Deprecated → Retired
- Immutable artifact bundle includes provenance + attestations + signature.
- Activation protocol: upload → verify → attest → atomic pointer swap → audit append → cache invalidate.
- Quotas/budgets enforced tenant-wide.
- Rollout/rollback (canary + kill switch) SHOULD exist.

## 18. Conformance (MUST)
Conformance pack MUST include categories:
contracts, canonical, overlay, expr, workflow, policy, acl, compose, security, governance.
Runner MUST fix clock, canonicalize output, byte-compare expected.

## 19. Consuming App Contract

A consuming application integrating MPC MUST:

- Supply a DomainMeta defining allowed kinds, types, and functions.
- Choose or define a Preset (limits + feature flags + policy strategy).
- Implement GuardPort if workflow transition guards are needed.
- Implement AuthPort if actor authorization is delegated to an external system.
- Implement Intent adapters for each Intent kind it produces (see INTENT_TAXONOMY.md).
- Store and version compiled artifacts; never mutate an artifact in place.
- Pass the active artifact to engine.evaluate() at runtime; MPC does not manage storage.

A consuming application MUST NOT:

- Inject host-language eval into the expression engine.
- Bypass the canonical compile step (e.g. hand-craft artifacts).
- Suppress or swallow structured Errors — surface them with code + message to callers.

MPC MUST NOT:

- Perform I/O, storage, or network calls inside any engine.
- Retain mutable state between evaluate() calls.
- Produce non-deterministic output given the same inputs and fixed clock.
