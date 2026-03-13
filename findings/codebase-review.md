# Manifest Platform Core Suite (MPC) — Codebase Review

**Date:** 2026-03-13
**Reviewer:** Claude (AI-assisted review)
**Scope:** Full codebase — src/mpc, tests, packages, tooling/mpc-studio, docs

---

## Overview

This is a well-structured Python library suite for manifest-driven platforms, organized across ~9 modules (`kernel`, `features`, `tooling`, `enterprise`) plus a React/Pyodide web IDE (`mpc-studio`). The architecture is clean, deterministic by design, and well-specced. The backlog/release-readiness docs are unusually self-aware. Below are findings grouped by severity.

---

## Bugs / Definite Defects

### 1. `bundle.py:122` — `verify_integrity()` is always `True` (tautology bug)

```python
def verify_integrity(self) -> bool:
    return self.bundle_hash == self.bundle_hash  # compares property to itself
```

Both sides call the same computed property. This always returns `True` regardless of actual bundle state. The method should compare against a stored/serialized hash, not recompute both sides from the same source.

**File:** `src/mpc/enterprise/governance/bundle.py:122`

---

### 2. `semantic.py:258` — `source` is forced to `None` in `_check_import_cycles`

```python
source=node_map.get(("", dep), node_map.get((ast.namespace, dep)))
    and None,  # <- this makes the whole expression always None
```

The `and None` short-circuits the entire expression to `None`. Source location info is silently dropped on all import cycle errors.

**File:** `src/mpc/tooling/validator/semantic.py:258`

---

### 3. `registry.py` — `R_WF_QUEUED` and `R_WF_IGNORED` not in `REASON_CODES`

`fsm.py` emits these two reason codes (lines 345, 373):
```python
Reason(code="R_WF_QUEUED", ...)
Reason(code="R_WF_IGNORED", ...)
```

Neither is registered in `REASON_CODES` in `registry.py`. The conformance runner's `_walk()` check would flag these as unknown reason codes.

**Files:** `src/mpc/features/workflow/fsm.py:345,373` / `src/mpc/kernel/errors/registry.py:56-72`

---

### 4. `worker.ts:122` — Code injection via DSL template interpolation

```ts
json.dumps(run_pipeline("""${dsl.replace(/"""/g, '\\"\\"\\"') }"""))
```

The DSL string is directly interpolated into Python code being `runPythonAsync()`'d. Escaping only triple-quotes is insufficient — a crafted DSL with newlines and valid Python syntax can inject arbitrary code. The DSL should be passed as a variable via `pyodide.globals.set()`, not string interpolation.

**File:** `tooling/mpc-studio/src/engine/worker.ts:122`

---

### 5. `worker.ts:102` — Unregistered error code `E_PARSE`

```python
{"code": "E_PARSE", "message": str(e), "severity": "error"}
```

`E_PARSE` is not in `ERROR_CODES`. Registered alternatives: `E_PARSE_SYNTAX`, `E_PARSE_INVALID_TOKEN`, `E_PARSE_UNSUPPORTED_FORMAT`.

**File:** `tooling/mpc-studio/src/engine/worker.ts:120`

---

### 6. `worker.ts` — `validate_semantic` called with wrong arity

```python
sem_errors = validate_semantic(ast, meta)  # passes 2 args
```

The actual signature (`semantic.py:16`) is `def validate_semantic(ast: ManifestAST)` — one argument only. This raises `TypeError` at runtime in the browser.

**Files:** `tooling/mpc-studio/src/engine/worker.ts:108` / `src/mpc/tooling/validator/semantic.py:16`

---

### 7. `dsl_frontend.py:172-175` — Duplicate key in `_ESCAPE_MAP`

```python
_ESCAPE_MAP: dict[str, str] = {
    ...
    "\\/": "/",   # line 172
    "\\b": "\b",
    "\\/": "/",   # line 174 — silent duplicate, second silently wins
    "\\f": "\f",
}
```

