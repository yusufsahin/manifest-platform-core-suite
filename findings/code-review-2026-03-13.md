# Code Review Findings (2026-03-13)

## High

1. Expression IR public API regression breaks imports
- Evidence: tests import `ir_from_dict` / `ir_to_dict` from `mpc.features.expr.ir`.
- File refs:
  - tests/test_expr.py:10
  - tests/test_expr.py:12
  - src/mpc/features/expr/ir.py:75
  - src/mpc/features/expr/ir.py:114
- Impact: `ImportError` during test collection; downstream imports fail.

2. Meta diff API regression in models module
- Evidence: tests import `diff_meta` from `mpc.kernel.meta.models`, but function exists in `mpc.kernel.meta.diff`.
- File refs:
  - tests/test_new_features.py:8
  - src/mpc/kernel/meta/diff.py:24
  - src/mpc/kernel/meta/models.py:1
- Impact: `ImportError` during test collection; compatibility break for callers importing from models.

3. Workflow creates `Intent` with wrong constructor argument
- Evidence: `Intent(action=...)` is used, but model requires `kind`.
- File refs:
  - src/mpc/features/workflow/fsm.py:445
  - src/mpc/kernel/contracts/models.py:79
  - src/mpc/kernel/contracts/models.py:80
- Impact: Runtime `TypeError` on workflow `fire` path.

4. WorkflowEngine missing required methods used by tests/runner
- Evidence: `engine.validate()` and `available_transitions()` are called but not implemented on the engine class.
- File refs:
  - src/mpc/tooling/conformance/runner.py:295
  - tests/test_workflow.py:39
  - tests/test_workflow.py:89
  - src/mpc/features/workflow/fsm.py:1
- Impact: `AttributeError`; workflow conformance path breaks.

## Medium

5. Role authorization not consistently enforced
- Evidence:
  - `Transition.auth_roles` exists.
  - `_process_fire` does not enforce `actor_roles` vs `auth_roles`.
  - AST parser path reads `auth_roles`, while fixture path accepts `authRoles` and `auth_roles`.
- File refs:
  - src/mpc/features/workflow/fsm.py:72
  - src/mpc/features/workflow/fsm.py:199
  - src/mpc/features/workflow/fsm.py:275
  - src/mpc/features/workflow/fsm.py:355
- Impact: potential policy bypass and behavior mismatch between construction paths.

## Low

6. Guard evaluation swallows all exceptions
- Evidence: bare `except` in guard expression evaluation.
- File refs:
  - src/mpc/features/workflow/fsm.py:384
- Impact: reduced observability/debuggability; expression failures silently map to guard denial.

## Test Validation Summary

1. `pytest -q` failed at collection with 2 import errors (`ir_from_dict`/`ir_to_dict`, `diff_meta` import path).
2. Running remaining tests (excluding `test_expr.py` and `test_new_features.py`) surfaced workflow interface/runtime failures.

## Open Questions

1. Should `mpc.features.expr.ir` expose `ir_from_dict` and `ir_to_dict` for backward compatibility?
2. Should `diff_meta` be re-exported from `mpc.kernel.meta.models`?
3. Should workflow auth enforce both `auth_port` and role checks (`actor_roles` vs `auth_roles`)?

---

## Release-Readiness Summary (2026-03-13)

### Gate Outcomes

| Gate | Description | Result |
|------|-------------|--------|
| A | Full test suite (`pytest -q`) | ✅ **397 passed** (0.91 s) |
| B | Studio lint + build (`npm run build`) | ✅ Passes — pre-existing lint warnings unrelated to this work |
| C | Studio runtime smoke (browser E2E) | ⚠️ Not executed — requires live browser environment |
| D | Packaging smoke (`pip install -e .` + `mpc-conformance --help`) | ✅ Passes |

### Remediation Work Items

All 10 items from the implementation plan are closed.

| ID | Summary | Area | Status |
|----|---------|------|--------|
| W-01 | Worker DSL interpolation injection hardening | Studio / Security | ✅ Done |
| W-02 | Visualizer XSS – `innerHTML` removed, DOM API + sanitizers | Studio / Security | ✅ Done |
| W-03 | Worker Python API alignment (AST, validator signatures) | Studio / Correctness | ✅ Done |
| W-04 | `pyproject.toml` CLI entrypoint path corrected | Packaging | ✅ Done |
| W-05 | Pyodide version aligned to `0.29.3` (CDN URL + footer) | Studio / Correctness | ✅ Done |
| W-06 | Stale `folderHandle` race in `handleOpenFolder` fixed | Studio / UX | ✅ Done |
| W-07 | Validation debounced at 350 ms | Studio / Performance | ✅ Done |
| W-08 | Worker enforces required module list; missing files throw | Studio / Reliability | ✅ Done |
| W-09 | Semantic validator dead-code / forced-`None` source fixed | Core / Correctness | ✅ Done |
| W-10 | README quick-start corrected (package names, imports, CLI) | Docs | ✅ Done |

### Files Changed

| File | Work Items | Nature |
|------|-----------|--------|
| `tooling/mpc-studio/src/components/Visualizer.tsx` | W-02 | Security — DOM API replaces `innerHTML` |
| `tooling/mpc-studio/src/engine/worker.ts` | W-01, W-03, W-05, W-08 | Security, correctness, version alignment |
| `tooling/mpc-studio/src/App.tsx` | W-05, W-06, W-07, lint | Version footer, race fix, debounce, typings |
| `tooling/mpc-studio/src/components/Sidebar.tsx` | lint | `any` prop type replaced with `ValidationSummary` interface |
| `tooling/mpc-studio/src/engine/mpc-engine.ts` | lint | `Function` types and `any` return replaced with proper types |
| `tooling/mpc-studio/src/types/fs.d.ts` | lint | All 5 `any` types replaced with specific FS API types |
| `pyproject.toml` | W-04 | Corrected CLI entrypoint path |
| `src/mpc/tooling/validator/semantic.py` | W-09 | Dead-code removal, source lookup fix |
| `tooling/mpc-studio/public/mpc/tooling/validator/semantic.py` | W-09 | Mirror of above |
| `README.md` | W-10 | Corrected install command, imports, CLI usage |
| `tests/test_security.py` | W-01, W-02, #5 | 24 new regression tests: DSL injection, XSS literal storage, auth edge cases |
| `findings/implementation_plan.md` | All | Board tracking |

### Gate Summary (final)

| Gate | Result |
|------|--------|
| A — full `pytest -q` | ✅ **421 passed** (397 original + 24 security/auth) |
| B — Studio `npm run lint` | ✅ **0 errors, 0 warnings** |
| B — Studio `npm run build` | ✅ Passes |
| C — Studio runtime smoke | ⚠️ Not executed — requires live browser |
| D — Packaging smoke | ✅ `mpc-conformance --help` passes |

### Remaining Recommendations

2. **Wheel-install CI smoke** — Only editable (`pip install -e .`) has been verified. Add a CI step that builds and installs the wheel (`pip install dist/*.whl`) to confirm the packaged artifact is importable.
3. **Gate C browser smoke** — Manually verify (or add a Playwright test) that loading the Studio in a browser, opening a folder, and running validation produces correct output end-to-end with Pyodide 0.29.3.
