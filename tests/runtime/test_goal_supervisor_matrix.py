"""Unit Test Matrix for PRUBETH Long-Horizon Autonomous Goal Supervisor."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from prubeth.runtime.goal import GoalSupervisor, GoalMilestone
from prubeth.models.gateway import GenerationResponse


def test_goal_milestone_dataclass():
    """Validates GoalMilestone dataclass properties and default values."""
    m = GoalMilestone(
        id=1,
        title="Design Schema",
        description="Write SQLite schema",
        verification_target="schema.sql exists",
    )
    assert m.id == 1
    assert m.status == "PENDING"
    assert m.evidence == ""
    assert m.snapshot_id == ""


def test_decompose_goal_structured_json(tmp_path):
    """Validates decomposition using LLM JSON output."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    supervisor = GoalSupervisor(controller=mock_ctrl)

    llm_output = json.dumps([
        {"id": 1, "title": "Setup", "description": "Init repo", "verification_target": "tests pass"},
        {"id": 2, "title": "Build", "description": "Add feature", "verification_target": "feature works"},
    ])

    with patch.object(supervisor.model_gw, "generate", return_value=GenerationResponse(text=llm_output)):
        milestones = supervisor.decompose_goal("Build user management")
        assert len(milestones) == 2
        assert milestones[0].title == "Setup"
        assert milestones[1].title == "Build"


def test_decompose_goal_markdown_codeblock_parsing(tmp_path):
    """Validates markdown-wrapped JSON extraction during decomposition."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    supervisor = GoalSupervisor(controller=mock_ctrl)

    llm_output = "```json\n" + json.dumps([
        {"id": 1, "title": "Design", "description": "Design contracts", "verification_target": "mypy check"}
    ]) + "\n```"

    with patch.object(supervisor.model_gw, "generate", return_value=GenerationResponse(text=llm_output)):
        milestones = supervisor.decompose_goal("Design API")
        assert len(milestones) == 1
        assert milestones[0].title == "Design"


def test_decompose_goal_fallback_on_invalid_response(tmp_path):
    """Validates deterministic fallback milestone generation on invalid LLM output."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    supervisor = GoalSupervisor(controller=mock_ctrl)

    with patch.object(supervisor.model_gw, "generate", return_value=GenerationResponse(text="Sure! Here are some steps...")):
        milestones = supervisor.decompose_goal("Create a payment service")
        assert len(milestones) == 3
        assert milestones[0].id == 1
        assert "Payment" in milestones[0].description or "payment" in milestones[0].description
        assert milestones[2].id == 3


def test_goal_persistence_lifecycle(tmp_path):
    """Validates save, load, and list lifecycle for goal state files."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    supervisor = GoalSupervisor(controller=mock_ctrl)

    goal_payload = {
        "id": "goal_123",
        "objective": "Build cache engine",
        "status": "IN_PROGRESS",
        "milestones": [
            {"id": 1, "title": "M1", "description": "D1", "verification_target": "V1", "status": "PENDING", "evidence": "", "snapshot_id": ""}
        ],
        "active_milestone_index": 0,
    }

    supervisor.save_goal_state(goal_payload)
    loaded = supervisor.load_goal_state("goal_123")
    assert loaded is not None
    assert loaded["objective"] == "Build cache engine"

    all_goals = supervisor.list_goals()
    assert len(all_goals) >= 1
    assert any(g["id"] == "goal_123" for g in all_goals)


def test_execute_goal_full_success(tmp_path):
    """Validates full sequential milestone completion with verification passes."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    mock_ctrl.run_fluid_turn.return_value = {"text": "Executed milestone task"}

    supervisor = GoalSupervisor(controller=mock_ctrl)

    milestones = [
        GoalMilestone(id=1, title="M1", description="D1", verification_target="test_m1"),
        GoalMilestone(id=2, title="M2", description="D2", verification_target="test_m2"),
    ]

    with patch.object(supervisor, "decompose_goal", return_value=milestones):
        with patch.object(supervisor.snap_mgr, "create_snapshot", side_effect=["snap-0", "snap-1", "snap-2"]):
            with patch.object(supervisor.verifier, "run_self_verification", return_value=(True, "Tests OK")):
                res = supervisor.execute_goal("Complete dual milestones", goal_id="goal_test_succ")
                assert res["success"] is True
                assert res["goal_id"] == "goal_test_succ"
                assert res["milestones_completed"] == 2
                loaded = supervisor.load_goal_state("goal_test_succ")
                assert loaded["status"] == "COMPLETED"
                assert all(m["status"] == "VERIFIED" for m in loaded["milestones"])


def test_execute_goal_auto_heals_failing_milestone(tmp_path):
    """Validates engagement of AutoHealer when milestone verification initially fails."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    mock_ctrl.run_fluid_turn.return_value = {"text": "Executed task"}

    supervisor = GoalSupervisor(controller=mock_ctrl)
    milestones = [GoalMilestone(id=1, title="M1", description="D1", verification_target="test_m1")]

    with patch.object(supervisor, "decompose_goal", return_value=milestones):
        with patch.object(supervisor.snap_mgr, "create_snapshot", side_effect=["snap-0", "snap-1"]):
            with patch.object(supervisor.verifier, "run_self_verification", return_value=(False, "Failed assertion")):
                with patch("prubeth.runtime.goal.AutoHealer") as MockHealer:
                    MockHealer.return_value.heal.return_value = (True, {"diagnosis": "Resolved syntax issue"})
                    res = supervisor.execute_goal("Goal with auto-heal", goal_id="goal_heal_test")
                    assert res["success"] is True
                    assert res["milestones_completed"] == 1
                    loaded = supervisor.load_goal_state("goal_heal_test")
                    assert loaded["status"] == "COMPLETED"
                    assert loaded["milestones"][0]["status"] == "VERIFIED"


def test_execute_goal_failure_rollback(tmp_path):
    """Validates rollback to baseline snapshot when milestone verification and auto-heal fail."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    mock_ctrl.run_fluid_turn.return_value = {"text": "Executed task"}

    supervisor = GoalSupervisor(controller=mock_ctrl)
    milestones = [GoalMilestone(id=1, title="M1", description="D1", verification_target="test_m1")]

    with patch.object(supervisor, "decompose_goal", return_value=milestones):
        with patch.object(supervisor.snap_mgr, "create_snapshot", return_value="snap-baseline"):
            with patch.object(supervisor.snap_mgr, "rollback_to_snapshot") as mock_rollback:
                with patch.object(supervisor.verifier, "run_self_verification", return_value=(False, "Fatal error")):
                    with patch("prubeth.runtime.goal.AutoHealer") as MockHealer:
                        MockHealer.return_value.heal.return_value = (False, {})
                        res = supervisor.execute_goal("Failing goal", goal_id="goal_fail_test")
                        assert res["success"] is False
                        assert res["failed_milestone"] == 1
                        mock_rollback.assert_called_once_with("snap-baseline")