Functionally harmless (same value), but is dead code and confusing.

**File:** `src/mpc/kernel/parser/dsl_frontend.py:172-175`

---

### 8. `acl/engine.py:103` — Wrong reason code on default-deny fallback

```python
reasons.append(Reason(
    code="R_ACL_DENY_ROLE",   # role-specific code used even when no role matched
    summary=f"No matching ACL rule for action='{action}', resource='{resource}'",
))
```

`R_ACL_DENY_ROLE` implies a role-based deny. The fallback path fires when *no* rule matched at all. A distinct code (e.g., `R_ACL_DENY_NO_MATCH`) would be more accurate and auditable.

**File:** `src/mpc/features/acl/engine.py:103-107`

---

## Logic / Design Issues

### 9. `fsm.py:480-482` — `fire_async` is not actually async

```python
async def fire_async(self, event: str, **kwargs) -> FireResult:
    return self.fire(event, **kwargs)
```

This is a synchronous method wrapped in `async def`. It blocks the event loop during transition execution. Should use `asyncio.to_thread()`.

**File:** `src/mpc/features/workflow/fsm.py:480-482`

---

### 10. `mpc-engine.ts:25` — Collision-prone request IDs

```ts
const id = Math.random().toString(36).substring(7);
```

`substring(7)` leaves only ~4 characters of entropy. Use `crypto.randomUUID()` instead.

**File:** `tooling/mpc-studio/src/engine/mpc-engine.ts:25`

---

### 11. `App.tsx:33-45` — No debounce on live validation

```ts
useEffect(() => {
    validate();
}, [dsl]);  // fires on every keystroke
```

Pyodide validation is expensive (Python + WASM). Every keystroke fires a full parse+validate cycle. Needs a debounce (e.g., 300-500ms).

**File:** `tooling/mpc-studio/src/App.tsx:33-45`

---

### 12. `App.tsx:178` vs `worker.ts:9` — Pyodide version mismatch

| Location | Version |
|---|---|
| Footer display (`App.tsx:178`) | `Pyodide 0.25.0` |
| `worker.ts` CDN URL | `v0.25.0` |
| `package.json` npm dependency | `pyodide@0.29.3` |

The npm package (`0.29.3`) and CDN (`v0.25.0`) are two different versions with different API surfaces.

**Files:** `tooling/mpc-studio/src/App.tsx:178` / `tooling/mpc-studio/src/engine/worker.ts:9` / `tooling/mpc-studio/package.json`

---

### 13. `worker.ts:32-51` — Incomplete MPC file list — missing critical modules

The hardcoded file list in `loadMPCLibrary` omits modules that the pipeline actually imports at runtime:

| Missing File | Required By |
|---|---|
| `kernel/errors/__init__.py` | All modules |
| `kernel/errors/exceptions.py` | Engines, parsers |
| `kernel/errors/registry.py` | Conformance runner |
| `kernel/canonical/__init__.py` | Compiler, bundle |
| `kernel/canonical/serializer.py` | Hashing |
| `kernel/canonical/hash.py` | Registry, bundle |
| `kernel/ast/normalizer.py` | Parser |
| `kernel/contracts/serialization.py` | Contracts |
| `kernel/meta/diff.py` | Meta module |
| `kernel/parser/grammar.lark` | DSL parser (LALR) |
| `kernel/parser/json_frontend.py` | Parser base |
| `kernel/parser/yaml_frontend.py` | Parser base |

All errors are silently swallowed in the catch block, making failures invisible.

**File:** `tooling/mpc-studio/src/engine/worker.ts:32-51`

---

### 14. `semantic.py:213-218` — Overcomplicated source lookup expression

```python
source=node_map.get(start_key, node_map.get(start_key))
    and node_map[start_key].source
    if start_key in node_map
    else None,
```

