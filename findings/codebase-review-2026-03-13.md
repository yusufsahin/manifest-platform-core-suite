# Codebase Review - 2026-03-13

## Scope

Repository-wide review focused on:

- correctness
- regression risk
- packaging/runtime issues
- missing or broken test coverage signals

## Findings

### 1. High - Public Python API regressions break test collection

The test suite currently fails during collection because public imports no longer match the module surface:

- `src/mpc/features/expr/ir.py` exposes `from_dict` and `to_dict`, but callers still import `ir_from_dict` directly from that module.
- `src/mpc/kernel/meta/models.py` no longer exposes `diff_meta`, while tests still import it from there.

Observed effect:

- `pytest -q` aborts before running tests.

Relevant files:

- `src/mpc/features/expr/ir.py`
- `src/mpc/kernel/meta/models.py`
- `src/mpc/kernel/meta/diff.py`
- `tests/test_expr.py`
- `tests/test_new_features.py`

### 2. High - Workflow transitions crash on successful execution

`WorkflowEngine` creates an `Intent` with `action=...`, but the contract model defines `Intent(kind, ...)`.

Observed effect:

- allowed transitions raise `TypeError: Intent.__init__() got an unexpected keyword argument 'action'`
- workflow tests and conformance fixtures fail even when transitions should succeed

Relevant files:

- `src/mpc/features/workflow/fsm.py`
- `src/mpc/kernel/contracts/models.py`

### 3. High - WorkflowEngine lost expected methods without compatibility

`WorkflowEngine` no longer provides methods that the current tests and conformance flow still expect:

- `validate()`
- `available_transitions()`

Validation logic exists separately in `src/mpc/features/workflow/validator.py`, but it is not surfaced through the engine.

Observed effect:

- workflow tests fail with `AttributeError`
- conformance workflow fixtures fail on missing engine methods

Relevant files:

- `src/mpc/features/workflow/fsm.py`
- `src/mpc/features/workflow/validator.py`
- `tests/test_workflow.py`

### 4. High - Transition role restrictions are parsed but never enforced

Workflow transitions store `auth_roles`, and `fire()` accepts `actor_roles`, but `_process_fire()` never compares them.

This is more serious than the current crash because after the `Intent` constructor bug is fixed, role-protected transitions will start succeeding for unauthorized actors.

Observed effect:

- authorization behavior is incomplete
- tests expecting role denial would fail after the transition crash is repaired unless this is fixed too

Relevant files:

- `src/mpc/features/workflow/fsm.py`
- `tests/test_workflow.py`

### 5. High - MPC Studio worker calls stale Python APIs

The browser worker in `tooling/mpc-studio` is wired to Python APIs that no longer match the backend:

- it constructs `DomainMeta(name=..., kinds={}, allowed_functions={})`, but `DomainMeta` does not accept `name`
- it calls `validate_semantic(ast, meta)`, but `validate_semantic()` takes only `ast`

Observed effect:

- Studio validation cannot run successfully in the browser worker
- runtime `TypeError` is expected even when the app builds

Relevant files:

- `tooling/mpc-studio/src/engine/worker.ts`
- `src/mpc/kernel/meta/models.py`
- `src/mpc/tooling/validator/semantic.py`

### 6. Medium - Opening a folder does not auto-load the first file

`handleOpenFolder()` stores `folderHandle` in React state and immediately calls `handleFileSelect()`. That function reads `folderHandle` from state, which is still stale in the same tick.

Observed effect:

- the first file in an opened folder is not reliably loaded automatically
- the user must manually click a file after opening the folder

Relevant files:

- `tooling/mpc-studio/src/App.tsx`

### 7. Medium - Studio visualizer has an XSS sink

The visualizer derives Mermaid graph text from DSL content and injects it through `innerHTML`.

Observed effect:

- a crafted manifest can inject markup into the Studio UI
- this is a frontend security issue, even if the app is intended for local use

Relevant files:

- `tooling/mpc-studio/src/components/Visualizer.tsx`

### 8. Medium - Packaged CLI entry point is incorrect

The `pyproject.toml` script points to `mpc.conformance.__main__:main`, but the implementation lives under `mpc.tooling.conformance.__main__`.

Observed effect:

- the packaged CLI target cannot be imported
- `mpc-conformance` would not work after installation without a compatibility shim or corrected entry point

Relevant files:

- `pyproject.toml`
- `src/mpc/tooling/conformance/__main__.py`

## Checks Run

### Python

- `pytest -q`
  - failed during collection with 2 import errors

- `pytest -q --ignore=tests/test_expr.py --ignore=tests/test_new_features.py`
  - 14 failures remained
  - failures were concentrated in workflow behavior and conformance

### Frontend

- `npm run lint` in `tooling/mpc-studio`
  - failed with 12 lint errors
  - primary issues were `any` usage and unsafe function typing

- `npm run build` in `tooling/mpc-studio`
  - build completed
  - warnings remained for CSS import ordering and Pyodide browser compatibility

## Residual Risk

I did not fully diff every mirrored module under `tooling/mpc-studio/public/mpc` against `src/mpc`. Given the API drift already visible in the worker integration, that mirror is likely another source of breakage.
