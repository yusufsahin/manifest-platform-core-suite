# Implementation Checklist Pack (Cursor-ready)

## 1) Must-Implement First
- core-contracts schemas (Event/Decision/Error/Intent/Trace)
- core-canonical (canonical JSON + stable hash)
- core-errors registry enforcement
- core-conformance runner behavior + minimal fixtures

## 2) Next
- core-meta (meta-metadata + diff)
- core-parser (DSL/YAML/JSON normalize)
- core-validator (structural + semantic)
- core-overlay (merge semantics)
- core-expr (IR + typecheck + eval + budgets)

## 3) Engines
- core-fsm + core-workflow
- core-policy
- core-acl
- core-decision-compose

## 4) Enterprise
- artifact bundle format (compiled/provenance/attest/sbom/signature)
- signing/verification ports
- activation protocol + audit + rollback + canary
- quotas + kill switch
- redaction everywhere

## 5) Release Gates
- conformance suite 100% pass
- compatibility matrix
- semver bump rules for breaking changes
