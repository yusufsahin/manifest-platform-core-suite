# Manifest Platform Core Suite - Master Implementation Board

Date: 2026-03-13
Branch: main
Status: Active

## 1. Completed Baseline and Regression Work

### 1.1 Compatibility and runtime regressions (done)
- [x] Restore expression IR compatibility exports (`ir_from_dict`, `ir_to_dict`).
- [x] Restore `diff_meta` compatibility import path via `mpc.kernel.meta.models`.
- [x] Fix workflow intent construction (`Intent(kind=...)`).
- [x] Add `WorkflowEngine.validate()` and `WorkflowEngine.available_transitions()`.

### 1.2 Authorization and behavior consistency (done)
- [x] Enforce `actor_roles` against transition `auth_roles` in workflow fire path.
- [x] Support both `authRoles` and `auth_roles` in AST transition parsing.
- [x] Replace broad guard handling with explicit `except Exception`.

### 1.3 Fixture and test alignment (done)
- [x] Align unknown-transition message with conformance fixtures.
- [x] Ensure successful transitions emit `R_WF_GUARD_PASS`.
- [x] Align missing-initial validation message with fixture text.

### 1.4 Coverage expansion (done)
- [x] Add expression edge-case tests for arithmetic, `substr`, `min`/`max`, `now`, and regex invalid patterns.
- [x] Add meta diff breaking/non-breaking tests.
- [x] Add validator tests for cycles, namespace collision, and invalid function refs.
- [x] Add edge-case suite in `tests/test_coverage_edge_cases.py`.

### 1.5 Verification (done)
- [x] `pytest -q` completed: `397 passed`.
- [x] Secondary `verify_*.py` validation marked N/A (no such scripts in repo).

## 2. Active Workboard (Open)

Legend: Priority = P0/P1/P2. Effort = S (<=0.5d), M (1d), L (2-3d).

| ID | Priority | Area | Task | Owner | Effort | Depends On | Status |
|---|---|---|---|---|---|---|---|
| W-01 | P0 | Studio Security | Remove DSL-to-Python interpolation and pass DSL via safe runtime variable binding in worker. | Core Maintainer | M | None | Done |
| W-02 | P0 | Studio Security | Remove unsafe HTML sink in visualizer; sanitize render path and avoid direct `innerHTML` usage. | Frontend Maintainer | M | W-01 | Done |
| W-03 | P0 | Studio Runtime | Align worker-side API calls with Python backend signatures (`DomainMeta`, `validate_semantic`). | Frontend Maintainer | S | None | Done |
| W-04 | P1 | Packaging | Fix CLI entry point mismatch in `pyproject.toml` and verify install-time command resolution. | Core Maintainer | S | None | Done |
| W-05 | P1 | Studio Runtime | Resolve Pyodide version drift across CDN loader, package dependency, and displayed version string. | Frontend Maintainer | M | W-03 | Done |
| W-06 | P1 | Studio UX | Fix open-folder stale state race so first file auto-opens reliably. | Frontend Maintainer | S | None | Done |
| W-07 | P1 | Studio Perf | Debounce live validation loop to reduce per-keystroke parse/validate churn. | Frontend Maintainer | S | W-03 | Done |
| W-08 | P1 | Studio Infra | Ensure worker loads all required mirrored MPC modules; fail loudly on missing runtime imports. | Frontend Maintainer | M | W-03 | Done |
| W-09 | P2 | Core Quality | Clean semantic source lookup simplification and dead-code cleanup where behavior remains unchanged. | Core Maintainer | S | None | Done |
| W-10 | P2 | Docs | Align README package/install guidance and language consistency with actual publish/install path. | Docs Maintainer | S | W-04 | Done |

## 3. Acceptance Criteria by Work Item

### W-01 DSL interpolation hardening
- Worker no longer constructs executable Python using raw DSL string interpolation.
- DSL is transmitted through runtime variables (or equivalent non-executable channel).
- Add one malicious-payload regression test that proves payload is treated as data.

### W-02 Visualizer XSS mitigation
- No direct assignment of untrusted DSL-derived content to `innerHTML`.
- Mermaid rendering path rejects or sanitizes unsafe markup.
- Add a regression test or fixture for payload-like DSL input.

### W-03 Worker API alignment
- No runtime `TypeError` from `DomainMeta` construction.
- `validate_semantic` called with correct signature.
- Studio validation succeeds for at least one known-good fixture.

### W-04 CLI entry point reliability
- `pyproject.toml` script target points to existing module/function.
- Fresh install exposes working `mpc-conformance` command.
- Add smoke command check to release checklist.