`node_map.get(start_key, node_map.get(start_key))` is equivalent to `node_map.get(start_key)`. Simplify to:
```python
source=node_map[start_key].source if start_key in node_map else None,
```

**File:** `src/mpc/tooling/validator/semantic.py:213-218`

---

### 15. `fsm.py` — Inline compound statements throughout

Multiple PEP 8-violating single-line compound statements:

```python
if isinstance(p_data, list): is_p = (s in p_data)
elif isinstance(p_data, dict): is_p = p_data.get(s, False)
```

Also `fire()` and `_process_fire()` parameter lists exceed 120 characters on one line.

**File:** `src/mpc/features/workflow/fsm.py` (multiple locations)

---

## Conformance / Testing Gaps

Already tracked in `RELEASE_READINESS.md` but confirmed during review:

| Gap | Category |
|---|---|
| Parser equivalence fixture (DSL/YAML/JSON → same AST) | Epic B |
| Validator fixture category | Epic B |
| Policy allow-all positive path fixture | Epic D |
| ACL ABAC fixture | Epic D |
| Intent dedup fixture | Epic D |
| Overlay: append / remove / patch fixtures (3 ops untested) | Epic E |
| Enterprise: attestation / quota / rollback fixtures | Epic F |
| Expr: time-limit + regex-limit fixtures | Epic C |
| `Intent.kind` not enum-constrained in JSON Schema | Epic A |
| `timestamp` missing `format: date-time` in JSON Schema | Epic A |

**Current overall release-readiness: 43/70 (61%)** per `docs/RELEASE_READINESS.md`.

---

## Minor / Code Quality

| Location | Issue |
|---|---|
| `src/mpc/enterprise/governance/bundle.py:50` | `ArtifactBundle` is `@dataclass` (mutable) but docs say "immutable artifact" — should be `frozen=True` |
| `src/mpc/features/workflow/fsm.py:392` | Bare `except:` in guard evaluation silently swallows all exceptions |
| `src/mpc/features/workflow/fsm.py:119` | `AuditRecord.timestamp` uses `time.time()` (wall clock) — breaks determinism guarantee |
| `src/mpc/enterprise/governance/quotas.py` | `QuotaEnforcer` mutable counter fields are not thread-safe |
| `README.md` | Written in Turkish; `pip install mpc-core` in quick-start doesn't match actual package name `mpc` in `pyproject.toml` |

---

## Priority Matrix

### Fix Now (correctness / security)

| # | Finding | File |
|---|---|---|
| 1 | `verify_integrity()` tautology | `bundle.py:122` |
| 2 | `validate_semantic` wrong arity (runtime crash) | `worker.ts:108` |
| 3 | DSL code injection via template interpolation | `worker.ts:122` |
| 4 | Missing `R_WF_QUEUED`, `R_WF_IGNORED` in REASON_CODES | `registry.py` |
| 5 | Pyodide version mismatch + incomplete file list | `worker.ts:9,32` |

### Fix Soon (logic / design)

| # | Finding | File |
|---|---|---|
| 6 | `fire_async` is not truly async | `fsm.py:480` |
| 7 | Collision-prone request IDs | `mpc-engine.ts:25` |
| 8 | `source` always `None` in import cycle errors | `semantic.py:258` |
| 9 | Wrong reason code on default ACL deny | `acl/engine.py:103` |
| 10 | Missing debounce on live validation | `App.tsx:33` |

### Cleanup (polish / conformance)

| # | Finding | File |
|---|---|---|
| 11 | Duplicate `_ESCAPE_MAP` key | `dsl_frontend.py:174` |
| 12 | `ArtifactBundle` should be `frozen=True` | `bundle.py:50` |
| 13 | PEP 8 inline compound statements | `fsm.py` throughout |
| 14 | README language + package name mismatch | `README.md` |
| 15 | Add missing conformance fixtures (10 gaps) | `packages/core-conformance/` |
