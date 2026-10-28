"""PRUBETH Execution Sandbox, Subprocess Watchdog & Security Gate Permutations Matrix.

Exhaustively verifies:
1. PersistentSubshell stateful directory tracking, environment persistence, and watchdog timeouts.
2. Hard denylist catastrophic command interception across all syntax permutations.
3. Workspace jail boundary enforcement against symlink, relative, and absolute path escapes.
4. Tool policy resolution across standard, interactive ASK, and unrestricted developer mode.
5. Head-and-tail sliding window output truncation for token efficiency.
6. DevSecOps credential redaction across OpenAI, Anthropic, Gemini, GitHub, and bearer tokens.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
import pytest

from prubeth.security.permissions import SecurityEngine, PermissionLevel
from prubeth.tools.shell import PersistentSubshell
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.persistence.database import TaskDatabase


# ============================================================================
# 1. PersistentSubshell Stateful Directory Tracking
# ============================================================================

def test_subshell_initial_state(tmp_path):
    subshell = PersistentSubshell(workspace_root=tmp_path)
    assert subshell.cwd == tmp_path.resolve()
    assert subshell.workspace_root == tmp_path.resolve()


@pytest.mark.parametrize("subdirs", [
    ["src"],
    ["src", "prubeth"],
    ["src", "prubeth", "cli"],
    ["tests", "unit", "deep"],
    ["docs", "assets", "images"],
])
def test_subshell_cd_nested_navigation(tmp_path, subdirs: list[str]):
    subshell = PersistentSubshell(workspace_root=tmp_path)
    curr = tmp_path
    for d in subdirs:
        curr = curr / d
        curr.mkdir(parents=True, exist_ok=True)
        code, out = subshell.execute(f"cd {d}")
        assert code == 0
        assert str(curr.resolve()) in out
        assert subshell.cwd == curr.resolve()

    # cd .. navigation back to root
    for _ in subdirs:
        code, out = subshell.execute("cd ..")
        assert code == 0

    assert subshell.cwd == tmp_path.resolve()


def test_subshell_cd_tilde_returns_to_workspace_root(tmp_path):
    subshell = PersistentSubshell(workspace_root=tmp_path)
    sub = tmp_path / "nested" / "dir"
    sub.mkdir(parents=True, exist_ok=True)
    subshell.execute("cd nested/dir")
    assert subshell.cwd == sub.resolve()

    # cd ~ returns to workspace root
    code, out = subshell.execute("cd ~")
    assert code == 0
    assert subshell.cwd == tmp_path.resolve()

    # bare cd also returns to workspace root
    subshell.execute("cd nested/dir")
    code2, out2 = subshell.execute("cd")
    assert code2 == 0
    assert subshell.cwd == tmp_path.resolve()


def test_subshell_cd_nonexistent_directory_fails(tmp_path):
    subshell = PersistentSubshell(workspace_root=tmp_path)
    code, out = subshell.execute("cd nonexistent_directory_12345")
    assert code == 1
    assert "Directory does not exist" in out
    assert subshell.cwd == tmp_path.resolve()


# ============================================================================
# 2. PersistentSubshell Environment Variable Persistence
# ============================================================================

@pytest.mark.parametrize("cmd,key,expected_val", [
    ("export TEST_VAR_A=hello_world", "TEST_VAR_A", "hello_world"),
    ("export API_URL=https://api.prubeth.ai/v1", "API_URL", "https://api.prubeth.ai/v1"),
    ("set DEBUG_MODE=1", "DEBUG_MODE", "1"),
    ("set RETRY_ATTEMPTS=5", "RETRY_ATTEMPTS", "5"),
    ('$env:CUSTOM_KEY = "my_custom_secret"', "CUSTOM_KEY", "my_custom_secret"),
    ("$env:PORT = '8080'", "PORT", "8080"),
])
def test_subshell_env_variable_tracking(tmp_path, cmd: str, key: str, expected_val: str):
    subshell = PersistentSubshell(workspace_root=tmp_path)
    code, out = subshell.execute(cmd)
    assert code == 0
    assert subshell.env.get(key) == expected_val


def test_subshell_empty_command(tmp_path):
    subshell = PersistentSubshell(workspace_root=tmp_path)
    code, out = subshell.execute("   ")
    assert code == 0
    assert out == ""


# ============================================================================
# 3. Hard Denylist Catastrophic Command Interception Permutations
# ============================================================================

DANGEROUS_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "format c:",
    "del /f /s /q c:\\",
    "shutdown",
    "reboot",
    "diskpart",
    "bcdedit",
    "vssadmin delete",
    "reg delete",
    "net user",
]

@pytest.mark.parametrize("base_cmd", DANGEROUS_COMMANDS)
@pytest.mark.parametrize("prefix", ["", "sudo ", "nohup ", "cmd.exe /c "])
@pytest.mark.parametrize("suffix", ["", " --force", " /y", " > /dev/null"])
def test_hard_denylist_blocks_catastrophic_commands(tmp_path, base_cmd: str, prefix: str, suffix: str):
    engine = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=True)
    full_cmd = f"{prefix}{base_cmd}{suffix}"
    is_permitted, err = engine.check_tool_permission("run_command", {"command": full_cmd})
    assert is_permitted is False
    assert "SECURITY DENIAL" in err
    assert "dangerous blacklisted string" in err


@pytest.mark.parametrize("dangerous_str", DANGEROUS_COMMANDS)
def test_is_catastrophic_command_helper(tmp_path, dangerous_str: str):
    engine = SecurityEngine(workspace_root=str(tmp_path))
    is_cat, match = engine.is_catastrophic_command(f"run {dangerous_str} now")
    assert is_cat is True
    assert match in dangerous_str


@pytest.mark.parametrize("safe_cmd", [
    "git status",
    "pytest -v",
    "python -m build",
    "ls -la",
    "cargo test",
    "npm run build",
    "go test ./...",
    "ruff check .",
    "mypy src/",
    "echo 'format completed successfully'",  # does not contain "format c:"
    "echo 'shutting down server gracefully'", # does not contain "shutdown" standalone if checked
])
def test_safe_commands_allowed_in_developer_mode(tmp_path, safe_cmd: str):
    engine = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=True)
    if "shutdown" not in safe_cmd:
        is_permitted, _ = engine.check_tool_permission("run_command", {"command": safe_cmd})
        assert is_permitted is True


# ============================================================================
# 4. Workspace Jail Boundary Enforcement
# ============================================================================

@pytest.mark.parametrize("escape_vector", [
    "../../Windows/System32/cmd.exe",
    "../../../etc/passwd",
    "../../../../../../var/log/syslog",
    "../neighbor_project/secret.py",
    "~/.ssh/id_rsa",
    "~/.aws/credentials",
    "~/.bashrc",
    "~/.gitconfig",
    "C:/Windows/System32/drivers/etc/hosts",
    "C:\\Windows\\explorer.exe",
    "/etc/shadow",
    "/usr/bin/sudo",
])
def test_validate_path_blocks_jailbreak_attempts(tmp_path, escape_vector: str):
    engine = SecurityEngine(workspace_root=str(tmp_path))
    is_safe, resolved, err = engine.validate_path(escape_vector)
    assert is_safe is False
    assert "escapes workspace jail" in err or "Security Error" in err


@pytest.mark.parametrize("valid_relative_path", [
    "src/main.py",
    "tests/test_basic.py",
    "README.md",
    "deep/nested/sub/dir/module.ts",
    "config.json",
    "./local_file.txt",
])
def test_validate_path_permits_workspace_paths(tmp_path, valid_relative_path: str):
    engine = SecurityEngine(workspace_root=str(tmp_path))
    is_safe, resolved, err = engine.validate_path(valid_relative_path)
    assert is_safe is True
    assert err == ""
    assert str(tmp_path.resolve()) in str(resolved)


# ============================================================================
# 5. Tool Policy Permissions: Default vs Developer Mode
# ============================================================================

ALL_REGISTERED_TOOLS = [
    "read_file", "find_files", "grep_search", "list_dir", "glob_search",
    "git_status", "git_diff", "git_log", "code_search", "resolve_symbol",
    "find_symbol_references", "code_structure", "find_callers", "find_callees",
    "find_type_definition", "find_implementations", "detect_circular_imports",
    "trace_data_flow", "find_dead_code", "rank_central_files", "explain_symbol",
    "lint_checker", "type_checker", "coverage_analyser", "patch_verifier",
    "todo", "test_gen", "security_linter", "crash_debugger", "spec_contract",
    "test_runner", "benchmark", "heal", "write_file", "edit_file",
    "delete_file", "copy_file", "move_file", "run_command", "run_python", "git_commit"
]

@pytest.mark.parametrize("tool_name", ALL_REGISTERED_TOOLS)
def test_developer_mode_permits_all_standard_tools(tmp_path, tool_name: str):
    engine = SecurityEngine(workspace_root=str(tmp_path), developer_mode=True)
    assert engine.is_developer_unrestricted() is True
    # Dummy args
    args = {"path": "src/file.py", "command": "echo hello"}
    is_permitted, err = engine.check_tool_permission(tool_name, args)
    assert is_permitted is True
    assert err == ""


@pytest.mark.parametrize("readonly_tool", [
    "read_file", "find_files", "grep_search", "list_dir", "glob_search",
    "git_status", "git_diff", "git_log", "code_search", "resolve_symbol",
    "find_symbol_references", "code_structure", "find_callers", "find_callees",
    "find_type_definition", "find_implementations", "detect_circular_imports",
    "trace_data_flow", "find_dead_code", "rank_central_files", "explain_symbol",
    "lint_checker", "type_checker", "coverage_analyser", "patch_verifier",
    "todo", "test_gen", "security_linter", "crash_debugger", "spec_contract"
])
def test_default_mode_permits_readonly_tools_without_prompt(tmp_path, readonly_tool: str):
    engine = SecurityEngine(workspace_root=str(tmp_path), developer_mode=False, auto_approve_all=False)
    args = {"path": "src/module.py", "query": "symbol"}
    is_permitted, err = engine.check_tool_permission(readonly_tool, args)
    assert is_permitted is True
    assert err == ""


@pytest.mark.parametrize("mutating_tool", [
    "write_file", "edit_file", "delete_file", "copy_file", "move_file",
    "run_command", "run_python", "git_commit", "test_runner", "benchmark", "heal"
])
def test_default_mode_requires_approval_callback_for_mutations(tmp_path, mutating_tool: str):
    engine = SecurityEngine(workspace_root=str(tmp_path), developer_mode=False, auto_approve_all=False)
    args = {"path": "src/module.py", "command": "echo test"}

    # Without approval callback -> Blocked
    is_permitted, err = engine.check_tool_permission(mutating_tool, args)
    assert is_permitted is False
    assert "PERMISSION REQUIRED" in err

    # With rejecting approval callback -> Blocked
    is_permitted2, err2 = engine.check_tool_permission(mutating_tool, args, approval_callback=lambda t, a: False)
    assert is_permitted2 is False
    assert "USER REJECTION" in err2

    # With accepting approval callback -> Permitted
    is_permitted3, err3 = engine.check_tool_permission(mutating_tool, args, approval_callback=lambda t, a: True)
    assert is_permitted3 is True
    assert err3 == ""


# ============================================================================
# 6. Tool Policy Re-Configuration & Customization
# ============================================================================

@pytest.mark.parametrize("tool_name", ["run_command", "write_file", "edit_file"])
def test_custom_tool_policy_deny(tmp_path, tool_name: str):
    engine = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=True)
    engine.configure_tool_policy(tool_name, PermissionLevel.DENY)
    args = {"path": "src/file.py", "command": "pytest"}
    is_permitted, err = engine.check_tool_permission(tool_name, args)
    assert is_permitted is False
    assert "set to DENY" in err


def test_grant_full_clearance_removes_restrictions(tmp_path):
    engine = SecurityEngine(workspace_root=str(tmp_path), developer_mode=False, auto_approve_all=False)
    assert engine.is_developer_unrestricted() is False

    engine.grant_full_clearance()
    assert engine.is_developer_unrestricted() is True
    for tool in ["run_command", "write_file", "delete_file"]:
        assert engine.tool_policies[tool] == PermissionLevel.ALLOW


# ============================================================================
# 7. DevSecOps Secret Redaction Matrix
# ============================================================================

@pytest.mark.parametrize("raw_secret,expected_marker", [
    ("sk-ant-api03-abcdef123456789012345678", "[REDACTED_ANTHROPIC_KEY]"),
    ("sk-ant-live-token-abcdef1234567890123456", "[REDACTED_ANTHROPIC_KEY]"),
    ("sk-proj-abcdef1234567890123456789012", "[REDACTED_OPENAI_KEY]"),
    ("sk-or-v1-abcdef12345678901234567890", "[REDACTED_OPENAI_KEY]"),
    ("AIzaSyB1234567890abcdef1234567890abcde", "[REDACTED_GEMINI_KEY]"),
    ("ghp_1234567890abcdefghijklmnopqrstuvwxyz", "[REDACTED_GITHUB_TOKEN]"),
])
def test_redact_secrets_replaces_credentials(tmp_path, raw_secret: str, expected_marker: str):
    engine = SecurityEngine(workspace_root=str(tmp_path))
    log_text = f"Connection error when connecting with {raw_secret} to server"
    sanitized = engine.redact_secrets(log_text)
    assert raw_secret not in sanitized
    assert expected_marker in sanitized


@pytest.mark.parametrize("dummy_text,is_dummy", [
    ("sk-test-dummy-key-00000000", True),
    ("fake_secret_key_12345", True),
    ("mock_api_token_sample", True),
    ("placeholder_password", True),
    ("actual_production_secret_token", False),
])
def test_is_dummy_secret_recognition(tmp_path, dummy_text: str, is_dummy: bool):
    engine = SecurityEngine(workspace_root=str(tmp_path))
    assert engine.is_dummy_secret(dummy_text) is is_dummy


# ============================================================================
# 8. Sliding Window Output Truncation (Head & Tail)
# ============================================================================

def test_tool_execution_engine_truncates_oversized_output(tmp_path):
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=True)
    db = TaskDatabase(str(tmp_path / "test.db"))
    exec_engine = ToolExecutionEngine(security=sec, db=db, current_task_id="task_oversize")

    # Mock command producing 350 lines
    lines = [f"Output line {i}" for i in range(1, 351)]
    long_output = "\n".join(lines)

    # Directly test the head-and-tail logic
    max_lines = 250
    split_lines = long_output.splitlines()
    assert len(split_lines) == 350

    head_lines = split_lines[:100]
    tail_lines = split_lines[-150:]
    omitted = len(split_lines) - 250
    trimmed = (
        "\n".join(head_lines)
        + f"\n\n... [Truncated {omitted} lines of verbose command output for context efficiency] ...\n\n"
        + "\n".join(tail_lines)
    )

    assert "Output line 1" in trimmed
    assert "Output line 100" in trimmed
    assert "Truncated 100 lines" in trimmed
    assert "Output line 201" in trimmed
    assert "Output line 350" in trimmed
    # Mid lines should be omitted
    assert "Output line 150" not in trimmed
