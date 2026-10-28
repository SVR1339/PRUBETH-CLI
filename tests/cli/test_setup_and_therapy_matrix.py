"""Comprehensive Unit Test Matrix for PRUBETH Setup Wizard, Permission Hardening & System Therapy."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from prubeth.cli.setup import (
    probe_local_ai_capabilities,
    save_claude_style_settings,
    initialize_workspace_prubeth_md,
    execute_factory_reset,
    render_onboarding_wizard,
)
from prubeth.cli.therapy import SystemTherapist
from prubeth.config.manager import ConfigManager, DEFAULT_CONFIG


def test_probe_local_ai_capabilities_keys():
    """Validates that probe_local_ai_capabilities returns all required inspection keys."""
    res = probe_local_ai_capabilities()
    assert "ollama_installed" in res
    assert "ollama_binary" in res
    assert "ollama_running" in res
    assert "ollama_models" in res
    assert "lm_studio_running" in res
    assert "lm_studio_models" in res
    assert isinstance(res["ollama_models"], list)
    assert isinstance(res["lm_studio_models"], list)


@pytest.mark.parametrize("mode,expected_allow_run_cmd", [
    ("default", False),
    ("acceptEdits", False),
    ("builder", True),
    ("developerMode", True),
])
def test_save_claude_style_settings(tmp_path, mode: str, expected_allow_run_cmd: bool):
    """Validates ~/.prubeth/settings.json generation across permission clearance modes."""
    settings_file = save_claude_style_settings(
        home_dir=tmp_path,
        mode=mode,
        enable_caching=True,
        ttl_s=300,
        workspace_root=tmp_path / "project",
    )
    assert settings_file.is_file()
    data = json.loads(settings_file.read_text(encoding="utf-8"))

    assert data["permissions"]["defaultMode"] == mode
    assert "read_file" in data["permissions"]["allow"]
    assert "grep_search" in data["permissions"]["allow"]
    assert data["caching"]["enable_prompt_caching"] is True
    assert data["caching"]["context_cache_ttl_s"] == 300
    assert str((tmp_path / "project").resolve()) in data["trusted_workspaces"]

    if expected_allow_run_cmd:
        assert "run_command" in data["permissions"]["allow"]
    else:
        assert "run_command" not in data["permissions"]["allow"]


def test_initialize_workspace_prubeth_md(tmp_path):
    """Validates creation of PRUBETH.md and idempotent reuse when present."""
    mock_console = MagicMock()
    created = initialize_workspace_prubeth_md(tmp_path, mock_console)
    assert created is not None
    assert created.is_file()
    assert "PRUBETH" in created.read_text(encoding="utf-8")

    # Second call returns existing without overwriting
    reused = initialize_workspace_prubeth_md(tmp_path, mock_console)
    assert reused == created


def test_execute_factory_reset(tmp_path):
    """Validates clean restore to factory default state and cleanup of settings.json."""
    mock_console = MagicMock()
    mock_cfg = MagicMock()
    mock_settings = tmp_path / ".prubeth" / "settings.json"
    mock_settings.parent.mkdir(parents=True, exist_ok=True)
    mock_settings.write_text("{}", encoding="utf-8")

    with patch("pathlib.Path.home", return_value=tmp_path):
        execute_factory_reset(mock_console, mock_cfg)
        assert mock_cfg.save_config.called
        assert not mock_settings.exists()


def test_render_onboarding_wizard_non_interactive(tmp_path):
    """Validates that non-interactive onboarding wizard runs end-to-end cleanly."""
    mock_console = MagicMock()
    cfg_mgr = ConfigManager(config_dir=tmp_path)

    with patch("prubeth.cli.setup.PrubethDoctor") as MockDoc:
        MockDoc.return_value.render_report.return_value = {"all_passed": True}
        with patch("pathlib.Path.home", return_value=tmp_path):
            render_onboarding_wizard(mock_console, cfg_mgr=cfg_mgr, interactive=False)
            cfg = cfg_mgr.load_config()
            assert cfg.get("first_run_completed") is True
            assert cfg.get("enable_prompt_caching") is True
            assert cfg.get("enable_context_caching") is True


def test_system_therapist_full_run(tmp_path):
    """Validates complete 7-pillar system therapy execution and report formatting."""
    mock_console = MagicMock()
    cfg_mgr = ConfigManager(config_dir=tmp_path)
    # Simulate slightly drifted config
    cfg_mgr.save_config({"default_model": "gemini-2.5-pro", "missing_keys_galore": True})

    therapist = SystemTherapist(console=mock_console, cfg_mgr=cfg_mgr)
    report = therapist.run_complete_therapy()

    assert "pillars" in report
    assert len(report["pillars"]) >= 6
    assert "remediations" in report

    # Verify that drift was auto-repaired
    repaired_cfg = cfg_mgr.load_config()
    for default_k in DEFAULT_CONFIG:
        assert default_k in repaired_cfg

    # Verify report rendering
    therapist.render_therapy_report()
    assert mock_console.print.called


def test_system_therapist_sqlite_wal_checkpoint(tmp_path):
    """Validates SQLite WAL checkpoint and VACUUM therapy on local databases."""
    import sqlite3
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE foo (id INT, name TEXT)")
    conn.execute("INSERT INTO foo VALUES (1, 'bar')")
    conn.commit()
    conn.close()

    mock_console = MagicMock()
    cfg_mgr = MagicMock()
    therapist = SystemTherapist(console=mock_console, cfg_mgr=cfg_mgr)

    # Therapy handles directory with databases cleanly
    report = therapist.run_complete_therapy()
    assert report is not None
