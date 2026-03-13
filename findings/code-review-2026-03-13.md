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
