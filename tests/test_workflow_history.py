from mpc.features.workflow.fsm import WorkflowEngine, FSMState, Transition

def test_shallow_history():
    # A -> (B -> C)
    # Return from any to A, then back to composite B. Should return to C if shallow history.
    engine = WorkflowEngine(
        states={
            "A": FSMState("A"),
            "B": FSMState("B", history_mode="shallow"),
            "C": FSMState("C", parent="B", is_initial=True),
            "D": FSMState("D", parent="B"),
        },
        transitions=[
            Transition(from_state="A", to_state="B", on="enter_b"),
            Transition(from_state="C", to_state="D", on="next"),
            Transition(from_state="B", to_state="A", on="exit_b"),
        ],
        initial_state="A"
    )
    
    engine.activate()
    assert engine.current_state == "A"
    
    engine.fire("enter_b")
    assert engine.current_state == "B,C"
    
    engine.fire("next")
    assert engine.current_state == "B,D"
    
    # Exit B to A. This should save history for B.
    engine.fire("exit_b")
    assert engine.current_state == "A"
    
    # Re-enter B. Should restore D.
    engine.fire("enter_b")
    assert engine.current_state == "B,D"

def test_deep_history():
    # A -> (B -> (C -> D))
    # Deep history should restore the leaf state even if multiple levels deep.
    engine = WorkflowEngine(
        states={
            "A": FSMState("A"),
            "B": FSMState("B", history_mode="deep"),
            "C": FSMState("C", parent="B", is_initial=True),
            "D": FSMState("D", parent="C", is_initial=True),
            "E": FSMState("E", parent="C"),
        },
        transitions=[
            Transition(from_state="A", to_state="B", on="enter_b"),
            Transition(from_state="D", to_state="E", on="next"),
            Transition(from_state="B", to_state="A", on="exit_b"),
        ],
        initial_state="A"
    )
    
    engine.activate()
    engine.fire("enter_b")
    assert engine.current_state == "B,C,D"
    
    engine.fire("next")
    assert engine.current_state == "B,C,E"
    
    engine.fire("exit_b")
    assert engine.current_state == "A"
    
    engine.fire("enter_b")
    assert engine.current_state == "B,C,E"

def test_parallel_history():
    # A -> (B [Parallel] -> (C -> D, F -> G))
    engine = WorkflowEngine(
        states={
            "A": FSMState("A"),
            "B": FSMState("B", is_parallel=True, history_mode="deep"),
            "C": FSMState("C", parent="B", is_initial=True),
            "D": FSMState("D", parent="C"),
            "F": FSMState("F", parent="B", is_initial=True),
            "G": FSMState("G", parent="F"),
        },
        transitions=[
            Transition(from_state="A", to_state="B", on="enter_b"),
            Transition(from_state="C", to_state="D", on="next_c"),
            Transition(from_state="F", to_state="G", on="next_f"),
            Transition(from_state="B", to_state="A", on="exit_b"),
        ],
        initial_state="A"
    )
    
    engine.activate()
    engine.fire("enter_b")
    # Parallel entry: enters ALL initial children
    assert "C" in engine.active_states
    assert "F" in engine.active_states
    
    engine.fire("next_c")
    engine.fire("next_f")
    assert "D" in engine.active_states
    assert "G" in engine.active_states
    
    engine.fire("exit_b")
    assert engine.current_state == "A"
    
    engine.fire("enter_b")
    assert "D" in engine.active_states
    assert "G" in engine.active_states

if __name__ == "__main__":
    test_shallow_history()
    test_deep_history()
    test_parallel_history()
    print("All history tests passed!")
