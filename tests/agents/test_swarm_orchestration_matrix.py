"""PRUBETH Multi-Agent Swarm Orchestrator Matrix Tests.

Validates 4-tier specialist collaboration, worktree isolation,
adversarial red-team reviewing, and automated test synthesis.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prubeth.agents.swarm import SwarmOrchestrator, SwarmResult, SwarmPhaseOutcome
from prubeth.agents.base import SubagentResult, SubagentRole


@pytest.fixture
def swarm_fixture():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        (ws / ".prubeth" / "memory").mkdir(parents=True, exist_ok=True)
        (ws / "src").mkdir(parents=True, exist_ok=True)
        orch = SwarmOrchestrator(workspace_root=ws)
        yield orch


def test_swarm_orchestrator_initial_state(swarm_fixture):
    assert swarm_fixture.workspace_root.exists()
    assert swarm_fixture.manager is not None
    assert swarm_fixture.contract_gate is not None


def test_swarm_orchestrator_successful_4_tier_pipeline(swarm_fixture):
    # Mock each tier's execution result
    from prubeth.agents.base import SubagentState
    outcomes = [
        SubagentResult(subagent_id="arch-1", role=SubagentRole.ARCHITECT, success=True, state=SubagentState.COMPLETED, output="Contract specified for AuthModule.", modified_files=["src/auth.py"]),
        SubagentResult(subagent_id="coder-2", role=SubagentRole.CODER, success=True, state=SubagentState.COMPLETED, output="AuthModule implemented.", modified_files=["src/auth.py"]),
        SubagentResult(subagent_id="critic-3", role=SubagentRole.CRITIC, success=True, state=SubagentState.COMPLETED, output="Clean adversarial review. Zero vulnerabilities."),
        SubagentResult(subagent_id="verifier-4", role=SubagentRole.TEST_ENGINEER, success=True, state=SubagentState.COMPLETED, output="3 unit tests verified passing.", modified_files=["tests/test_auth.py"]),
    ]

    with patch.object(swarm_fixture.manager, "run_subagent", side_effect=outcomes):
        res = swarm_fixture.run_swarm("Implement JWT Authentication Module")
        assert res.success is True
        assert res.total_phases == 4
        assert len(res.phases) == 4
        assert res.phases[0].phase_name == "Architect Specifier"
        assert res.phases[1].phase_name == "Code Implementer"
        assert res.phases[2].phase_name == "Adversarial Reviewer"
        assert res.phases[3].phase_name == "Verification Tester"
        assert len(res.adversarial_findings) == 0


def test_swarm_orchestrator_adversarial_vulnerability_captured(swarm_fixture):
    from prubeth.agents.base import SubagentState
    vulnerability_note = "Potential SQL injection vulnerability in search query parameter."
    outcomes = [
        SubagentResult(subagent_id="arch-1", role=SubagentRole.ARCHITECT, success=True, state=SubagentState.COMPLETED, output="Architecture ready."),
        SubagentResult(subagent_id="coder-2", role=SubagentRole.CODER, success=True, state=SubagentState.COMPLETED, output="Query handler created."),
        SubagentResult(subagent_id="critic-3", role=SubagentRole.CRITIC, success=True, state=SubagentState.COMPLETED, output=vulnerability_note),
        SubagentResult(subagent_id="verifier-4", role=SubagentRole.TEST_ENGINEER, success=True, state=SubagentState.COMPLETED, output="Tests executed."),
    ]

    with patch.object(swarm_fixture.manager, "run_subagent", side_effect=outcomes):
        res = swarm_fixture.run_swarm("Implement Search Database Query")
        assert len(res.adversarial_findings) == 1
        assert "SQL injection vulnerability" in res.adversarial_findings[0]


@pytest.mark.parametrize("subagent_role", [
    SubagentRole.ARCHITECT,
    SubagentRole.CODER,
    SubagentRole.CRITIC,
    SubagentRole.TEST_ENGINEER,
])
def test_swarm_subagent_spawning_roles(swarm_fixture, subagent_role):
    spec = swarm_fixture.manager.spawn_subagent(
        role=subagent_role,
        goal=f"Test goal for {subagent_role.value}"
    )
    assert spec.role == subagent_role
    assert spec.id.startswith(subagent_role.value)
    assert spec.worktree_path.exists()
