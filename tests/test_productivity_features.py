"""Unit and Integration Tests for PRUBETH Frontier Productivity Modules.

Validates:
1. Dynamic Reasoning Token Budgeting (/thinking)
2. Interactive Objective Checklist & Task HUD (/todo)
3. Codebase Architectural Topology Mapper (/map)
4. Polyglot Quality & Security Linter (/lint)
5. Autonomous Crash Debugger (/debug)
6. Permanent KV Cache Context Pinning (/pin)
7. Companion Unit Test Synthesizer (/test-gen)
"""

import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from prubeth.config.manager import ConfigManager
from prubeth.cli.commands import (
    handle_thinking_command,
    handle_todo_command,
    handle_map_command,
    handle_lint_command,
    handle_debug_command,
    handle_pin_command,
    handle_testgen_command
)
from prubeth.repository.topology import CodebaseTopologyMapper
from prubeth.security.linter import PolyglotQualityLinter
from prubeth.runtime.debugger import AutonomousCrashDebugger
from prubeth.persistence.pinned import PinnedContextManager

class MockController:
    def __init__(self, workspace_root: Path):
        self.workspace_root = str(workspace_root)
        self.security = MagicMock()
        self.db = MagicMock()

def test_thinking_command_budget_and_effort(tmp_path):
    """Verifies dynamic reasoning token budgeting and effort configuration."""
    cfg_mgr = ConfigManager()
    orig_budget = cfg_mgr.get("thinking_budget", 4096)
    orig_effort = cfg_mgr.get("reasoning_effort", "medium")

    try:
        # Default inspection
        handle_thinking_command([])

        # Set specific token budget
        handle_thinking_command(["8192"])
        assert cfg_mgr.get("thinking_budget") == 8192

        # Set reasoning effort
        handle_thinking_command(["effort", "high"])
        assert cfg_mgr.get("reasoning_effort") == "high"

        # Max mode
        handle_thinking_command(["max"])
        assert cfg_mgr.get("thinking_budget") == 16384
        assert cfg_mgr.get("reasoning_effort") == "high"

        # Disable / Fast mode
        handle_thinking_command(["off"])
        assert cfg_mgr.get("thinking_budget") == 0
        assert cfg_mgr.get("reasoning_effort") == "low"
    finally:
        cfg_mgr.set("thinking_budget", orig_budget)
        cfg_mgr.set("reasoning_effort", orig_effort)

def test_todo_command_lifecycle(tmp_path):
    """Verifies interactive workspace checklist lifecycle and TODO.md sync."""
    ctrl = MockController(tmp_path)

    # Empty list
    handle_todo_command(["list"], ctrl)

    # Add items
    handle_todo_command(["add", "Implement", "JWT", "auth"], ctrl)
    handle_todo_command(["add", "Add", "pytest", "suite"], ctrl)

    todo_file = tmp_path / ".prubeth" / "TODO.json"
    todo_md = tmp_path / "TODO.md"

    assert todo_file.exists()
    assert todo_md.exists()

    todos = json.loads(todo_file.read_text(encoding="utf-8"))
    assert len(todos) == 2
    assert todos[0]["title"] == "Implement JWT auth"
    assert todos[0]["status"] == "PENDING"

    # Start item 1
    handle_todo_command(["start", "1"], ctrl)
    todos = json.loads(todo_file.read_text(encoding="utf-8"))
    assert todos[0]["status"] == "IN_PROGRESS"

    # Complete item 1
    handle_todo_command(["done", "1"], ctrl)
    todos = json.loads(todo_file.read_text(encoding="utf-8"))
    assert todos[0]["status"] == "DONE"

    # Verify TODO.md content
    md_content = todo_md.read_text(encoding="utf-8")
    assert "[x] #1: Implement JWT auth" in md_content
    assert "[ ] #2: Add pytest suite" in md_content

    # Clear completed
    handle_todo_command(["clear"], ctrl)
    todos = json.loads(todo_file.read_text(encoding="utf-8"))
    assert len(todos) == 1
    assert todos[0]["id"] == 2

