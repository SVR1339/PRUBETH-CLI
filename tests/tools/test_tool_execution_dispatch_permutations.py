"""Comprehensive execution engine dispatch, audit trail, and polyglot safety permutation tests."""

import pytest
from pathlib import Path

from prubeth.tools.execution import ToolExecutionEngine
from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase


@pytest.fixture
def dispatch_env(tmp_path: Path):
    db = TaskDatabase(str(tmp_path / "dispatch.db"))
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=True)
    engine = ToolExecutionEngine(security=sec, db=db, current_task_id="dispatch_task_01")
    return {"workspace": tmp_path, "db": db, "security": sec, "engine": engine}


def test_dispatch_copy_file(dispatch_env):
    engine = dispatch_env["engine"]
    ws = dispatch_env["workspace"]
    src = ws / "source.txt"
    src.write_text("data", encoding="utf-8")

    success, output = engine.execute_tool("copy_file", {"src": "source.txt", "dst": "dest.txt"})
    assert success is True
    assert (ws / "dest.txt").is_file()


def test_dispatch_move_file(dispatch_env):
    engine = dispatch_env["engine"]
    ws = dispatch_env["workspace"]
    src = ws / "old.txt"
    src.write_text("move me", encoding="utf-8")

    success, output = engine.execute_tool("move_file", {"src": "old.txt", "dst": "renamed.txt"})
    assert success is True
    assert not src.exists()
    assert (ws / "renamed.txt").is_file()


def test_dispatch_delete_file(dispatch_env):
    engine = dispatch_env["engine"]
    ws = dispatch_env["workspace"]
    f = ws / "trash.txt"
    f.write_text("bye", encoding="utf-8")

    success, output = engine.execute_tool("delete_file", {"path": "trash.txt"})
    assert success is True
    assert not f.exists()


def test_dispatch_glob_search(dispatch_env):
    engine = dispatch_env["engine"]
    ws = dispatch_env["workspace"]
    (ws / "doc1.md").write_text("doc", encoding="utf-8")
    (ws / "doc2.md").write_text("doc", encoding="utf-8")

    success, output = engine.execute_tool("glob_search", {"pattern": "*.md"})
    assert success is True
    assert "doc1.md" in output
    assert "doc2.md" in output


def test_dispatch_run_python(dispatch_env):
    engine = dispatch_env["engine"]
    success, output = engine.execute_tool("run_python", {"code": "print(100 + 200)"})
    assert success is True
    assert "300" in output


def test_dispatch_git_log_and_commit(dispatch_env):
    engine = dispatch_env["engine"]
    # Even if not a git repo, returns handled response without unhandled crash
    success, output = engine.execute_tool("git_log", {})
    assert isinstance(output, str)
    assert len(output) > 0


def test_dispatch_unknown_tool_fails_cleanly(dispatch_env):
    engine = dispatch_env["engine"]
    success, output = engine.execute_tool("unregistered_phantom_tool", {})
    assert success is False
    assert "Unknown tool" in output


def test_dispatch_malformed_mcp_tool_name(dispatch_env):
    engine = dispatch_env["engine"]
    success, output = engine.execute_tool("mcp_invalid", {})
    assert success is False
    assert "Malformed MCP tool name" in output


def test_dispatch_approval_callback_rejection(tmp_path: Path):
    db = TaskDatabase(str(tmp_path / "appr.db"))
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=False)
    engine = ToolExecutionEngine(security=sec, db=db, current_task_id="appr_01")

    # When approval_cb returns False, execution must be rejected
    def reject_cb(action_type, details):
        return False

    success, output = engine.execute_tool("write_file", {"path": "blocked.txt", "content": "x"}, approval_cb=reject_cb)
    assert success is False
    assert "rejected" in output.lower()
    assert not (tmp_path / "blocked.txt").exists()


def test_dispatch_approval_callback_approval(tmp_path: Path):
    db = TaskDatabase(str(tmp_path / "appr.db"))
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=False)
    engine = ToolExecutionEngine(security=sec, db=db, current_task_id="appr_02")

    def approve_cb(action_type, details):
        return True

    success, output = engine.execute_tool("write_file", {"path": "allowed.txt", "content": "approved content"}, approval_cb=approve_cb)
    assert success is True
    assert (tmp_path / "allowed.txt").read_text(encoding="utf-8") == "approved content"


def test_dispatch_polyglot_syntax_gate_rejection(dispatch_env):
    engine = dispatch_env["engine"]
    # Attempting to write invalid Python code raises pre-flight ValueError or error
    success, output = engine.execute_tool("write_file", {"path": "broken.py", "content": "def invalid_syntax(:"})
    assert success is False
    assert "Syntax Invariant Failed" in output or "syntax" in output.lower()


@pytest.mark.parametrize("file_ext,content", [
    ("script.js", "function run() { return 42; }"),
    ("types.ts", "interface Config { port: number; }"),
    ("data.json", '{"name": "prubeth", "version": "1.5.0"}'),
    ("page.html", "<!DOCTYPE html><html><body><h1>Title</h1></body></html>"),
    ("style.css", "body { margin: 0; padding: 0; }"),
])
def test_dispatch_polyglot_syntax_gate_valid_languages(dispatch_env, file_ext, content):
    engine = dispatch_env["engine"]
    ws = dispatch_env["workspace"]
    fname = f"sample.{file_ext}"

    success, output = engine.execute_tool("write_file", {"path": fname, "content": content})
    assert success is True
    assert (ws / fname).read_text(encoding="utf-8") == content


def test_dispatch_audit_trail_duration_recorded(dispatch_env):
    engine = dispatch_env["engine"]
    db = dispatch_env["db"]
    task_id = "dispatch_task_01"

    engine.execute_tool("read_file", {"path": "nonexistent.txt"})
    logs = db.get_task_tool_executions(task_id)
    assert len(logs) >= 1
    # Check that duration_ms is an integer >= 0
    assert isinstance(logs[-1]["duration_ms"], int)
    assert logs[-1]["duration_ms"] >= 0
