This fixture asserts fail-closed behavior:

- When `fail_open=false`, expression evaluation errors invert the default.
- `visibilityExpr` default is `True` → fails closed to `False` → field hidden.
- `readonlyExpr` default is `False` → fails closed to `True` → field readonly.

