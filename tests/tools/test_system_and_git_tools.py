"""Tests for PRUBETH System Execution & Git Core Tools (RunShell, RunPython, GitStatus, GitDiff, GitCommit, GitLog)."""

import os
import sys
import subprocess
import pytest
from pathlib import Path

from prubeth.tools.core.run_shell import RunShellTool
from prubeth.tools.core.run_python import RunPythonTool
from prubeth.tools.core.git_status import GitStatusTool
from prubeth.tools.core.git_diff import GitDiffTool
from prubeth.tools.core.git_commit import GitCommitTool
from prubeth.tools.core.git_log import GitLogTool
from prubeth.tools.base import ToolClearanceLevel


class MockContext:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root


# =========================================================================
# RunShellTool Tests
# =========================================================================

def test_run_shell_tool_metadata():
    tool = RunShellTool()
    assert tool.name == "run_shell"
    assert tool.clearance_level == ToolClearanceLevel.SYSTEM_EXECUTION


def test_run_shell_tool_executes_simple_command():
    tool = RunShellTool()
    res = tool.execute({"command": f'"{sys.executable}" -c "print(12345)"'})
    assert res.success is True
    assert res.exit_code == 0
    assert "12345" in res.output


def test_run_shell_tool_captures_stderr():
    tool = RunShellTool()
    res = tool.execute({"command": f'"{sys.executable}" -c "import sys; sys.stderr.write(\'err_token\\n\')\''})
    assert "err_token" in res.output


def test_run_shell_tool_dangerous_rm_rf():
    tool = RunShellTool()
    res = tool.execute({"command": "rm -rf /"})
    assert res.success is False
    assert res.exit_code == 403
    assert "Security Violation" in res.output


def test_run_shell_tool_dangerous_fork_bomb():
    tool = RunShellTool()
    res = tool.execute({"command": ":(){ :|:& };:"})
    assert res.success is False
    assert res.exit_code == 403
    assert "Security Violation" in res.output


def test_run_shell_tool_dangerous_mkfs():
    tool = RunShellTool()
    res = tool.execute({"command": "mkfs /dev/sda1"})
    assert res.success is False
    assert res.exit_code == 403
    assert "Security Violation" in res.output


def test_run_shell_tool_dangerous_format():
    tool = RunShellTool()
    res = tool.execute({"command": "format C: /fs:NTFS"})
    assert res.success is False
    assert res.exit_code == 403
    assert "Security Violation" in res.output


def test_run_shell_tool_timeout():
    tool = RunShellTool()
    # 1 second timeout running 5 second sleep
    res = tool.execute({
        "command": f'"{sys.executable}" -c "import time; time.sleep(5)"',
        "timeout": 1
    })
    assert res.success is False
    assert res.exit_code == 124
    assert "timed out" in res.output.lower()


def test_run_shell_tool_custom_cwd(tmp_path: Path):
    sub = tmp_path / "subdir"
    sub.mkdir()

    tool = RunShellTool()
    ctx = MockContext(workspace_root=tmp_path)
    res = tool.execute({
        "command": f'"{sys.executable}" -c "import os; print(os.path.basename(os.getcwd()))"',
        "cwd": "subdir"
    }, context=ctx)
    assert res.success is True
    assert "subdir" in res.output


def test_run_shell_tool_empty_command():
    tool = RunShellTool()
    res = tool.execute({"command": ""})
    assert res.success is False
    assert res.exit_code == 1


# =========================================================================
# RunPythonTool Tests
# =========================================================================

def test_run_python_tool_metadata():
    tool = RunPythonTool()
    assert tool.name == "run_python"
    assert tool.clearance_level == ToolClearanceLevel.SYSTEM_EXECUTION


def test_run_python_tool_basic_execution():
    tool = RunPythonTool()
    res = tool.execute({"code": "print(sum([1, 2, 3, 4]))"})
    assert res.success is True
    assert res.exit_code == 0
    assert "10" in res.output


def test_run_python_tool_exception_handling():
    tool = RunPythonTool()
    res = tool.execute({"code": "raise ValueError('custom_error_code')"})
    assert res.success is False
    assert res.exit_code != 0
    assert "ValueError" in res.output
    assert "custom_error_code" in res.output


def test_run_python_tool_timeout():
    tool = RunPythonTool()
    res = tool.execute({"code": "import time; time.sleep(5)", "timeout": 1})
    assert res.success is False
    assert res.exit_code == 124
    assert "timed out" in res.output.lower()


def test_run_python_tool_empty_code():
    tool = RunPythonTool()
    res = tool.execute({"code": ""})
    assert res.success is False
    assert res.exit_code == 1


# =========================================================================
# Git Tools (GitStatus, GitDiff, GitCommit, GitLog) Tests
# =========================================================================

def test_git_status_tool_not_a_repo(tmp_path: Path):
    ctx = MockContext(workspace_root=tmp_path)
    tool = GitStatusTool()
    res = tool.execute({}, context=ctx)
    # When not a git repository, returns graceful notice
    assert ("not a Git repository" in res.output) or res.success is False


def test_git_diff_tool_not_a_repo(tmp_path: Path):
    ctx = MockContext(workspace_root=tmp_path)
    tool = GitDiffTool()
    res = tool.execute({"staged": True}, context=ctx)
    assert ("not a Git repository" in res.output) or res.success is False


def test_git_commit_tool_validation():
    tool = GitCommitTool()
    res = tool.execute({})  # missing message
    assert res.success is False
    assert res.exit_code == 1

    res2 = tool.execute({"message": ""})
    assert res2.success is False
    assert res2.exit_code == 1


def test_git_log_tool_not_a_repo(tmp_path: Path):
    ctx = MockContext(workspace_root=tmp_path)
    tool = GitLogTool()
    res = tool.execute({"max_count": 5}, context=ctx)
    assert ("not a Git repository" in res.output) or res.success is False


def test_git_tools_in_real_repo(tmp_path: Path):
    """Initializes a temporary git repository and tests GitStatus, GitDiff, GitCommit, GitLog."""
    import shutil
    if not shutil.which("git"):
        pytest.skip("Git CLI binary not available in environment.")
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception:
        pytest.skip("Git CLI binary not available in environment.")

    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), stdout=subprocess.PIPE, check=True)
    subprocess.run(["git", "config", "user.name", "Prubeth Tester"], cwd=str(repo_dir), stdout=subprocess.PIPE, check=True)
    subprocess.run(["git", "config", "user.email", "test@prubeth.ai"], cwd=str(repo_dir), stdout=subprocess.PIPE, check=True)

    ctx = MockContext(workspace_root=repo_dir)

    # 1. Create file and check git_status
    (repo_dir / "file.txt").write_text("v1\n", encoding="utf-8")
    status_tool = GitStatusTool()
    res_status = status_tool.execute({}, context=ctx)
    assert res_status.success is True
    assert "file.txt" in res_status.output

    # 2. Commit file
    commit_tool = GitCommitTool()
    res_commit = commit_tool.execute({"message": "Initial commit"}, context=ctx)
    assert res_commit.success is True
    assert "Initial commit" in res_commit.output

    # 3. Check git_log
    log_tool = GitLogTool()
    res_log = log_tool.execute({"max_count": 5}, context=ctx)
    assert res_log.success is True
    assert "Initial commit" in res_log.output

    # 4. Modify file and check git_diff
    (repo_dir / "file.txt").write_text("v2\n", encoding="utf-8")
    diff_tool = GitDiffTool()
    res_diff = diff_tool.execute({}, context=ctx)
    assert res_diff.success is True
    assert "-v1" in res_diff.output or "+v2" in res_diff.output
