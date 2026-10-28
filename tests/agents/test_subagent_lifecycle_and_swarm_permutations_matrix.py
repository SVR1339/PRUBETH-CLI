"""PRUBETH Subagent Lifecycle, Swarm & Worktree Permutations Matrix.

Exhaustively verifies SubagentRole, SubagentState, SubagentSpec, SubagentResult,
SubagentManager spawning across all 5 roles, role system instructions,
and SwarmOrchestrator 4-tier pipeline data structures.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.agents.base import (
    SubagentRole,
    SubagentState,
    SubagentSpec,
    SubagentResult,
)
from prubeth.agents.subagent import SubagentManager
from prubeth.agents.swarm import SwarmOrchestrator, SwarmPhaseOutcome, SwarmResult


# ============================================================================
# 1. SubagentRole & SubagentState Enum Invariants Matrix
# ============================================================================

ALL_ROLES = [
    SubagentRole.ARCHITECT,
    SubagentRole.CODER,
    SubagentRole.CRITIC,
    SubagentRole.TEST_ENGINEER,
    SubagentRole.DOCS,
]

ALL_STATES = [
    SubagentState.IDLE,
    SubagentState.RUNNING,
    SubagentState.AUDITING,
    SubagentState.MERGED,
    SubagentState.COMPLETED,
    SubagentState.FAILED,
    SubagentState.CANCELLED,
]


@pytest.mark.parametrize("role", ALL_ROLES)
def test_subagent_role_enum_values(role: SubagentRole):
    assert isinstance(role.value, str)
    assert role == SubagentRole(role.value)
    assert len(role.value) > 2


@pytest.mark.parametrize("state", ALL_STATES)
def test_subagent_state_enum_values(state: SubagentState):
    assert isinstance(state.value, str)
    assert state == SubagentState(state.value)


# ============================================================================
# 2. SubagentSpec & SubagentResult Data Structure Matrix
# ============================================================================

@pytest.mark.parametrize("role", ALL_ROLES)
def test_subagent_spec_instantiation(tmp_path: Path, role: SubagentRole):
    spec = SubagentSpec(
        id=f"test-{role.value}-01",
        role=role,
        goal=f"Test goal for {role.value}",
        model_override="local-model",
        max_turns=12,
        worktree_path=tmp_path / "wt",
        metadata={"priority": "high", "env": "sandbox"}
    )
    assert spec.id == f"test-{role.value}-01"
    assert spec.role == role
    assert spec.max_turns == 12
    assert spec.model_override == "local-model"
    assert spec.worktree_path == tmp_path / "wt"
    assert spec.metadata["priority"] == "high"


@pytest.mark.parametrize("state", ALL_STATES)
def test_subagent_result_properties_and_aliases(state: SubagentState):
    res = SubagentResult(
        subagent_id="agent-xyz-99",
        role=SubagentRole.CODER,
        success=(state in (SubagentState.COMPLETED, SubagentState.MERGED)),
        state=state,
        output="Execution output summary text.",
        diff="--- a/file.py\n+++ b/file.py\n",
        modified_files=["src/main.py", "tests/test_main.py"],
        critic_approved=(state == SubagentState.MERGED),
        critic_notes="Review passed.",
        turns_used=3
    )
    assert res.subagent_id == "agent-xyz-99"
    assert res.state == state
    assert res.summary == res.output
    assert res.files_modified == res.modified_files
    assert len(res.files_modified) == 2
    assert res.turns_used == 3


# ============================================================================
# 3. SubagentManager Spawning Across All Roles Matrix
# ============================================================================

@pytest.mark.parametrize("role", ALL_ROLES)
def test_subagent_manager_spawns_isolated_worktree(tmp_path: Path, role: SubagentRole):
    mgr = SubagentManager(workspace_root=tmp_path)
    goal = f"Execute tasks for {role.value}"

    spec = mgr.spawn_subagent(role=role, goal=goal, max_turns=5)
    assert spec.role == role
    assert spec.goal == goal
    assert spec.max_turns == 5
    assert spec.id in mgr.active_subagents
    assert spec.worktree_path is not None
    assert spec.worktree_path.exists()
    assert spec.worktree_path.is_dir()


@pytest.mark.parametrize("role,expected_phrase", [
    (SubagentRole.ARCHITECT, "architecture"),
    (SubagentRole.CODER, "clean"),
    (SubagentRole.CRITIC, "adversarial"),
    (SubagentRole.TEST_ENGINEER, "test"),
    (SubagentRole.DOCS, "documentation"),
])
def test_subagent_role_system_instructions(tmp_path: Path, role: SubagentRole, expected_phrase: str):
    mgr = SubagentManager(workspace_root=tmp_path)
    prompt = mgr._get_role_system_prompt(role)
    assert isinstance(prompt, str)
    assert len(prompt) > 50
    assert expected_phrase.lower() in prompt.lower()


# ============================================================================
# 4. SwarmOrchestrator Data Structures Matrix
# ============================================================================

def test_swarm_phase_outcome_instantiation():
    outcome = SwarmPhaseOutcome(
        phase_name="Architect Specifier",
        subagent_id="arch-001",
        success=True,
        summary="Formulated AST interface contracts.",
        artifacts_produced=["src/contract.py"],
        diagnostics=["No circular dependencies detected."]
    )
    assert outcome.phase_name == "Architect Specifier"
    assert outcome.subagent_id == "arch-001"
    assert outcome.success is True
    assert len(outcome.artifacts_produced) == 1
    assert len(outcome.diagnostics) == 1


def test_swarm_result_instantiation():
    res = SwarmResult(
        goal="Refactor auth service",
        success=True,
        total_phases=4,
        duration_s=12.5,
        phases=[
            SwarmPhaseOutcome("Architect", "arch-1", True, "Done"),
            SwarmPhaseOutcome("Coder", "coder-1", True, "Implemented"),
            SwarmPhaseOutcome("Critic", "critic-1", True, "Approved"),
            SwarmPhaseOutcome("TestEngineer", "test-1", True, "Verified"),
        ],
        final_output="Auth service refactored with 100% test coverage.",
        adversarial_findings=[]
    )
    assert res.goal == "Refactor auth service"
    assert res.success is True
    assert res.total_phases == 4
    assert res.duration_s == 12.5
    assert len(res.phases) == 4
    assert "100%" in res.final_output


def test_swarm_orchestrator_initialization(tmp_path: Path):
    orchestrator = SwarmOrchestrator(workspace_root=tmp_path)
    assert orchestrator.workspace_root == tmp_path.resolve()
    assert orchestrator.manager is not None
    assert orchestrator.contract_gate is not None
