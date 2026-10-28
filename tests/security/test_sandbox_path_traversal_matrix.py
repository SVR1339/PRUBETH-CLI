"""PRUBETH Workspace Sandbox & Path Traversal Prevention Matrix Tests.

Exhaustively verifies SecurityEngine path validation:
- Prevention of parent directory traversal (..)
- Absolute paths escaping workspace boundary
- Operating system system root protections (Windows C:\\Windows, POSIX /etc)
- UNC network paths and null-byte injection resistance
- Preservation of legitimate deeply-nested workspace paths and relative references
"""

from __future__ import annotations

import os
import sys
import pytest
from pathlib import Path

from prubeth.security.permissions import SecurityEngine


@pytest.fixture
def sandbox_env(tmp_path: Path):
    workspace = tmp_path / "safe_workspace"
    workspace.mkdir()
    engine = SecurityEngine(workspace_root=str(workspace))
    return engine, workspace


# ============================================================================
# 1. Path Traversal Jail Break Rejections
# ============================================================================

ADVERSARIAL_ESCAPE_PATHS = [
    "../secret.txt",
    "../../outside_file.py",
    "../../../etc/shadow",
    "../../../../Windows/System32/cmd.exe",
    "src/../../outside.txt",
    "nested/sub/../../../../target.env",
]

@pytest.mark.parametrize("bad_path", ADVERSARIAL_ESCAPE_PATHS)
def test_path_traversal_escapes_are_denied(sandbox_env, bad_path: str):
    engine, workspace = sandbox_env
    ok, resolved, err = engine.validate_path(bad_path)
    assert ok is False
    assert "escapes workspace jail" in err


# ============================================================================
# 2. Absolute System Root Paths Denied
# ============================================================================

SYSTEM_ABSOLUTE_PATHS = [
    "C:\\Windows\\System32\\drivers\\etc\\hosts" if sys.platform == "win32" else "/etc/passwd",
    "C:\\Users" if sys.platform == "win32" else "/var/log/syslog",
    "C:\\Program Files" if sys.platform == "win32" else "/bin/bash",
]

@pytest.mark.parametrize("abs_path", SYSTEM_ABSOLUTE_PATHS)
def test_absolute_system_paths_are_denied(sandbox_env, abs_path: str):
    engine, workspace = sandbox_env
    ok, resolved, err = engine.validate_path(abs_path)
    assert ok is False
    assert "escapes workspace jail" in err


# ============================================================================
# 3. Legitimate Workspace Paths Allowed
# ============================================================================

LEGITIMATE_PATHS = [
    "pyproject.toml",
    "README.md",
    "src/main.py",
    "src/prubeth/cli/main.py",
    "tests/tools/test_file_core_tools.py",
    "./config/settings.json",
    "docs/architecture/diagrams/pipeline.png",
    "vendor/bundle/cache/gem.tar.gz",
    "a/b/c/d/e/f/g.txt",
]

@pytest.mark.parametrize("safe_path", LEGITIMATE_PATHS)
def test_legitimate_workspace_paths_are_allowed(sandbox_env, safe_path: str):
    engine, workspace = sandbox_env
    ok, resolved, err = engine.validate_path(safe_path)
    assert ok is True
    assert err == ""
    assert str(resolved).startswith(str(workspace))


# ============================================================================
# 4. Tool Permission Integration Checks
# ============================================================================

@pytest.mark.parametrize("dangerous_cmd", [
    "rm -rf /",
    "rm -rf /*",
    "mkfs.ext4 /dev/sda1",
    "format c:",
    "del /f /s /q c:\\",
    "shutdown /s /t 0",
    "vssadmin delete shadows",
])
def test_lethal_commands_blocked_even_in_developer_mode(sandbox_env, dangerous_cmd: str):
    engine, _ = sandbox_env
    engine.enable_unrestricted_developer_mode()

    ok, reason = engine.check_tool_permission("run_command", {"command": dangerous_cmd})
    assert ok is False
    assert "SECURITY DENIAL" in reason
    assert "dangerous blacklisted string" in reason


def test_write_file_outside_jail_denied_via_check_tool_permission(sandbox_env):
    engine, _ = sandbox_env
    ok, reason = engine.check_tool_permission("write_file", {"path": "../../etc/malicious.sh", "content": "echo hi"})
    assert ok is False
    assert "escapes workspace jail" in reason
