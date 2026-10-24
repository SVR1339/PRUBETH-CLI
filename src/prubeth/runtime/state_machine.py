from enum import Enum
from typing import Dict, Set, Optional, Callable, List
from datetime import datetime

class TaskState(str, Enum):
    CREATED = "CREATED"
    CONTEXTUALIZING = "CONTEXTUALIZING"
    PLANNING = "PLANNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    READY = "READY"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"

class StateMachineError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass

class TaskStateMachine:
    """Explicit Finite State Machine enforcing validated state transitions."""

    # Valid transitions mapping: current_state -> set of valid next states
    ALLOWED_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
        TaskState.CREATED: {TaskState.CONTEXTUALIZING, TaskState.CANCELLED},
        TaskState.CONTEXTUALIZING: {TaskState.PLANNING, TaskState.FAILED, TaskState.CANCELLED},
        TaskState.PLANNING: {TaskState.WAITING_FOR_APPROVAL, TaskState.READY, TaskState.FAILED, TaskState.CANCELLED},
        TaskState.WAITING_FOR_APPROVAL: {TaskState.READY, TaskState.CANCELLED, TaskState.PLANNING},
        TaskState.READY: {TaskState.EXECUTING, TaskState.PAUSED, TaskState.CANCELLED},
        TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.RECOVERING, TaskState.PAUSED, TaskState.FAILED, TaskState.CANCELLED},
        TaskState.VERIFYING: {TaskState.COMPLETED, TaskState.RECOVERING, TaskState.EXECUTING, TaskState.FAILED},
        TaskState.RECOVERING: {TaskState.PLANNING, TaskState.EXECUTING, TaskState.VERIFYING, TaskState.RECOVERING, TaskState.FAILED, TaskState.CANCELLED},
        TaskState.PAUSED: {TaskState.READY, TaskState.EXECUTING, TaskState.CANCELLED},
        TaskState.COMPLETED: set(), # Terminal
        TaskState.FAILED: {TaskState.RECOVERING, TaskState.CANCELLED}, # Can recover
        TaskState.CANCELLED: set(), # Terminal
    }

    def __init__(self, task_id: str, initial_state: TaskState = TaskState.CREATED, on_transition: Optional[Callable[[str, TaskState, TaskState, str], None]] = None):
        self.task_id = task_id
        self.current_state = initial_state
        self.on_transition = on_transition
        self.history: List[Dict[str, str]] = [{
            "state": initial_state.value,
            "timestamp": datetime.now().isoformat(),
            "reason": "Task initialized"
        }]

    def transition_to(self, new_state: TaskState, reason: str = "") -> TaskState:
        """Validates and executes a state transition."""
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed:
            raise StateMachineError(
                f"Illegal State Transition: Cannot transition task {self.task_id} "
                f"from {self.current_state.value} to {new_state.value}. Allowed next states: {[s.value for s in allowed]}"
            )

        old_state = self.current_state
        self.current_state = new_state
        now = datetime.now().isoformat()
        
        self.history.append({
            "from_state": old_state.value,
            "to_state": new_state.value,
            "timestamp": now,
            "reason": reason
        })

        if self.on_transition:
            self.on_transition(self.task_id, old_state, new_state, reason)

        return self.current_state

    def is_terminal(self) -> bool:
        return self.current_state in {TaskState.COMPLETED, TaskState.CANCELLED}
