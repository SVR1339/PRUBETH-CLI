"""PRUBETH Finite State Machine (FSM) 144-State Transition Exhaustive Matrix Tests.

Exhaustively verifies TaskStateMachine across all 12x12 = 144 state pairs:
- Enforces strict deterministic state graph topology
- Validates that allowed transitions succeed and update state history
- Validates that all disallowed transitions raise StateMachineError
- Asserts terminal state sinks: COMPLETED and CANCELLED have zero exit transitions
- Tests on_transition event callback dispatch
"""

from __future__ import annotations

import pytest
from prubeth.runtime.state_machine import TaskState, TaskStateMachine, StateMachineError


ALL_STATES = list(TaskState)

# Compute all 144 transition pairs
ALL_TRANSITION_PAIRS = [
    (from_state, to_state)
    for from_state in ALL_STATES
    for to_state in ALL_STATES
]


@pytest.mark.parametrize("from_state,to_state", ALL_TRANSITION_PAIRS)
def test_all_144_state_transition_pairs(from_state: TaskState, to_state: TaskState):
    """Exhaustive mathematical verification of all 144 directed state transitions."""
    sm = TaskStateMachine(task_id="fsm-audit", initial_state=from_state)
    is_allowed = to_state in TaskStateMachine.ALLOWED_TRANSITIONS.get(from_state, set())

    if is_allowed:
        res = sm.transition_to(to_state, reason=f"Testing legal transition {from_state.value}->{to_state.value}")
        assert res == to_state
        assert sm.current_state == to_state
        assert len(sm.history) == 2
        assert sm.history[-1]["from_state"] == from_state.value
        assert sm.history[-1]["to_state"] == to_state.value
        assert f"Testing legal transition {from_state.value}->{to_state.value}" in sm.history[-1]["reason"]
    else:
        with pytest.raises(StateMachineError) as exc_info:
            sm.transition_to(to_state, reason="Testing illegal transition")
        assert f"Cannot transition task fsm-audit from {from_state.value} to {to_state.value}" in str(exc_info.value)
        # Ensure state did not mutate on error
        assert sm.current_state == from_state
        assert len(sm.history) == 1


# ============================================================================
# Additional FSM Lifecycle and Invariant Tests
# ============================================================================

def test_terminal_states_have_zero_outgoing_transitions():
    assert len(TaskStateMachine.ALLOWED_TRANSITIONS[TaskState.COMPLETED]) == 0
    assert len(TaskStateMachine.ALLOWED_TRANSITIONS[TaskState.CANCELLED]) == 0


@pytest.mark.parametrize("state", ALL_STATES)
def test_is_terminal_predicate(state: TaskState):
    sm = TaskStateMachine(task_id="term-check", initial_state=state)
    if state in (TaskState.COMPLETED, TaskState.CANCELLED):
        assert sm.is_terminal() is True
    else:
        assert sm.is_terminal() is False


def test_transition_callback_invoked_with_correct_arguments():
    callback_records = []

    def tracking_callback(task_id: str, old_state: TaskState, new_state: TaskState, reason: str):
        callback_records.append({
            "task_id": task_id,
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason
        })

    sm = TaskStateMachine(
        task_id="task-callback-test",
        initial_state=TaskState.CREATED,
        on_transition=tracking_callback
    )

    sm.transition_to(TaskState.CONTEXTUALIZING, reason="Step 1")
    sm.transition_to(TaskState.PLANNING, reason="Step 2")

    assert len(callback_records) == 2
    assert callback_records[0]["task_id"] == "task-callback-test"
    assert callback_records[0]["old_state"] == TaskState.CREATED
    assert callback_records[0]["new_state"] == TaskState.CONTEXTUALIZING
    assert callback_records[0]["reason"] == "Step 1"

    assert callback_records[1]["old_state"] == TaskState.CONTEXTUALIZING
    assert callback_records[1]["new_state"] == TaskState.PLANNING
    assert callback_records[1]["reason"] == "Step 2"
