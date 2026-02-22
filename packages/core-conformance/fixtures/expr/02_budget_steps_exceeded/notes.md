# Notes

Expression step budget enforcement. `len("hello")` is a valid expression but
maxExprSteps is overridden to 1 in meta.limits. Any expression requiring more
than 1 step MUST produce E_BUDGET_EXCEEDED. Step counting includes function
call overhead, argument evaluation, and result production.
