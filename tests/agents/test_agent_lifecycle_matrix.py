"""PRUBETH Agent Development Life Cycle (Agent-DLC) Matrix.

Exhaustively verifies agent lifecycle state transitions, boundary constraints,
disallowed bypasses, iteration counters, critic reviews, and telemetry summaries.
"""

from __future__ import annotations

import pytest
from prubeth.agents.lifecycle import AgentLifecycleManager, AgentLifecycleState


# ============================================================================
# 1. Standard Happy Path Transitions
# ============================================================================

def test_agent_lifecycle_initial_state():
    """Agent initializes in INCEPTION state with zero iterations."""
    mgr = AgentLifecycleManager(agent_id="agent-001", role="architect")
    assert mgr.current_state == AgentLifecycleState.INCEPTION
    assert mgr.iterations == 0
    assert mgr.critic_reviews == 0
    assert len(mgr.history) == 1
    assert "agent-001" in mgr.history[0]["note"]


def test_agent_lifecycle_complete_happy_path():
    """Traverses complete lifecycle: INCEPTION -> GROUNDING -> PLAN -> DISPATCH -> CRITIQUE -> RETIREMENT -> TERMINATED."""
    mgr = AgentLifecycleManager(agent_id="agent-002", role="coder")

    mgr.transition_stage(AgentLifecycleState.CONTEXT_GROUNDING, "Loaded repository skeleton")
    assert mgr.current_state == AgentLifecycleState.CONTEXT_GROUNDING

    mgr.transition_stage(AgentLifecycleState.PLAN_SYNTHESIS, "Formulated 3-step patch plan")
    assert mgr.current_state == AgentLifecycleState.PLAN_SYNTHESIS

    mgr.transition_stage(AgentLifecycleState.TOOL_DISPATCH, "Executing write_file tool")
    assert mgr.current_state == AgentLifecycleState.TOOL_DISPATCH
    assert mgr.iterations == 1

    mgr.transition_stage(AgentLifecycleState.REFLECTION_CRITIQUE, "Reviewing diff against AST contracts")
    assert mgr.current_state == AgentLifecycleState.REFLECTION_CRITIQUE
    assert mgr.critic_reviews == 1

    mgr.transition_stage(AgentLifecycleState.RETIREMENT, "Task completed successfully")
    assert mgr.current_state == AgentLifecycleState.RETIREMENT

    mgr.transition_stage(AgentLifecycleState.TERMINATED, "Worktree cleaned up")
    assert mgr.current_state == AgentLifecycleState.TERMINATED
    assert len(mgr.history) == 7


def test_agent_lifecycle_reflection_loop_back_to_dispatch():
    """Critic rejection triggers reflection loop back to TOOL_DISPATCH with incremented iterations."""
    mgr = AgentLifecycleManager(agent_id="agent-loop", role="coder")
    mgr.transition_stage(AgentLifecycleState.CONTEXT_GROUNDING)
    mgr.transition_stage(AgentLifecycleState.PLAN_SYNTHESIS)

    # First attempt
    mgr.transition_stage(AgentLifecycleState.TOOL_DISPATCH, "Attempt 1")
    assert mgr.iterations == 1
    mgr.transition_stage(AgentLifecycleState.REFLECTION_CRITIQUE, "Critic found syntax defect")
    assert mgr.critic_reviews == 1

    # Second attempt (loop back)
    mgr.transition_stage(AgentLifecycleState.TOOL_DISPATCH, "Attempt 2: Fixed syntax defect")
    assert mgr.iterations == 2

    # Second critique approved
    mgr.transition_stage(AgentLifecycleState.REFLECTION_CRITIQUE, "Critic approved diff")
    assert mgr.critic_reviews == 2

    mgr.transition_stage(AgentLifecycleState.RETIREMENT, "Finished")
    assert mgr.current_state == AgentLifecycleState.RETIREMENT


# ============================================================================
# 2. Invariant Violations & Illegal Transitions
# ============================================================================

