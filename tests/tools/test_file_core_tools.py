"""Tests for PRUBETH Core File Operations Tools (ReadFile, WriteFile, EditFile, ListDir, DeleteFile, CopyFile, MoveFile)."""

import os
import pytest
from pathlib import Path

from prubeth.tools.core.read_file import ReadFileTool
from prubeth.tools.core.write_file import WriteFileTool
from prubeth.tools.core.edit_file import EditFileTool
from prubeth.tools.core.list_dir import ListDirTool
from prubeth.tools.core.delete_file import DeleteFileTool
from prubeth.tools.core.copy_file import CopyFileTool
from prubeth.tools.core.move_file import MoveFileTool
from prubeth.tools.base import ToolClearanceLevel


class MockContext:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root


# =========================================================================
# ReadFileTool Tests
# =========================================================================

def test_read_file_tool_metadata():
    tool = ReadFileTool()
    assert tool.name == "read_file"
    assert tool.clearance_level == ToolClearanceLevel.READ_ONLY
    assert len(tool.parameters) >= 3


def test_read_file_tool_basic(tmp_path: Path):
    sample = tmp_path / "hello.txt"
    sample.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    tool = ReadFileTool()
    res = tool.execute({"path": str(sample)})
    assert res.success is True
    assert res.exit_code == 0
    assert "1 | line 1" in res.output
    assert "2 | line 2" in res.output
    assert "3 | line 3" in res.output
    assert res.metadata["total_lines"] == 3


def test_read_file_tool_line_ranges(tmp_path: Path):
    sample = tmp_path / "numbered.txt"
    sample.write_text("\n".join([f"entry {i}" for i in range(1, 11)]) + "\n", encoding="utf-8")

    tool = ReadFileTool()
    # Read lines 3 through 5
    res = tool.execute({"path": str(sample), "start_line": 3, "end_line": 5})
    assert res.success is True
    assert "3 | entry 3" in res.output
    assert "4 | entry 4" in res.output
    assert "5 | entry 5" in res.output
    assert "1 | entry 1" not in res.output
    assert "6 | entry 6" not in res.output
    assert res.metadata["lines_rendered"] == 3


def test_read_file_tool_not_found(tmp_path: Path):
    tool = ReadFileTool()
    res = tool.execute({"path": str(tmp_path / "nonexistent.txt")})
    assert res.success is False
    assert res.exit_code == 404
    assert "File not found" in res.output


def test_read_file_tool_validation_errors():
    tool = ReadFileTool()
    res = tool.execute({})
    assert res.success is False
    assert res.exit_code == 1
    assert "Validation Error" in res.output

    res2 = tool.execute({"path": ""})
    assert res2.success is False
    assert "cannot be empty" in res2.output


def test_read_file_tool_character_limit(tmp_path: Path):
    sample = tmp_path / "long.txt"
    sample.write_text("A" * 500, encoding="utf-8")

    tool = ReadFileTool()
    res = tool.execute({"path": str(sample), "limit": 50})
    assert res.success is True
    assert "Truncated" in res.output
    assert res.metadata["truncated"] is True


def test_read_file_tool_workspace_context(tmp_path: Path):
    sample = tmp_path / "sub" / "doc.txt"
    sample.parent.mkdir(parents=True)
    sample.write_text("context works\n", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = ReadFileTool()
    res = tool.execute({"path": "sub/doc.txt"}, context=ctx)
    assert res.success is True
    assert "context works" in res.output


# =========================================================================
# WriteFileTool Tests
# =========================================================================

def test_write_file_tool_metadata():
    tool = WriteFileTool()
    assert tool.name == "write_file"
    assert tool.clearance_level == ToolClearanceLevel.WORKSPACE_MUTATION


def test_write_file_tool_creates_file(tmp_path: Path):
    target = tmp_path / "sub" / "output.txt"
    tool = WriteFileTool()
    res = tool.execute({"path": str(target), "content": "hello world\nline 2"})
    assert res.success is True
    assert res.exit_code == 0
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "hello world\nline 2"
    assert res.metadata["lines"] == 2


def test_write_file_tool_overwrites_atomically(tmp_path: Path):
    target = tmp_path / "target.py"
    target.write_text("x = 1\n", encoding="utf-8")

    tool = WriteFileTool()
    res = tool.execute({"path": str(target), "content": "x = 2\ny = 3\n"})
    assert res.success is True
    assert target.read_text(encoding="utf-8") == "x = 2\ny = 3\n"


def test_write_file_tool_syntax_gate_rejection(tmp_path: Path):
    target = tmp_path / "broken.py"
    tool = WriteFileTool()
    # Malformed python syntax
    res = tool.execute({"path": str(target), "content": "def broken(:\n    pass\n"})
    assert res.success is False
    assert res.exit_code == 422
    assert "syntax invariant failed" in res.output.lower()
    assert not target.exists()


def test_write_file_tool_syntax_gate_allows_non_code(tmp_path: Path):
    target = tmp_path / "notes.md"
    tool = WriteFileTool()
    res = tool.execute({"path": str(target), "content": "# Markdown Header\nSome regular notes.\n"})
    assert res.success is True
    assert target.is_file()


def test_write_file_tool_validation_errors():
    tool = WriteFileTool()
    res = tool.execute({"path": "file.txt"})  # missing content
    assert res.success is False
    assert res.exit_code == 1


# =========================================================================
# EditFileTool Tests
# =========================================================================

def test_edit_file_tool_metadata():
    tool = EditFileTool()
    assert tool.name == "edit_file"
    assert tool.clearance_level == ToolClearanceLevel.WORKSPACE_MUTATION


def test_edit_file_tool_exact_replacement(tmp_path: Path):
    target = tmp_path / "mod.py"
    target.write_text("def test():\n    return 41\n", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target),
        "target": "    return 41",
        "replacement": "    return 42"
    })
    assert res.success is True
    assert res.exit_code == 0
    assert "return 42" in target.read_text(encoding="utf-8")


