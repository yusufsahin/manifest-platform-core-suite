# Notes

Workflow validation MUST reject a definition that does not declare which state
is initial. Without an initial state the FSM cannot be instantiated. The engine
MUST produce E_WF_NO_INITIAL during validation, before any transition is attempted.
