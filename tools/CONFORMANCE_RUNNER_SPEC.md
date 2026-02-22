# Conformance Runner Spec (Normative)

## Python Reference Runner

```bash
pip install mpc-conformance
mpc-conformance run packages/core-conformance/fixtures/
mpc-conformance run packages/core-conformance/fixtures/expr/   # single category
```

Exit code 0 = all pass. Non-zero = at least one failure.

---

## Runner Behaviour

The runner MUST:

- Load `meta.json` for each fixture and:
  - Fix the clock to `meta.clock` (no system time).
  - Load the preset named in `meta.preset`.
  - If `meta.limits` is present, override the preset limits with those values.
- Determine the target operation from the fixture category:
  - `contracts/*` — validate `input.json` against the matching JSON Schema
  - `canonical/*` — apply definition ordering + canonicalize; compare output
  - `overlay/*` — run merge engine with ops from `input.json`
  - `expr/*` — typecheck + evaluate; apply limits from preset (+ meta override)
  - `workflow/*` — validate FSM definition; attempt transition if `current` + `event` present
  - `policy/*` — evaluate policy set against event
  - `acl/*` — evaluate RBAC/ABAC rules; produce masking intents if applicable
  - `compose/*` — run decision composition with strategy from `input.json`
  - `security/*` — apply redaction policy to trace/error output
  - `governance/*` — verify signing / attestation / activation preconditions
- Canonicalize the produced output (lexicographic key sort, no whitespace).
- Compare canonicalized output byte-for-byte with `expected.json`.
- Emit a structured diff report on mismatch:
  - changed paths
  - expected vs actual excerpts
  - trace snippet if present in output

---

## Failure Conditions

The runner MUST fail if ANY of the following are true:

- An `E_*` error code in any output is not listed in `ERROR_CODE_REGISTRY.md`.
- An `R_*` reason code in any output is not listed in `ERROR_CODE_REGISTRY.md` (Reason Codes section).
- An Intent `kind` in any output is not listed in `INTENT_TAXONOMY.md`.
- Output is not canonicalizable (invalid JSON, circular ref, non-finite number).
- Canonicalized output does not byte-match `expected.json`.
- A fixture `meta.json` references a preset that does not exist in `packages/presets/`.

---

## Special Output Formats

Some fixture categories produce outputs that are not governed by the core JSON
Schemas but are still byte-compared by the runner:

| Category | Expected output shape | Notes |
| --- | --- | --- |
| `contracts/*` | `{ "valid": true }` | Runner schema-validates `input.json`; outputs `valid: true` on pass, or an `Error` object on fail. |
| `canonical/*` | The canonicalized object itself | Runner reorders keys + lists per HASH_CANONICAL_SPEC.md rules and outputs the result. |
| `overlay/*` | The merged/patched object | Runner applies ops to `base` using `overlays` from `input.json` and outputs the result object. |

The `notes` field in `meta.json` is informational only. The runner MUST ignore it.

---

## meta.json Schema

```json
{
  "clock":  "<ISO-8601 timestamp — runner fixes clock to this value>",
  "preset": "<preset name from packages/presets/>",
  "limits": {
    "maxManifestNodes": 500,
    "maxExprSteps":     1,
    "maxExprDepth":     1,
    "maxEvalTimeMs":    5,
    "maxRegexOps":      10
  }
}
```

`limits` is optional. When present, individual keys override the preset defaults.
This allows fixtures to test budget enforcement without creating a new preset.

---

## Diff Report Format

```text
FAIL  expr/02_budget_steps_exceeded
  path:     error.code
  expected: "E_BUDGET_EXCEEDED"
  actual:   "E_EXPR_LIMIT_STEPS"

  path:     error.message
  expected: "Expression evaluation exceeded step budget (limit: 1)"
  actual:   (missing)
```
