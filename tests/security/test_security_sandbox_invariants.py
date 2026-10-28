"""Tests for PRUBETH Security Sandbox, Path Boundary Enforcement, and Dangerous Command Filtering."""

import os
import re
import pytest
from pathlib import Path

from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase
from prubeth.tools.core.run_shell import RunShellTool, DANGEROUS_COMMAND_PATTERNS
from prubeth.tools.base import ToolClearanceLevel
from prubeth.tools.registry import ToolRegistry


# =========================================================================
# Path Boundary & Workspace Escapes
# =========================================================================

def test_security_engine_blocks_relative_directory_traversal(tmp_path: Path):
    sec = SecurityEngine(workspace_root=str(tmp_path))
    valid, _, err = sec.validate_path("../outside.txt")
    assert valid is False
    assert "escapes workspace" in err.lower() or "violation" in err.lower()


def test_security_engine_blocks_deep_relative_traversal(tmp_path: Path):
    sec = SecurityEngine(workspace_root=str(tmp_path))
    valid, _, err = sec.validate_path("sub/../../outside.txt")
    assert valid is False


def test_security_engine_blocks_windows_system_paths(tmp_path: Path):
    sec = SecurityEngine(workspace_root=str(tmp_path))
    valid, _, err = sec.validate_path("C:\\Windows\\System32\\cmd.exe")
    assert valid is False


def test_security_engine_allows_clean_internal_paths(tmp_path: Path):
    sec = SecurityEngine(workspace_root=str(tmp_path))
    valid, target_path, err = sec.validate_path("src/core/main.py")
    assert valid is True
    assert err == ""
    assert str(target_path).startswith(str(tmp_path))


# =========================================================================
# Dangerous Command Filtering Invariants
# =========================================================================

@pytest.mark.parametrize("cmd", [
    "rm -rf /",
    "rm -rf /var",
    "rm -rf *",
    "rm -rf  *",
    "mkfs",
    "mkfs.ext4 /dev/sda",
    ":(){ :|:& };:",
    ":() { :|:& };:",
    "format C:",
    "format d: /q",
    "del /f /s /q C:\\",
    "del /F/S/Q C:\\Windows",
    "DROP DATABASE users;",
    "drop database production",
])
def test_run_shell_tool_blocks_dangerous_commands(cmd: str):
    tool = RunShellTool()
    res = tool.execute({"command": cmd})
    assert res.success is False
    assert res.exit_code == 403
    assert "Security Violation" in res.output


@pytest.mark.parametrize("safe_cmd", [
    "git format-patch HEAD~1",
    "python -c \"print('format string')\"",
    "echo \"hello world\"",
    "ls -la",
    "git status",
    "pytest -v",
])
def test_run_shell_tool_allows_safe_commands_with_benign_words(safe_cmd: str):
    tool = RunShellTool()
    # Check that dangerous pattern filter does NOT trigger on benign commands
    for pat in DANGEROUS_COMMAND_PATTERNS:
        match = re.search(pat, safe_cmd, re.IGNORECASE)
        # git format-patch must not match format [a-zA-Z]:
        assert not match, f"Benign command '{safe_cmd}' incorrectly triggered pattern '{pat}'"


# =========================================================================
# Permission Clearance and Audit Trail Invariants
# =========================================================================

def test_registry_clearance_filtering_all_levels():
    reg = ToolRegistry(populate_defaults=True)
    all_tools = reg.list_tools()
    assert len(all_tools) == 37

    read_only_expected = {
        "read_file", "list_dir", "grep_search", "glob_search", "git_status", "git_diff", "git_log",
        "code_structure", "find_callers", "find_callees", "find_type_definition", "find_implementations",
        "detect_circular_imports", "trace_data_flow", "find_dead_code", "rank_central_files", "explain_symbol",
        "lint_checker", "type_checker", "coverage_analyser", "patch_verifier",
        "todo", "test_gen", "security_linter", "crash_debugger", "spec_contract"
    }
    mutation_expected = {"write_file", "edit_file", "delete_file", "copy_file", "move_file", "git_commit", "heal"}
    execution_expected = {"run_shell", "run_python", "test_runner", "benchmark"}

    for tool in all_tools:
        if tool.clearance_level == ToolClearanceLevel.READ_ONLY:
            assert tool.name in read_only_expected
        elif tool.clearance_level == ToolClearanceLevel.WORKSPACE_MUTATION:
            assert tool.name in mutation_expected
        elif tool.clearance_level == ToolClearanceLevel.SYSTEM_EXECUTION:
            assert tool.name in execution_expected


def test_audit_trail_logging_to_database(tmp_path: Path):
    db_file = tmp_path / "audit.db"
    db = TaskDatabase(str(db_file))
    task_id = "task_audit_001"
    db.create_task(task_id, "Security Audit Trail Verification")

    sec = SecurityEngine(workspace_root=str(tmp_path))
    from prubeth.tools.execution import ToolExecutionEngine
    engine = ToolExecutionEngine(security=sec, db=db, current_task_id=task_id)

    # 1. Successful execution
    f = tmp_path / "sample.txt"
    f.write_text("logged content\n", encoding="utf-8")
    ok, out = engine.execute_tool("read_file", {"path": str(f)})
    assert ok is True

    # 2. Blocked execution (Security violation)
    bad_ok, bad_out = engine.execute_tool("read_file", {"path": "../escaped.txt"})
    assert bad_ok is False

    # Check database records
    logs = db.get_task_tool_executions(task_id)
    assert len(logs) >= 2
    # First execution was success (exit_code 0)
    assert logs[0]["tool_name"] == "read_file"
    assert logs[0]["exit_code"] == 0
    # Second execution was blocked (exit_code 403)
    assert logs[1]["tool_name"] == "read_file"
    assert logs[1]["exit_code"] == 403
