# Notes

Transition from review to published has a guard (ctx.ok).
Meta specifies guard_behavior="fail" — conformance uses a GuardPort that always returns False.
Engine MUST return E_WF_GUARD_FAIL and R_WF_GUARD_FAIL.
