# Worker Contract v1 vs v2

## Purpose

This document freezes the compatibility contract between `src/engine/mpc-engine.ts` and `src/engine/worker.ts` for the metadata-driven transition.

## v1 Legacy Contract (Workflow-Centric)

- **Request types**: `LIST_WORKFLOWS`, `MERMAID_EXPORT`, `WORKFLOW_STEP`, `WORKFLOW_RUN`, `EVALUATE_POLICY`, `SIMULATE_ACL`.
- **Response shape**: raw payload (`RESULT`) or plain error string (`ERROR`).
- **Scope**: workflow and policy/acl operations, but without a generic definition envelope.
- **Weakness**:
  - no explicit request metadata (`requestId`, `durationMs`, `timestamp`);
  - no versioned worker envelope for contract evolution;
  - no first-class unknown-kind fallback diagnostic.

## v2 Metadata-Driven Contract

- **Request types**:
  - `LIST_DEFINITIONS`
  - `PREVIEW_DEFINITION`
  - `SIMULATE_DEFINITION`
- **Response shape**: versioned envelope
  - `contractVersion`
  - `requestId`
  - `timestamp`
  - `type`
  - `payload`
  - `diagnostics`
  - `durationMs`
  - `errorCode` (optional)
- **Descriptor contract**:
  - `{ id, name, kind, version, capabilities[], diagnostics[] }`
- **Fallback behavior**:
  - unknown/new kinds must return `inspector` capability and `UNKNOWN_KIND_FALLBACK` warning diagnostic.

## Compatibility Rules

- Existing v1 requests remain supported and continue to power legacy panels and simulator flows.
- `mpc-engine` unwraps v2 envelopes when present and still accepts plain payloads for v1 handlers.
- Feature flag `VITE_METADATA_DRIVEN_ROUTER=false` keeps UI routing behavior compatible with legacy panel mapping.

## Deprecation Path

1. Keep v1 request handlers until one minor release after v2 rollout.
2. Monitor:
   - unknown-kind fallback ratio
   - v2 request error codes
   - p50/p95 parse/preview/simulate timings
3. Remove v1-only routing after compatibility window and release migration notes.
