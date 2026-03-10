# Notes

Transition from draft to cancelled requires auth_roles ["admin"].
Actor has actor_roles ["viewer"], so the transition MUST be denied.
Engine MUST return allow=false with E_WF_AUTH_DENIED error and R_WF_AUTH_DENIED reason.
