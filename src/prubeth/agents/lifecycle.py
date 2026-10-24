"""PRUBETH Agent Development Life Cycle (Agent-DLC) Engine.

Manages the formal lifecycle stages of autonomous agents:
Inception -> Context Grounding -> Plan Synthesis -> Tool Dispatch -> Reflection & Critique -> Retirement.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime

class AgentLifecycleState(str, Enum):
    INCEPTION = "INCEPTION"
    CONTEXT_GROUNDING = "CONTEXT_GROUNDING"
    PLAN_SYNTHESIS = "PLAN_SYNTHESIS"
    TOOL_DISPATCH = "TOOL_DISPATCH"
    REFLECTION_CRITIQUE = "REFLECTION_CRITIQUE"
    RETIREMENT = "RETIREMENT"
    TERMINATED = "TERMINATED"

class AgentLifecycleManager:
    """Agent-DLC: Evaluates, transitions, and monitors AI agent lifecycles."""

    VALID_TRANSITIONS = {
        AgentLifecycleState.INCEPTION: {AgentLifecycleState.CONTEXT_GROUNDING, AgentLifecycleState.TERMINATED},
        AgentLifecycleState.CONTEXT_GROUNDING: {AgentLifecycleState.PLAN_SYNTHESIS, AgentLifecycleState.TERMINATED},
        AgentLifecycleState.PLAN_SYNTHESIS: {AgentLifecycleState.TOOL_DISPATCH, AgentLifecycleState.TERMINATED},
        AgentLifecycleState.TOOL_DISPATCH: {AgentLifecycleState.REFLECTION_CRITIQUE, AgentLifecycleState.TERMINATED},
        AgentLifecycleState.REFLECTION_CRITIQUE: {AgentLifecycleState.TOOL_DISPATCH, AgentLifecycleState.RETIREMENT, AgentLifecycleState.TERMINATED},
        AgentLifecycleState.RETIREMENT: {AgentLifecycleState.TERMINATED},
        AgentLifecycleState.TERMINATED: set()
    }

    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role
        self.current_state = AgentLifecycleState.INCEPTION
        self.history: List[Dict[str, Any]] = [{
            "state": self.current_state.value,
            "timestamp": datetime.now().isoformat(),
            "note": f"Agent {agent_id} spawned with role {role}"
        }]
        self.iterations = 0
        self.critic_reviews = 0

    def transition_stage(self, new_state: AgentLifecycleState, note: str = "") -> AgentLifecycleState:
        """Transitions agent to the next lifecycle stage according to Agent-DLC invariants."""
        allowed = self.VALID_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Agent-DLC Violation: Cannot transition agent {self.agent_id} "
                f"from {self.current_state.value} to {new_state.value}."
            )
        self.current_state = new_state
        if new_state == AgentLifecycleState.TOOL_DISPATCH:
            self.iterations += 1
        elif new_state == AgentLifecycleState.REFLECTION_CRITIQUE:
            self.critic_reviews += 1

        self.history.append({
            "state": new_state.value,
            "timestamp": datetime.now().isoformat(),
            "note": note
        })
        return self.current_state

    def get_summary(self) -> Dict[str, Any]:
        """Returns comprehensive lifecycle telemetry for evaluation and observability."""
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "current_state": self.current_state.value,
            "iterations": self.iterations,
            "critic_reviews": self.critic_reviews,
            "stages_traversed": len(self.history),
            "is_retired": self.current_state in [AgentLifecycleState.RETIREMENT, AgentLifecycleState.TERMINATED]
        }
