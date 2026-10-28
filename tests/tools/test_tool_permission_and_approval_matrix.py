"""Exhaustive permission, clearance, and interactive approval matrix tests across all 15 core tools."""

import pytest
from typing import Dict, Any

from prubeth.tools.core import ALL_CORE_TOOLS
from prubeth.tools.base import ToolClearanceLevel
from prubeth.security.permissions import SecurityEngine, PermissionLevel


# =========================================================================
# Read-Only Tools Always Permitted Without Prompts
# =========================================================================

READ_ONLY_TOOLS = [t for t in ALL_CORE_TOOLS if t.clearance_level == ToolClearanceLevel.READ_ONLY]
MUTATION_AND_EXEC_TOOLS = [t for t in ALL_CORE_TOOLS if t.clearance_level in (ToolClearanceLevel.WORKSPACE_MUTATION, ToolClearanceLevel.SYSTEM_EXECUTION)]


@pytest.mark.parametrize("tool_cls", READ_ONLY_TOOLS)
def test_read_only_tools_never_require_interactive_approval(tmp_path, tool_cls):
    """Invariant: Read-only inspection tools must never interrupt developers with approval prompts."""
    # Even when auto_approve_all is False and approval_cb is None:
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=False)
    tool_name = tool_cls.name

    # Check permission with no callback provided
    is_permitted, err = sec.check_tool_permission(tool_name, {"path": "clean.txt"}, approval_callback=None)
    assert is_permitted is True, f"Read-only tool '{tool_name}' was blocked: {err}"
    assert err == ""


@pytest.mark.parametrize("tool_cls", MUTATION_AND_EXEC_TOOLS)
def test_mutation_tools_allowed_when_auto_approve_enabled(tmp_path, tool_cls):
    """When auto_approve_all is True, mutation and execution tools proceed without prompt."""
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=True)
    tool_name = tool_cls.name

    is_permitted, err = sec.check_tool_permission(tool_name, {"path": "safe.py", "command": "echo hi"}, approval_callback=None)
    assert is_permitted is True, f"Tool '{tool_name}' was blocked under auto_approve_all: {err}"
    assert err == ""


@pytest.mark.parametrize("tool_cls", MUTATION_AND_EXEC_TOOLS)
def test_mutation_tools_ask_and_approve_via_callback(tmp_path, tool_cls):
    """When auto_approve_all is False, approval callback receives tool name and can approve."""
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=False)
    tool_name = tool_cls.name

    approved_events = []
    def approval_cb(t_name, args):
        approved_events.append(t_name)
        return True

    is_permitted, err = sec.check_tool_permission(tool_name, {"path": "safe.py", "command": "echo hi"}, approval_callback=approval_cb)
    assert is_permitted is True
    assert tool_name in approved_events


@pytest.mark.parametrize("tool_cls", MUTATION_AND_EXEC_TOOLS)
def test_mutation_tools_rejected_when_callback_denies(tmp_path, tool_cls):
    """When developer rejects execution via callback, check_tool_permission returns False."""
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=False)
    tool_name = tool_cls.name

    def deny_cb(t_name, args):
        return False

    is_permitted, err = sec.check_tool_permission(tool_name, {"path": "safe.py", "command": "echo hi"}, approval_callback=deny_cb)
    assert is_permitted is False
    assert "USER REJECTION" in err or "rejected" in err.lower()


@pytest.mark.parametrize("tool_cls", MUTATION_AND_EXEC_TOOLS)
def test_mutation_tools_require_permission_if_no_callback(tmp_path, tool_cls):
    """When auto_approve_all is False and no callback is passed, permission is denied safely."""
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=False)
    tool_name = tool_cls.name

    is_permitted, err = sec.check_tool_permission(tool_name, {"path": "safe.py", "command": "echo hi"}, approval_callback=None)
    assert is_permitted is False
    assert "PERMISSION REQUIRED" in err or "requires approval" in err.lower()
