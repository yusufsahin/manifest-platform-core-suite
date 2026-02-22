# Notes

FSM MUST reject a transition event that has no matching `from` entry for the current state.
The only defined transition is draft→published on 'publish'. Current state is 'published',
so triggering 'publish' again has no valid transition and MUST produce E_WF_UNKNOWN_TRANSITION.
