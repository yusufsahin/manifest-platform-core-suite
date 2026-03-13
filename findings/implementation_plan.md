## 1. Regression Fixes (Completed)

### 1.1 High-priority compatibility/runtime fixes
- [x] Restore expression IR compatibility exports (`ir_from_dict`, `ir_to_dict`).
- [x] Restore `diff_meta` compatibility import path via `mpc.kernel.meta.models`.
- [x] Fix workflow intent construction (`Intent(kind=...)` instead of invalid argument).
- [x] Add missing `WorkflowEngine.validate()` and `WorkflowEngine.available_transitions()`.

### 1.2 Authorization and behavior consistency
- [x] Enforce `actor_roles` vs transition `auth_roles` during workflow firing.
- [x] Support both `authRoles` and `auth_roles` in AST transition parsing.
- [x] Replace broad guard-evaluation exception handling with explicit `except Exception`.

### 1.3 Fixture/test alignment
- [x] Align workflow unknown-transition message with conformance fixtures.
- [x] Ensure successful transitions emit expected `R_WF_GUARD_PASS` reason.
- [x] Align missing-initial validation message with conformance fixture text.

## 2. Test Coverage Audit (Status)

### 2.1 `mpc.features.expr`
- [x] Test nested arithmetic operations.
- [x] Test `substr` with out-of-bounds start/length.
- [x] Test `min`/`max` with single argument and empty args.
- [x] Test `now()` behavior when `__clock__` is missing.
- [x] Test `regex` with invalid patterns.
- [x] Expand mixed-type mismatch coverage to all binary operators (including explicit ordering-op TypeError behavior checks).

### 2.2 `mpc.kernel.meta.diff`
- [x] Test breaking change: removing a kind.
- [x] Test breaking change: removing an allowed type from a kind.
- [x] Test breaking change: changing function return type.
- [x] Test non-breaking change: adding a kind.
- [x] Add explicit test for non-breaking optional function addition semantics.

### 2.3 `mpc.tooling.validator`
- [x] Test cycle detection in complex workflows.
- [x] Test duplicate names across different kinds (Entity vs Workflow namespace conflict path).
- [x] Add dedicated invalid function reference tests inside policy expressions.

## 3. Implementation & Verification (Completed)

### 3.1 Automated tests
- [x] Create `tests/test_coverage_edge_cases.py` to host edge-case tests.
- [x] Run `pytest -q` and verify full suite passes.
- [x] Run optional `verify_*.py` scripts as secondary validation (N/A: no `verify_*.py` files present in repository).

### 3.2 Current verification result
- `397 passed` on `pytest -q`.