def test_edit_file_tool_fuzzy_whitespace_replacement(tmp_path: Path):
    target = tmp_path / "indent.py"
    target.write_text("def compute():\n    val = 10\n    return val\n", encoding="utf-8")

    tool = EditFileTool()
    # Different leading indentation in target snippet
    res = tool.execute({
        "path": str(target),
        "target": "val = 10\nreturn val",
        "replacement": "val = 20\nreturn val * 2"
    })
    assert res.success is True
    content = target.read_text(encoding="utf-8")
    assert "val = 20" in content
    assert "return val * 2" in content


def test_edit_file_tool_target_not_found(tmp_path: Path):
    target = tmp_path / "mod.py"
    target.write_text("content = 'test'\n", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target),
        "target": "nonexistent block",
        "replacement": "replaced"
    })
    assert res.success is False
    assert res.exit_code == 400
    assert "could not be located" in res.output


def test_edit_file_tool_syntax_gate_rejection(tmp_path: Path):
    target = tmp_path / "code.py"
    target.write_text("x = 1\n", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target),
        "target": "x = 1",
        "replacement": "x = (\n"  # unclosed parenthesis
    })
    assert res.success is False
    assert res.exit_code == 422
    assert "invalid syntax" in res.output.lower()
    # Original file must remain untouched
    assert target.read_text(encoding="utf-8") == "x = 1\n"


def test_edit_file_tool_file_not_found(tmp_path: Path):
    tool = EditFileTool()
    res = tool.execute({
        "path": str(tmp_path / "missing.py"),
        "target": "x",
        "replacement": "y"
    })
    assert res.success is False
    assert res.exit_code == 404


# =========================================================================
# ListDirTool Tests
# =========================================================================

def test_list_dir_tool_basic(tmp_path: Path):
    (tmp_path / "file1.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "file2.py").write_text("print()", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.txt").write_text("nested", encoding="utf-8")

    tool = ListDirTool()
    res = tool.execute({"path": str(tmp_path)})
    assert res.success is True
    assert "[FILE] file1.txt" in res.output
    assert "[FILE] file2.py" in res.output
    assert "[DIR]  subdir/" in res.output
    # Non-recursive should not show nested.txt
    assert "nested.txt" not in res.output