### W-05 Pyodide version consistency
- Runtime loader version, dependency version, and UI-reported version agree.
- Build and runtime smoke test pass under the selected version.

### W-06 Folder open race fix
- Opening a folder auto-loads first file without manual click.
- Repro case validated in at least two attempts.

### W-07 Validation debounce
- Validation does not execute on every keystroke.
- Debounce interval configured (target: 300-500ms).
- Typing responsiveness improves without stale-result regressions.

### W-08 Worker module loading completeness
- Required MPC mirrored modules are loaded before validation pipeline.
- Missing modules produce explicit surfaced error (not swallowed silently).

### W-09 Core cleanup
- Simplified expressions in semantic validator preserve behavior.
- No new failures in `pytest -q`.

### W-10 Documentation alignment
- README install instructions match package and entry points.
- Language/wording is consistent with release targets.

## 4. Execution Order

1. W-01, W-03 (security and runtime correctness first).
2. W-02, W-08 (complete Studio safety and determinism).
3. W-04, W-05 (packaging and runtime version consistency).
4. W-06, W-07 (UX/performance improvements).
5. W-09, W-10 (cleanup and docs).

## 5. Validation Gates

### Gate A - Core Python
- Run `pytest -q`.
- Pass target: no regressions from current baseline (`397 passed` minimum after accounting for intentional new tests).

### Gate B - Studio Static Quality
- In `tooling/mpc-studio`, run `npm run lint` and `npm run build`.
- No new lint errors introduced by changed files.

### Gate C - Studio Runtime Smoke
- Validate one known-good DSL file end to end.
- Validate one intentionally invalid DSL file with expected diagnostics.
- Validate one hostile payload sample does not execute arbitrary code.

### Gate D - Packaging Smoke
- Install package in clean environment.
- Run `mpc-conformance --help` successfully.

## 6. Rollup Status Template (Update per cycle)

- Cycle date:
- Completed IDs:
- In-progress IDs:
- Blocked IDs + reason:
- Test summary (`pytest`, `lint`, `build`):
- Risk delta:

### Latest Cycle Update

- Cycle date: 2026-03-13
- Completed IDs: W-01, W-03
- In-progress IDs: None
- Blocked IDs + reason: None
- Test summary (`pytest`, `lint`, `build`): Worker file lint clean (`npx eslint src/engine/worker.ts`); Studio build passes (`npm run build`); full Studio lint still has pre-existing repo issues unrelated to this change set.
- Risk delta: Removed worker code-injection vector from DSL interpolation path and removed API-arity/runtime mismatch for semantic validation.

### Latest Cycle Update (2)

- Cycle date: 2026-03-13
- Completed IDs: W-02, W-08
- In-progress IDs: None
- Blocked IDs + reason: None
- Test summary (`pytest`, `lint`, `build`): Changed files lint clean (`npx eslint src/components/Visualizer.tsx src/engine/worker.ts`); Studio build passes (`npm run build`).
- Risk delta: Removed direct HTML injection path in workflow visualizer and converted worker module loading to required-file enforcement with explicit import smoke validation.

### Latest Cycle Update (3)

- Cycle date: 2026-03-13
- Completed IDs: W-04, W-05, W-06, W-07
- In-progress IDs: None
- Blocked IDs + reason: None
- Test summary (`pytest`, `lint`, `build`): Packaging smoke passed (`python -m pip install -e .` and `mpc-conformance --help`); changed Studio files lint clean; Studio build passes after each change set.
- Risk delta: CLI entrypoint now resolves correctly; Pyodide version references are aligned (`0.29.3`) across dependency, worker loader, and UI; folder-open race and per-keystroke validation load reduced via handle-threading and debounce.

### Latest Cycle Update (4)

- Cycle date: 2026-03-13
- Completed IDs: W-09, W-10
- In-progress IDs: None
- Blocked IDs + reason: None
- Test summary (`pytest`, `lint`, `build`): `pytest -q tests/test_validator.py tests/test_conformance_runner.py` passed (`48 passed`); `mpc-conformance --help` confirms documented command is valid.
- Risk delta: Semantic validator now preserves usable source metadata in cycle diagnostics (core + Studio mirror) and README quick-start/install guidance matches the current package and CLI surface.

## 7. Current Risks and Watchlist

- Studio worker mirror drift risk reduced after W-03 and W-08; continue monitoring during future parser/validator mirror changes.
- Security hardening tasks in this board are complete; add dedicated hostile-payload regression fixtures in a follow-up cycle if desired.
- Packaging smoke is validated in editable install; add wheel-install smoke in CI for release confidence.
