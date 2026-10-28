"""PRUBETH Task State Machine & Transition Invariant Matrix Tests.

Exhaustively verifies TaskStateMachine (Subsystem 1): 12 TaskState enum values,
legal transition lifecycle paths, terminal state sinks, illegal transition rejection
via StateMachineError, transition history audit ledgers, and callback notifications.
"""

from __future__ import annotations

import pytest

from prubeth.runtime.state_machine import (
    TaskState,
    TaskStateMachine,
    StateMachineError,
)


# ============================================================================
# 1. Initial State & History Invariants
# ============================================================================

def test_state_machine_initial_state_created():
    sm = TaskStateMachine(task_id="task-001")
    assert sm.current_state == TaskState.CREATED
    assert sm.task_id == "task-001"
    assert len(sm.history) == 1
    assert sm.history[0]["state"] == "CREATED"
    assert "initialized" in sm.history[0]["reason"].lower()


def test_state_machine_custom_initial_state():
    sm = TaskStateMachine(task_id="task-002", initial_state=TaskState.PLANNING)
    assert sm.current_state == TaskState.PLANNING
    assert sm.history[0]["state"] == "PLANNING"


# ============================================================================
# 2. Canonical Happy Path Lifecycle
# ============================================================================

def test_canonical_happy_path_to_completed():
    sm = TaskStateMachine(task_id="task-happy")

    # CREATED -> CONTEXTUALIZING
    s1 = sm.transition_to(TaskState.CONTEXTUALIZING, reason="Inspecting repo context")
    assert s1 == TaskState.CONTEXTUALIZING

    # CONTEXTUALIZING -> PLANNING
    s2 = sm.transition_to(TaskState.PLANNING, reason="Synthesizing multi-file edit plan")
    assert s2 == TaskState.PLANNING

    # PLANNING -> READY
    s3 = sm.transition_to(TaskState.READY, reason="Plan approved, ready for tool dispatch")
    assert s3 == TaskState.READY

    # READY -> EXECUTING
    s4 = sm.transition_to(TaskState.EXECUTING, reason="Dispatching write_file and run_shell tools")
    assert s4 == TaskState.EXECUTING

    # EXECUTING -> VERIFYING
    s5 = sm.transition_to(TaskState.VERIFYING, reason="Executing pytest suite to verify fix")
    assert s5 == TaskState.VERIFYING

    # VERIFYING -> COMPLETED
    s6 = sm.transition_to(TaskState.COMPLETED, reason="All verification tests pass exit code 0")
    assert s6 == TaskState.COMPLETED

    assert len(sm.history) == 7
    assert sm.history[-1]["to_state"] == "COMPLETED"


# ============================================================================
# 3. Approval Workflow Path
# ============================================================================

def test_planning_waiting_for_approval_path():
    sm = TaskStateMachine(task_id="task-approval")
    sm.transition_to(TaskState.CONTEXTUALIZING)
    sm.transition_to(TaskState.PLANNING)

    # PLANNING -> WAITING_FOR_APPROVAL
    sm.transition_to(TaskState.WAITING_FOR_APPROVAL, reason="Awaiting user confirmation on destructive action")
    assert sm.current_state == TaskState.WAITING_FOR_APPROVAL

    # WAITING_FOR_APPROVAL -> READY
    sm.transition_to(TaskState.READY, reason="User approved proposal")
    assert sm.current_state == TaskState.READY


def test_waiting_for_approval_rejected_returns_to_planning():
    sm = TaskStateMachine(task_id="task-reject")
    sm.transition_to(TaskState.CONTEXTUALIZING)
    sm.transition_to(TaskState.PLANNING)
    sm.transition_to(TaskState.WAITING_FOR_APPROVAL)

    # User requests alternative approach
    sm.transition_to(TaskState.PLANNING, reason="User declined plan; replanning alternative")
    assert sm.current_state == TaskState.PLANNING


# ============================================================================
# 4. Failure & Self-Healing Recovery Cycles
# ============================================================================

def test_executing_recovering_planning_cycle():
    sm = TaskStateMachine(task_id="task-heal")
    sm.transition_to(TaskState.CONTEXTUALIZING)
    sm.transition_to(TaskState.PLANNING)
    sm.transition_to(TaskState.READY)
    sm.transition_to(TaskState.EXECUTING)

    # Tool fails -> RECOVERING
    sm.transition_to(TaskState.RECOVERING, reason="Subprocess failed with exit code 1")
    assert sm.current_state == TaskState.RECOVERING

    # Self-healing loop triggers replanning
    sm.transition_to(TaskState.PLANNING, reason="Synthesizing corrective patch")
    assert sm.current_state == TaskState.PLANNING