def test_list_dir_tool_recursive(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir()
    (tmp_path / "a" / "b" / "deep.txt").write_text("deep", encoding="utf-8")

    tool = ListDirTool()
    res = tool.execute({"path": str(tmp_path), "recursive": True, "max_depth": 3})
    assert res.success is True
    assert "deep.txt" in res.output


def test_list_dir_tool_ignores_git_by_default(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("repo", encoding="utf-8")
    (tmp_path / "tracked.txt").write_text("ok", encoding="utf-8")

    tool = ListDirTool()
    res = tool.execute({"path": str(tmp_path), "show_hidden": False})
    assert res.success is True
    assert ".git" not in res.output
    assert "tracked.txt" in res.output


def test_list_dir_tool_not_found(tmp_path: Path):
    tool = ListDirTool()
    res = tool.execute({"path": str(tmp_path / "missing_dir")})
    assert res.success is False
    assert res.exit_code == 404


def test_list_dir_tool_path_is_file(tmp_path: Path):
    f = tmp_path / "a_file.txt"
    f.write_text("text", encoding="utf-8")

    tool = ListDirTool()
    res = tool.execute({"path": str(f)})
    assert res.success is False
    assert res.exit_code == 400
    assert "is not a directory" in res.output


# =========================================================================
# DeleteFileTool Tests
# =========================================================================

def test_delete_file_tool_deletes_single_file(tmp_path: Path):
    f = tmp_path / "victim.txt"
    f.write_text("delete me", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = DeleteFileTool()
    res = tool.execute({"path": "victim.txt"}, context=ctx)
    assert res.success is True
    assert not f.exists()


def test_delete_file_tool_deletes_empty_dir(tmp_path: Path):
    d = tmp_path / "empty_dir"
    d.mkdir()

    ctx = MockContext(workspace_root=tmp_path)
    tool = DeleteFileTool()
    res = tool.execute({"path": "empty_dir"}, context=ctx)
    assert res.success is True
    assert not d.exists()


def test_delete_file_tool_non_empty_dir_requires_recursive(tmp_path: Path):
    d = tmp_path / "full_dir"
    d.mkdir()
    (d / "item.txt").write_text("stay", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = DeleteFileTool()
    # Without recursive -> fail
    res = tool.execute({"path": "full_dir", "recursive": False}, context=ctx)
    assert res.success is False
    assert res.exit_code == 400
    assert "is not empty" in res.output
    assert d.exists()

    # With recursive -> succeed
    res2 = tool.execute({"path": "full_dir", "recursive": True}, context=ctx)
    assert res2.success is True
    assert not d.exists()


def test_delete_file_tool_security_escape_workspace(tmp_path: Path):
    ctx = MockContext(workspace_root=tmp_path)
    tool = DeleteFileTool()
    res = tool.execute({"path": "../outside.txt"}, context=ctx)
    assert res.success is False
    assert res.exit_code == 403
    assert "Security Violation" in res.output


def test_delete_file_tool_security_prevent_workspace_root_deletion(tmp_path: Path):
    ctx = MockContext(workspace_root=tmp_path)
    tool = DeleteFileTool()
    res = tool.execute({"path": "."}, context=ctx)
    assert res.success is False
    assert res.exit_code == 403
    assert "entire workspace root" in res.output


def test_delete_file_tool_security_prevent_git_deletion(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    ctx = MockContext(workspace_root=tmp_path)
    tool = DeleteFileTool()
    res = tool.execute({"path": ".git"}, context=ctx)
    assert res.success is False
    assert res.exit_code == 403
    assert ".git" in res.output


# =========================================================================
# CopyFileTool Tests
# =========================================================================

def test_copy_file_tool_single_file(tmp_path: Path):
    src = tmp_path / "source.txt"
    src.write_text("copy me", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = CopyFileTool()
    res = tool.execute({"src": "source.txt", "dst": "backup.txt"}, context=ctx)
    assert res.success is True
    assert (tmp_path / "backup.txt").read_text(encoding="utf-8") == "copy me"


def test_copy_file_tool_directory_tree(tmp_path: Path):
    src_dir = tmp_path / "pkg"
    src_dir.mkdir()
    (src_dir / "mod.py").write_text("x = 1", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = CopyFileTool()
    res = tool.execute({"src": "pkg", "dst": "pkg_copy"}, context=ctx)
    assert res.success is True
    assert (tmp_path / "pkg_copy" / "mod.py").is_file()


def test_copy_file_tool_overwrite_guard(tmp_path: Path):
    src = tmp_path / "s.txt"
    src.write_text("new", encoding="utf-8")
    dst = tmp_path / "d.txt"
    dst.write_text("old", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = CopyFileTool()
    # Without overwrite -> fails
    res = tool.execute({"src": "s.txt", "dst": "d.txt", "overwrite": False}, context=ctx)
    assert res.success is False
    assert res.exit_code == 409

    # With overwrite -> succeeds
    res2 = tool.execute({"src": "s.txt", "dst": "d.txt", "overwrite": True}, context=ctx)
    assert res2.success is True
    assert dst.read_text(encoding="utf-8") == "new"


# =========================================================================
# MoveFileTool Tests
# =========================================================================

def test_move_file_tool_single_file(tmp_path: Path):
    src = tmp_path / "old_name.txt"
    src.write_text("rename me", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = MoveFileTool()
    res = tool.execute({"src": "old_name.txt", "dst": "new_name.txt"}, context=ctx)
    assert res.success is True
    assert not src.exists()
    assert (tmp_path / "new_name.txt").read_text(encoding="utf-8") == "rename me"


def test_move_file_tool_directory(tmp_path: Path):
    src_dir = tmp_path / "old_dir"
    src_dir.mkdir()
    (src_dir / "inner.txt").write_text("data", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = MoveFileTool()
    res = tool.execute({"src": "old_dir", "dst": "new_dir"}, context=ctx)
    assert res.success is True
    assert not src_dir.exists()
    assert (tmp_path / "new_dir" / "inner.txt").is_file()


def test_move_file_tool_overwrite_guard(tmp_path: Path):
    src = tmp_path / "a.txt"
    src.write_text("source", encoding="utf-8")
    dst = tmp_path / "b.txt"
    dst.write_text("dest", encoding="utf-8")

    ctx = MockContext(workspace_root=tmp_path)
    tool = MoveFileTool()
    # Without overwrite -> fails
    res = tool.execute({"src": "a.txt", "dst": "b.txt", "overwrite": False}, context=ctx)
    assert res.success is False
    assert res.exit_code == 409

    # With overwrite -> succeeds
    res2 = tool.execute({"src": "a.txt", "dst": "b.txt", "overwrite": True}, context=ctx)
    assert res2.success is True
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "source"
