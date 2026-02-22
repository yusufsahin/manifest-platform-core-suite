# Notes

Valid FSM transition: current state is 'draft', event is 'submit'. A matching
transition (draft → review on submit) exists. No GuardPort is configured.
Engine MUST return allow=true with R_WF_GUARD_PASS reason. The consuming app
is responsible for applying the state change via its own adapter.
