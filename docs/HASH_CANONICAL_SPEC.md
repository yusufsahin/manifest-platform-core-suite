# HASH + CANONICAL JSON SPEC v1.0 (Normative)

## Canonical JSON
- Objects: keys sorted lexicographically (unicode codepoint order).
- Arrays: order MUST be deterministic. Where a model defines an ordering rule, it MUST be applied.
- No insignificant whitespace; UTF-8 bytes.

## Stable Hash
- stable_hash(x) = SHA-256(canonical_json_bytes(x)) by default.
- The algorithm MAY be configured but MUST be recorded in provenance.

## Deterministic Ordering Rule for Definitions
For lists of definition-like items:
1) priority desc (if present)
2) name asc (if present)
3) id asc

## Idempotence
canonicalize(canonicalize(x)) MUST equal canonicalize(x).
