This fixture asserts budget enforcement:

- `limits.maxExprSteps` is set low via `meta.json`.
- A long `visibilityExpr` exceeds step budget and raises `MPCBudgetError`.
- With `fail_open=false`, visibility fails closed → field is hidden.