def test_agent_lifecycle_blocks_illegal_jump_from_inception_to_dispatch():
    """Agents cannot skip context grounding and jump directly to tool dispatch."""
    mgr = AgentLifecycleManager(agent_id="agent-bad", role="coder")
    with pytest.raises(ValueError, match="Agent-DLC Violation"):
        mgr.transition_stage(AgentLifecycleState.TOOL_DISPATCH)


def test_agent_lifecycle_blocks_illegal_jump_from_plan_to_retirement():
    """Agents cannot retire without executing actions or going through critique."""
    mgr = AgentLifecycleManager(agent_id="agent-bad", role="coder")
    mgr.transition_stage(AgentLifecycleState.CONTEXT_GROUNDING)
    mgr.transition_stage(AgentLifecycleState.PLAN_SYNTHESIS)
    with pytest.raises(ValueError, match="Agent-DLC Violation"):
        mgr.transition_stage(AgentLifecycleState.RETIREMENT)


def test_agent_lifecycle_terminated_state_is_sink():
    """TERMINATED state has no outgoing transitions."""
    mgr = AgentLifecycleManager(agent_id="agent-term", role="docs")
    mgr.transition_stage(AgentLifecycleState.TERMINATED, "Killed early")
    assert mgr.current_state == AgentLifecycleState.TERMINATED

    with pytest.raises(ValueError, match="Agent-DLC Violation"):
        mgr.transition_stage(AgentLifecycleState.INCEPTION)


# ============================================================================
# 3. Early Termination & Summary Telemetry
# ============================================================================

def test_agent_lifecycle_early_termination_from_any_stage():
    """Agent can be terminated early from any active stage on failure or user cancellation."""
    for stage in [
        AgentLifecycleState.CONTEXT_GROUNDING,
        AgentLifecycleState.PLAN_SYNTHESIS,
        AgentLifecycleState.TOOL_DISPATCH,
        AgentLifecycleState.REFLECTION_CRITIQUE,
    ]:
        mgr = AgentLifecycleManager(agent_id=f"agent-{stage.value}", role="test")
        # Advance to stage
        if stage != AgentLifecycleState.CONTEXT_GROUNDING:
            mgr.transition_stage(AgentLifecycleState.CONTEXT_GROUNDING)
        if stage in [AgentLifecycleState.PLAN_SYNTHESIS, AgentLifecycleState.TOOL_DISPATCH, AgentLifecycleState.REFLECTION_CRITIQUE]:
            mgr.transition_stage(AgentLifecycleState.PLAN_SYNTHESIS)
        if stage in [AgentLifecycleState.TOOL_DISPATCH, AgentLifecycleState.REFLECTION_CRITIQUE]:
            mgr.transition_stage(AgentLifecycleState.TOOL_DISPATCH)
        if stage == AgentLifecycleState.REFLECTION_CRITIQUE:
            mgr.transition_stage(AgentLifecycleState.REFLECTION_CRITIQUE)

        # Terminate
        mgr.transition_stage(AgentLifecycleState.TERMINATED, f"Aborted at {stage.value}")
        assert mgr.current_state == AgentLifecycleState.TERMINATED


def test_agent_lifecycle_get_summary_telemetry():
    """Summary dictionary contains exact execution counts and retirement status."""
    mgr = AgentLifecycleManager(agent_id="summary-agent", role="critic")
    mgr.transition_stage(AgentLifecycleState.CONTEXT_GROUNDING)
    mgr.transition_stage(AgentLifecycleState.PLAN_SYNTHESIS)
    mgr.transition_stage(AgentLifecycleState.TOOL_DISPATCH)
    mgr.transition_stage(AgentLifecycleState.REFLECTION_CRITIQUE)
    mgr.transition_stage(AgentLifecycleState.RETIREMENT)

    summary = mgr.get_summary()
    assert summary["agent_id"] == "summary-agent"
    assert summary["role"] == "critic"
    assert summary["current_state"] == "RETIREMENT"
    assert summary["iterations"] == 1
    assert summary["critic_reviews"] == 1
    assert summary["stages_traversed"] == 6
    assert summary["is_retired"] is True


def test_agent_lifecycle_is_not_retired_while_active():
    mgr = AgentLifecycleManager(agent_id="active-agent", role="coder")
    summary = mgr.get_summary()
    assert summary["is_retired"] is False
