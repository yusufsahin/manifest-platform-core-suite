# Notes

Type checking MUST reject a call to a function not in the allowed functions list.
`toUpperCase` is not declared in the fixture's functions list or in the preset's
defaultFunctions. The engine MUST produce E_EXPR_UNKNOWN_FUNCTION at typecheck time,
before any evaluation occurs.
