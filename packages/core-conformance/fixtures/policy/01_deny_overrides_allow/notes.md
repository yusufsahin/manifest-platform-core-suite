# Notes

Policy evaluation with deny-wins strategy: both policies match the event (kind=delete).
p1 (priority=10) allows; p2 (priority=20) denies. With deny-wins, any deny MUST produce
allow=false regardless of matching allow policies. Only deny reasons are propagated.

Policies are evaluated in priority desc order (p2 first, then p1). Final: allow=false.