def test_codebase_topology_mapper(tmp_path):
    """Verifies structural AST scanning, entrypoint detection, and LOC metrics."""
    # Create sample files
    src = tmp_path / "src"
    src.mkdir(parents=True)
    main_py = src / "main.py"
    main_py.write_text("def main():\n    print('Hello World')\n", encoding="utf-8")

    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    test_py = tests / "test_main.py"
    test_py.write_text("def test_main():\n    assert True\n", encoding="utf-8")

    mapper = CodebaseTopologyMapper(workspace_root=tmp_path)
    scan = mapper.scan_workspace()

    assert scan["total_files"] == 2
    assert scan["test_file_count"] == 1
    assert scan["total_lines"] >= 4
    assert scan["languages"].get("Python") is not None

    # Render map
    mapper.render_map()
    ctrl = MockController(tmp_path)
    handle_map_command([], ctrl)

def test_polyglot_quality_linter_detection(tmp_path):
    """Verifies secret leak detection and security anti-pattern scanning."""
    # Create file with secrets and anti-patterns
    bad_file = tmp_path / "vulnerable.py"
    bad_file.write_text(
        'AWS_KEY = "AKIA1234567890ABCDEF"\n'
        'import subprocess\n'
        'subprocess.call("ls", shell=True)\n'
        'eval("2 + 2")\n',
        encoding="utf-8"
    )

    linter = PolyglotQualityLinter(workspace_root=tmp_path)
    issues = linter.audit_workspace()

    rules = [i["rule"] for i in issues]
    assert "AWS Access Key ID" in rules
    assert "Unsafe Subprocess Shell Execution" in rules
    assert "Dynamic Code Execution (eval/exec)" in rules

    # Verify report rendering
    code = linter.render_report()
    assert code == 1

def test_crash_debugger_frame_parsing():
    """Verifies call stack parsing across Python and Rust tracebacks."""
    debugger = AutonomousCrashDebugger()

    py_trace = (
        'Traceback (most recent call last):\n'
        '  File "src/calc.py", line 42, in divide\n'
        '    return a / b\n'
        'ZeroDivisionError: division by zero\n'
    )
    frame = debugger._parse_failure_frame(py_trace)
    assert frame["file"] == "src/calc.py"
    assert frame["line"] == 42
    assert frame["function"] == "divide"
    assert frame["type"] == "python"

    rust_trace = (
        "thread 'main' panicked at 'index out of bounds', src/lib.rs:88:14\n"
    )
    rust_frame = debugger._parse_failure_frame(rust_trace)
    assert rust_frame["file"] == "src/lib.rs"
    assert rust_frame["line"] == 88
    assert rust_frame["type"] == "rust"

def test_pinned_context_manager(tmp_path):
    """Verifies permanent prompt KV cache context pinning and retrieval."""
    test_file = tmp_path / "contracts.py"
    test_file.write_text("class UserContract:\n    id: int\n", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    assert mgr.load_pinned() == []

    # Pin file
    ok = mgr.pin(str(test_file))
    assert ok is True
    assert len(mgr.load_pinned()) == 1

    # Attachments
    att = mgr.get_context_attachments()
    assert len(att) == 1
    assert "contracts.py" in att[0]["label"]
    assert "class UserContract" in att[0]["content"]

    # Render list
    mgr.render_list()

    # CLI handler
    ctrl = MockController(tmp_path)
    handle_pin_command([], ctrl)
    handle_pin_command(["unpin", "contracts.py"], ctrl)
    assert mgr.load_pinned() == []

def test_testgen_command_safeguards(tmp_path):
    """Verifies companion test generator argument handling and file checks."""
    ctrl = MockController(tmp_path)

    # Missing arg
    handle_testgen_command([], ctrl)

    # Nonexistent file
    handle_testgen_command(["nonexistent.py"], ctrl)
