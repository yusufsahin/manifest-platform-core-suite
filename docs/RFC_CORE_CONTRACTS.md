# RFC — Core Contracts v1.0 (Normative)

This RFC defines the canonical cross-engine contracts:
- EventEnvelope
- Decision
- Error
- Intent
- Trace

Implementations MUST:
- conform to JSON Schemas in packages/core-contracts/schemas/
- produce deterministic ordering and stable hashes via core-canonical rules
- apply redaction policies to Trace/Error/log outputs

See: HASH_CANONICAL_SPEC.md and ERROR_CODE_REGISTRY.md
