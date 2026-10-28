"""Tests for PRUBETH Search Core Tools (GrepSearchTool, GlobSearchTool)."""

import os
import pytest
from pathlib import Path

from prubeth.tools.core.grep_search import GrepSearchTool
from prubeth.tools.core.glob_search import GlobSearchTool
from prubeth.tools.base import ToolClearanceLevel


class MockContext:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root


# =========================================================================
# GrepSearchTool Tests
# =========================================================================

def test_grep_search_tool_metadata():
    tool = GrepSearchTool()
    assert tool.name == "grep_search"
    assert tool.clearance_level == ToolClearanceLevel.READ_ONLY
    assert any(p.name == "query" for p in tool.parameters)


def test_grep_search_tool_basic(tmp_path: Path):
    (tmp_path / "a.py").write_text("def hello_world():\n    return 'hello'\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("say hello to everyone\n", encoding="utf-8")
    (tmp_path / "c.md").write_text("No matches here\n", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GrepSearchTool()
    res = tool.execute({"query": "hello"}, context=ctx)
    assert res.success is True
    assert res.exit_code == 0
    assert "hello_world" in res.output
    assert "say hello to everyone" in res.output
    assert res.metadata["matches"] >= 2


def test_grep_search_tool_case_sensitive(tmp_path: Path):
    (tmp_path / "case.txt").write_text("PRUBETH\nprubeth\nPrubeth\n", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GrepSearchTool()

    # Case-sensitive
    res1 = tool.execute({"query": "PRUBETH", "case_sensitive": True}, context=ctx)
    assert res1.success is True
    assert res1.metadata["matches"] == 1

    # Case-insensitive
    res2 = tool.execute({"query": "PRUBETH", "case_sensitive": False}, context=ctx)
    assert res2.success is True
    assert res2.metadata["matches"] == 3


def test_grep_search_tool_regex(tmp_path: Path):
    (tmp_path / "tokens.txt").write_text("token_123 = True\ntoken_abc = False\nother = None\n", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GrepSearchTool()
    res = tool.execute({"query": r"token_\d+"}, context=ctx)
    assert res.success is True
    assert res.metadata["matches"] == 1
    assert "token_123" in res.output
    assert "token_abc" not in res.output


def test_grep_search_tool_invalid_regex_fallback_to_literal(tmp_path: Path):
    (tmp_path / "symbols.txt").write_text("cost is [unclosed regex(\nnormal\n", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GrepSearchTool()
    # Invalid regex syntax
    res = tool.execute({"query": "[unclosed regex("}, context=ctx)
    assert res.success is True
    assert res.metadata["matches"] == 1
    assert "[unclosed regex(" in res.output


def test_grep_search_tool_file_pattern_filter(tmp_path: Path):
    (tmp_path / "match.py").write_text("target_word in py\n", encoding="utf-8")
    (tmp_path / "match.js").write_text("target_word in js\n", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GrepSearchTool()
    res = tool.execute({"query": "target_word", "file_pattern": "*.py"}, context=ctx)
    assert res.success is True
    assert "target_word in py" in res.output
    assert "target_word in js" not in res.output


def test_grep_search_tool_max_results(tmp_path: Path):
    lines = "\n".join([f"hit item {i}" for i in range(50)]) + "\n"
    (tmp_path / "many.txt").write_text(lines, encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GrepSearchTool()
    res = tool.execute({"query": "hit item", "max_results": 5}, context=ctx)
    assert res.success is True
    assert res.metadata["truncated"] is True
    assert "top 5" in res.output


def test_grep_search_tool_single_file_search(tmp_path: Path):
    f = tmp_path / "single.txt"
    f.write_text("isolated line\n", encoding="utf-8")

    tool = GrepSearchTool()
    res = tool.execute({"query": "isolated", "path": str(f)})
    assert res.success is True
    assert "isolated line" in res.output


def test_grep_search_tool_not_found(tmp_path: Path):
    tool = GrepSearchTool()
    res = tool.execute({"query": "x", "path": str(tmp_path / "missing")})
    assert res.success is False
    assert res.exit_code == 404


def test_grep_search_tool_empty_query():
    tool = GrepSearchTool()
    res = tool.execute({"query": ""})
    assert res.success is False
    assert res.exit_code == 1


def test_grep_search_tool_ignores_git_dir(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "internal.txt").write_text("secret_query", encoding="utf-8")
    (tmp_path / "normal.txt").write_text("clean", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GrepSearchTool()
    res = tool.execute({"query": "secret_query"}, context=ctx)
    assert res.success is True
    assert res.metadata["matches"] == 0


# =========================================================================
# GlobSearchTool Tests
# =========================================================================

def test_glob_search_tool_metadata():
    tool = GlobSearchTool()
    assert tool.name == "glob_search"
    assert tool.clearance_level == ToolClearanceLevel.READ_ONLY


def test_glob_search_tool_basic(tmp_path: Path):
    (tmp_path / "file1.txt").write_text("a", encoding="utf-8")
    (tmp_path / "file2.txt").write_text("b", encoding="utf-8")
    (tmp_path / "other.md").write_text("c", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GlobSearchTool()
    res = tool.execute({"pattern": "*.txt"}, context=ctx)
    assert res.success is True
    assert res.metadata["count"] == 2
    assert "file1.txt" in res.output
    assert "file2.txt" in res.output
    assert "other.md" not in res.output


def test_glob_search_tool_recursive(tmp_path: Path):
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)
    (sub / "nested.py").write_text("print()", encoding="utf-8")
    (tmp_path / "root.py").write_text("print()", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GlobSearchTool()
    res = tool.execute({"pattern": "**/*.py"}, context=ctx)
    assert res.success is True
    assert res.metadata["count"] == 2
    assert "root.py" in res.output
    assert "nested.py" in res.output


def test_glob_search_tool_max_results(tmp_path: Path):
    for i in range(10):
        (tmp_path / f"test_{i}.log").write_text("log", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GlobSearchTool()
    res = tool.execute({"pattern": "*.log", "max_results": 4}, context=ctx)
    assert res.success is True
    assert res.metadata["count"] == 4


def test_glob_search_tool_ignores_git(tmp_path: Path):
    git_dir = tmp_path / ".git" / "objects"
    git_dir.mkdir(parents=True)
    (git_dir / "obj.dat").write_text("binary", encoding="utf-8")
    (tmp_path / "valid.dat").write_text("valid", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = GlobSearchTool()
    res = tool.execute({"pattern": "**/*.dat"}, context=ctx)
    assert res.success is True
    assert res.metadata["count"] == 1
    assert "valid.dat" in res.output


def test_glob_search_tool_no_matches(tmp_path: Path):
    ctx = MockContext(workspace_root=tmp_path)
    tool = GlobSearchTool()
    res = tool.execute({"pattern": "*.nonexistent"}, context=ctx)
    assert res.success is True
    assert res.metadata["count"] == 0
    assert "No files matched" in res.output


def test_glob_search_tool_not_found(tmp_path: Path):
    tool = GlobSearchTool()
    res = tool.execute({"pattern": "*", "path": str(tmp_path / "missing")})
    assert res.success is False
    assert res.exit_code == 404


def test_glob_search_tool_empty_pattern():
    tool = GlobSearchTool()
    res = tool.execute({"pattern": ""})
    assert res.success is False
    assert res.exit_code == 1
