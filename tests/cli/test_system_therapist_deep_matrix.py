"""PRUBETH System Therapist & Deep Self-Healing Matrix Tests.

Exhaustively verifies SystemTherapist:
- 7 core therapy pillars
- Configuration drift repair and type coercion
- Terminal codepage detection and remediation
- WAL database checkpointing and SQLite integrity
- Memory garbage collection and footprint metrics
- DevSecOps quarantine directory provisioning
- Speculative Plan B re-arming
- Visual scorecard report rendering
"""

from __future__ import annotations

import io
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from rich.console import Console

from prubeth.cli.therapy import SystemTherapist
from prubeth.config.manager import ConfigManager, DEFAULT_CONFIG


@pytest.fixture
def test_console():
    return Console(file=io.StringIO(), force_terminal=False, width=120)


@pytest.fixture
def therapist_env(tmp_path: Path, test_console: Console):
    cfg_dir = tmp_path / "cfg"
    cfg_mgr = ConfigManager(config_dir=cfg_dir)
    therapist = SystemTherapist(console=test_console, cfg_mgr=cfg_mgr)
    return therapist, cfg_mgr, tmp_path


# ============================================================================
# 1. 7-Pillar Architecture & Report Schema Matrix
# ============================================================================

def test_run_complete_therapy_returns_all_7_pillars(therapist_env):
    therapist, _, _ = therapist_env
    report = therapist.run_complete_therapy()

    assert "pillars" in report
    assert "remediations" in report
    assert report["overall_status"] == "HEALTHY & OPTIMIZED"
    assert len(report["pillars"]) == 7

    expected_prefixes = [
        "1. Terminal",
        "2. Configuration Drift",
        "3. Memory Budget",
        "4. Cognitive Cascade",
        "5. SQLite WAL",
        "6. DevSecOps",
        "7. Speculative Plan B"
    ]
    for i, prefix in enumerate(expected_prefixes):
        assert prefix in report["pillars"][i]["pillar"]
        assert "status" in report["pillars"][i]
        assert "detail" in report["pillars"][i]


# ============================================================================
# 2. Configuration Drift & Schema Therapy Matrix
# ============================================================================

def test_therapy_repairs_corrupted_setting_types(therapist_env):
    therapist, cfg_mgr, _ = therapist_env
    # Inject corrupted string for integer setting into loaded config
    cfg = cfg_mgr.load_config()
    cfg["watchdog_timeout_s"] = "not_an_int"
    cfg_mgr.save_config(cfg)

    report = therapist.run_complete_therapy()

    pillar2 = report["pillars"][1]
    assert pillar2["status"] == "REMEDIED"
    assert "Repaired" in pillar2["detail"]

    # Verify keys were reset to default
    repaired_cfg = cfg_mgr.load_config()
    assert isinstance(repaired_cfg["watchdog_timeout_s"], int)


def test_therapy_repairs_nested_dict_keys(therapist_env):
    therapist, cfg_mgr, _ = therapist_env
    cfg = cfg_mgr.load_config()
    # Remove nested provider endpoint
    if "provider_endpoints" in cfg and "groq" in cfg["provider_endpoints"]:
        del cfg["provider_endpoints"]["groq"]
        cfg_mgr.save_config(cfg)

    report = therapist.run_complete_therapy()
    repaired_cfg = cfg_mgr.load_config()
    assert "groq" in repaired_cfg["provider_endpoints"]


def test_therapy_coerces_invalid_setting_types(therapist_env):
    therapist, cfg_mgr, _ = therapist_env
    cfg = cfg_mgr.load_config()
    # Inject string for int setting
    cfg["watchdog_timeout_s"] = "90"
    cfg["developer_mode"] = "true"
    cfg_mgr.save_config(cfg)

    therapist.run_complete_therapy()

    repaired_cfg = cfg_mgr.load_config()
    assert isinstance(repaired_cfg["watchdog_timeout_s"], int)
    assert repaired_cfg["watchdog_timeout_s"] == 90
    assert isinstance(repaired_cfg["developer_mode"], bool)


# ============================================================================
# 3. WAL Database Persistence Maintenance Matrix
# ============================================================================

def test_therapy_handles_nonexistent_wal_database(therapist_env, monkeypatch):
    therapist, _, tmp_path = therapist_env
    empty_workspace = tmp_path / "empty_workspace_dir"
    empty_workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(empty_workspace)

    report = therapist.run_complete_therapy()
    pillar5 = report["pillars"][4]
    assert pillar5["status"] == "OPTIMAL"
    assert "ready for initial session" in pillar5["detail"].lower()