def test_failed_can_transition_to_recovering():
    sm = TaskStateMachine(task_id="task-fail-recover")
    sm.transition_to(TaskState.CONTEXTUALIZING)
    sm.transition_to(TaskState.FAILED, reason="Network timeout")

    sm.transition_to(TaskState.RECOVERING, reason="Triggering offline fallback")
    assert sm.current_state == TaskState.RECOVERING


# ============================================================================
# 5. Paused & Resumed Lifecycle
# ============================================================================

def test_pause_and_resume_during_execution():
    sm = TaskStateMachine(task_id="task-pause")
    sm.transition_to(TaskState.CONTEXTUALIZING)
    sm.transition_to(TaskState.PLANNING)
    sm.transition_to(TaskState.READY)
    sm.transition_to(TaskState.EXECUTING)

    # Pause
    sm.transition_to(TaskState.PAUSED, reason="User requested pause via Ctrl+C")
    assert sm.current_state == TaskState.PAUSED

    # Resume directly to executing
    sm.transition_to(TaskState.EXECUTING, reason="User resumed session")
    assert sm.current_state == TaskState.EXECUTING


# ============================================================================
# 6. Cancellation from Multiple Stages
# ============================================================================

@pytest.mark.parametrize("initial_state", [
    TaskState.CREATED,
    TaskState.CONTEXTUALIZING,
    TaskState.PLANNING,
    TaskState.WAITING_FOR_APPROVAL,
    TaskState.READY,
    TaskState.EXECUTING,
    TaskState.PAUSED,
    TaskState.FAILED,
])
def test_cancellation_allowed_from_active_states(initial_state: TaskState):
    sm = TaskStateMachine(task_id="task-cancel", initial_state=initial_state)
    sm.transition_to(TaskState.CANCELLED, reason="User terminated objective")
    assert sm.current_state == TaskState.CANCELLED


# ============================================================================
# 7. Terminal States (Sinks)
# ============================================================================

def test_completed_is_terminal_sink():
    sm = TaskStateMachine(task_id="task-terminal", initial_state=TaskState.COMPLETED)
    with pytest.raises(StateMachineError) as exc_info:
        sm.transition_to(TaskState.EXECUTING)
    assert "Illegal State Transition" in str(exc_info.value)


def test_cancelled_is_terminal_sink():
    sm = TaskStateMachine(task_id="task-terminal", initial_state=TaskState.CANCELLED)
    with pytest.raises(StateMachineError) as exc_info:
        sm.transition_to(TaskState.PLANNING)
    assert "Illegal State Transition" in str(exc_info.value)


# ============================================================================
# 8. Illegal Transitions Matrix
# ============================================================================

@pytest.mark.parametrize("from_state,to_state", [
    (TaskState.CREATED, TaskState.COMPLETED),
    (TaskState.CREATED, TaskState.EXECUTING),
    (TaskState.CREATED, TaskState.VERIFYING),
    (TaskState.CONTEXTUALIZING, TaskState.COMPLETED),
    (TaskState.PLANNING, TaskState.COMPLETED),
    (TaskState.READY, TaskState.COMPLETED),
    (TaskState.PAUSED, TaskState.COMPLETED),
])
def test_illegal_shortcuts_raise_state_machine_error(from_state: TaskState, to_state: TaskState):
    sm = TaskStateMachine(task_id="task-illegal", initial_state=from_state)
    with pytest.raises(StateMachineError):
        sm.transition_to(to_state)


# ============================================================================
# 9. Transition Callback Notification
# ============================================================================

def test_transition_fires_callback():
    notified = []

    def on_trans(task_id, old_st, new_st, reason):
        notified.append({
            "task_id": task_id,
            "old": old_st,
            "new": new_st,
            "reason": reason
        })

    sm = TaskStateMachine(task_id="task-callback", on_transition=on_trans)
    sm.transition_to(TaskState.CONTEXTUALIZING, reason="Beginning scan")

    assert len(notified) == 1
    assert notified[0]["task_id"] == "task-callback"
    assert notified[0]["old"] == TaskState.CREATED
    assert notified[0]["new"] == TaskState.CONTEXTUALIZING
    assert notified[0]["reason"] == "Beginning scan"
