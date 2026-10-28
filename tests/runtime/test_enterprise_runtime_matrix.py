"""Unit Test Matrix for PRUBETH Enterprise Runtime: Issue Resolver and Codebase Migrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from prubeth.runtime.enterprise import (
    AutonomousIssueResolver,
    AutonomousCodebaseMigrator,
    EnterpriseTicketResolver,
    EnterpriseMigrator,
)


def test_enterprise_aliases_compatibility():
    """Validates backwards compatibility of class aliases."""
    assert EnterpriseTicketResolver is AutonomousIssueResolver
    assert EnterpriseMigrator is AutonomousCodebaseMigrator


def test_issue_resolver_initialization(tmp_path):
    """Validates AutonomousIssueResolver initialization and directory resolution."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    resolver = AutonomousIssueResolver(controller=mock_ctrl)
    assert resolver.workspace_root == tmp_path.resolve()
    assert resolver.controller is mock_ctrl


def test_issue_resolver_success_flow(tmp_path):
    """Validates successful end-to-end autonomous issue resolution."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    mock_ctrl.run_fluid_turn.return_value = {"text": "Diagnosed and applied bugfix"}

    resolver = AutonomousIssueResolver(controller=mock_ctrl)

    with patch.object(resolver.index, "search", return_value=[MagicMock(file_path="src/auth.py")]):
        with patch.object(resolver.snap_mgr, "create_snapshot", side_effect=["snap-start", "snap-verified"]):
            with patch.object(resolver.verifier, "run_self_verification", return_value=(True, "All tests passed")):
                res = resolver.resolve_issue("Fix KeyError on missing token attribute")
                assert res["success"] is True
                assert res["snapshot_id"] == "snap-verified"
                assert "src/auth.py" in res["candidate_files"]
                assert "Diagnosed" in res["summary"]


def test_issue_resolver_auto_heal_recovery(tmp_path):
    """Validates issue resolver auto-healing pivot when tests initially fail."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    mock_ctrl.run_fluid_turn.return_value = {"text": "Applied initial patch"}

    resolver = AutonomousIssueResolver(controller=mock_ctrl)

    with patch.object(resolver.index, "search", return_value=[]):
        with patch.object(resolver.snap_mgr, "create_snapshot", side_effect=["snap-1", "snap-2"]):
            with patch.object(resolver.verifier, "run_self_verification", return_value=(False, "AssertionError on line 42")):
                with patch("prubeth.runtime.enterprise.AutoHealer") as MockHealer:
                    MockHealer.return_value.heal.return_value = (True, {"diagnosis": "Fixed off-by-one error"})
                    res = resolver.resolve_issue("Off by one error in index slice")
                    assert res["success"] is True
                    assert "Self-Healed" in res["summary"]


def test_issue_resolver_failure_rollback(tmp_path):
    """Validates rollback to initial snapshot if auto-healing also fails."""
    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    mock_ctrl.run_fluid_turn.return_value = {"text": "Applied broken patch"}

    resolver = AutonomousIssueResolver(controller=mock_ctrl)

    with patch.object(resolver.index, "search", return_value=[]):
        with patch.object(resolver.snap_mgr, "create_snapshot", return_value="snap-rollback-target"):
            with patch.object(resolver.snap_mgr, "rollback_to_snapshot") as mock_rollback:
                with patch.object(resolver.verifier, "run_self_verification", return_value=(False, "SyntaxError")):
                    with patch("prubeth.runtime.enterprise.AutoHealer") as MockHealer:
                        MockHealer.return_value.heal.return_value = (False, {})
                        res = resolver.resolve_issue("Syntax error in module")
                        assert res["success"] is False
                        assert "Verification failed" in res["error"]
                        mock_rollback.assert_called_once_with("snap-rollback-target")


def test_codebase_migrator_plan_migration_file_filtering(tmp_path):
    """Validates file discovery and exclusion of ignore patterns."""
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "service.py").write_text("code", encoding="utf-8")
    (tmp_path / "src" / "util.py").write_text("code", encoding="utf-8")
    (tmp_path / ".prubeth" / "ignored.py").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".git" / "hooks.py").mkdir(parents=True, exist_ok=True)

    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    migrator = AutonomousCodebaseMigrator(controller=mock_ctrl)

    plan = migrator.plan_migration("AsyncIO refactor")
    assert "src/service.py" in plan
    assert "src/util.py" in plan
    assert not any(p.startswith(".prubeth") for p in plan)
    assert not any(p.startswith(".git") for p in plan)


def test_codebase_migrator_execute_success(tmp_path):
    """Validates successful staged codebase migration across target files."""
    (tmp_path / "app.py").write_text("import requests", encoding="utf-8")

    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)
    mock_ctrl.run_fluid_turn.return_value = {"text": "Migrated requests to httpx"}

    migrator = AutonomousCodebaseMigrator(controller=mock_ctrl)

    with patch.object(migrator.snap_mgr, "create_snapshot", side_effect=["snap-start", "snap-done"]):
        with patch.object(migrator.verifier, "run_self_verification", return_value=(True, "Tests OK")):
            res = migrator.execute_migration("Migrate to httpx.AsyncClient")
            assert res["success"] is True
            assert res["snapshot_id"] == "snap-done"
            assert "app.py" in res["transformed_files"]


def test_codebase_migrator_execute_failure_rollback(tmp_path):
    """Validates rollback when migration introduces regressions that cannot be auto-healed."""
    (tmp_path / "app.py").write_text("code", encoding="utf-8")

    mock_ctrl = MagicMock()
    mock_ctrl.workspace_root = str(tmp_path)

    migrator = AutonomousCodebaseMigrator(controller=mock_ctrl)

    with patch.object(migrator.snap_mgr, "create_snapshot", return_value="snap-init"):
        with patch.object(migrator.snap_mgr, "rollback_to_snapshot") as mock_rollback:
            with patch.object(migrator.verifier, "run_self_verification", return_value=(False, "Failed")):
                with patch("prubeth.runtime.enterprise.AutoHealer") as MockHealer:
                    MockHealer.return_value.heal.return_value = (False, {})
                    res = migrator.execute_migration("Broken migration")
                    assert res["success"] is False
                    assert "rolled back" in res["error"]
                    mock_rollback.assert_called_once_with("snap-init")