def test_therapy_performs_wal_checkpoint_and_integrity_check(therapist_env, monkeypatch):
    therapist, _, tmp_path = therapist_env
    db_dir = tmp_path / ".prubeth"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_file = db_dir / "prubeth.db"

    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE test_tab (id INT);")
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    report = therapist.run_complete_therapy()

    pillar5 = report["pillars"][4]
    assert pillar5["status"] == "OPTIMAL"
    assert "WAL truncated & SQLite integrity 100% verified" in pillar5["detail"]


# ============================================================================
# 4. DevSecOps Sandbox & Quarantine Directory Provisioning
# ============================================================================

def test_therapy_creates_quarantine_and_snapshot_directories(therapist_env, monkeypatch):
    therapist, _, tmp_path = therapist_env
    monkeypatch.chdir(tmp_path)

    report = therapist.run_complete_therapy()
    pillar6 = report["pillars"][5]
    assert pillar6["status"] == "OPTIMAL"
    assert "quarantine initialized" in pillar6["detail"].lower()

    assert (tmp_path / ".prubeth" / "quarantine").is_dir()
    assert (tmp_path / ".prubeth" / "snapshots").is_dir()


# ============================================================================
# 5. Speculative Plan B & Resilience Guard Matrix
# ============================================================================

def test_therapy_rearms_disarmed_plan_b_and_rollback(therapist_env):
    therapist, cfg_mgr, _ = therapist_env
    cfg = cfg_mgr.load_config()
    cfg["speculative_plan_b"] = False
    cfg["auto_rollback_on_failure"] = False
    cfg_mgr.save_config(cfg)

    report = therapist.run_complete_therapy()
    pillar7 = report["pillars"][6]
    assert pillar7["status"] == "REMEDIED"

    repaired_cfg = cfg_mgr.load_config()
    assert repaired_cfg["speculative_plan_b"] is True
    assert repaired_cfg["auto_rollback_on_failure"] is True

    # Check remediation action logged
    rem = next(r for r in report["remediations"] if r["pillar"] == "Resilience Guard")
    assert rem["status"] == "APPLIED"
    assert "Speculative Plan B" in rem["action"]


# ============================================================================
# 6. Memory Budget & Garbage Collection Matrix
# ============================================================================

def test_therapy_memory_footprint_thresholds(therapist_env):
    therapist, _, _ = therapist_env

    with patch("psutil.Process") as mock_proc:
        mock_instance = MagicMock()
        # Test optimal (< 33 MB)
        mock_instance.memory_info.return_value.rss = 25 * 1024 * 1024
        mock_proc.return_value = mock_instance

        report = therapist.run_complete_therapy()
        pillar3 = report["pillars"][2]
        assert pillar3["status"] == "OPTIMAL"
        assert "25.00 MB" in pillar3["detail"]

        # Test acceptable (33 - 42 MB)
        mock_instance.memory_info.return_value.rss = 38 * 1024 * 1024
        report = therapist.run_complete_therapy()
        assert report["pillars"][2]["status"] == "ACCEPTABLE"

        # Test warning (> 42 MB)
        mock_instance.memory_info.return_value.rss = 55 * 1024 * 1024
        report = therapist.run_complete_therapy()
        assert report["pillars"][2]["status"] == "WARNING"


# ============================================================================
# 7. Visual Report Rendering Matrix
# ============================================================================

def test_render_therapy_report_prints_scorecard_and_banner(therapist_env):
    therapist, _, _ = therapist_env
    therapist.render_therapy_report()

    output = therapist.console.file.getvalue()
    assert "PRUBETH Autonomous System Therapy & Self-Healing Engine" in output
    assert "Therapy Pillar" in output
    assert "Status" in output
    assert "Diagnostics & Remediations Applied" in output
    assert "System Therapy Completed Successfully!" in output
    assert "100% PERFECT" in output


def test_render_therapy_report_displays_remediations_list(therapist_env):
    therapist, cfg_mgr, _ = therapist_env
    cfg = cfg_mgr.load_config()
    cfg["speculative_plan_b"] = False
    cfg_mgr.save_config(cfg)

    therapist.render_therapy_report()
    output = therapist.console.file.getvalue()
    assert "Remediation Actions Executed" in output
    assert "Resilience Guard" in output
