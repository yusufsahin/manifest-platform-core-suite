# Notes

Expression depth budget enforcement. `isEmpty(len("hello"))` has call depth 2
(isEmpty at depth 1, len at depth 2). maxExprDepth is overridden to 1 in meta.limits.
The engine MUST detect the depth violation before or during evaluation and return
E_EXPR_LIMIT_DEPTH without executing the expression.
