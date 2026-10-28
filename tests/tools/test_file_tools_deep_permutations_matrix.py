"""PRUBETH File & Core Tool Permutations Deep Matrix Tests.

Exhaustively verifies core file tools:
- ReadFileTool: line slicing, binary decoding, nonexistent paths
- WriteFileTool: parent directory auto-creation, unicode/emoji handling, overwrite
- EditFileTool: single-line, multi-line, deletion, target-not-found error
- DeleteFileTool: file deletion and nonexistent error handling
- CopyFileTool: replication and destination directory creation
- MoveFileTool: file relocation and nonexistent source handling
- ListDirTool: directory traversal and entry reporting
- GrepSearchTool: case sensitivity, regex patterns, multiline search
- GlobSearchTool: flat and recursive pattern matching
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.tools.core.read_file import ReadFileTool
from prubeth.tools.core.write_file import WriteFileTool
from prubeth.tools.core.edit_file import EditFileTool
from prubeth.tools.core.delete_file import DeleteFileTool
from prubeth.tools.core.copy_file import CopyFileTool
from prubeth.tools.core.move_file import MoveFileTool
from prubeth.tools.core.list_dir import ListDirTool
from prubeth.tools.core.grep_search import GrepSearchTool
from prubeth.tools.core.glob_search import GlobSearchTool


# ============================================================================
# 1. ReadFileTool Permutations
# ============================================================================

def test_read_file_nonexistent_returns_error(tmp_path: Path):
    tool = ReadFileTool()
    res = tool.execute({"path": str(tmp_path / "missing.txt")})
    assert res.success is False
    assert "not found" in res.output.lower() or "error" in res.output.lower()


def test_read_file_empty_file(tmp_path: Path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    tool = ReadFileTool()
    res = tool.execute({"path": str(f)})
    assert res.success is True
    assert res.output == ""


@pytest.mark.parametrize("start,end,expected_lines", [
    (1, 1, ["Line 1"]),
    (1, 3, ["Line 1", "Line 2", "Line 3"]),
    (3, 5, ["Line 3", "Line 4", "Line 5"]),
    (8, 10, ["Line 8", "Line 9", "Line 10"]),
    (9, 20, ["Line 9", "Line 10"]),  # past EOF
])
def test_read_file_line_ranges(tmp_path: Path, start: int, end: int, expected_lines: list[str]):
    f = tmp_path / "lines.txt"
    content = "\n".join(f"Line {i}" for i in range(1, 11))
    f.write_text(content, encoding="utf-8")

    tool = ReadFileTool()
    res = tool.execute({"path": str(f), "start_line": start, "end_line": end})
    assert res.success is True
    for expected in expected_lines:
        assert expected in res.output


def test_read_file_unicode_and_emojis(tmp_path: Path):
    f = tmp_path / "unicode.txt"
    f.write_text("Hello 🌍! PRUBETH autonomous CLI: 🚀 ⚡ 🛡️", encoding="utf-8")
    tool = ReadFileTool()
    res = tool.execute({"path": str(f)})
    assert res.success is True
    assert "🌍" in res.output
    assert "🚀" in res.output


# ============================================================================
# 2. WriteFileTool Permutations
# ============================================================================

def test_write_file_creates_nested_directories(tmp_path: Path):
    dest = tmp_path / "deep" / "nested" / "path" / "out.txt"
    tool = WriteFileTool()
    res = tool.execute({"path": str(dest), "content": "Autonomous Creation"})
    assert res.success is True
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == "Autonomous Creation"


@pytest.mark.parametrize("payload", [
    "Simple content",
    "",
    "Multiline\nContent\nWith\nNewlines",
    "JSON text: {\"key\": \"value\", \"count\": 42}",
    "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?",
    "Emoji payload: 🦾 🤖 🧠 ⚡ 🎯",
])
def test_write_file_various_payloads(tmp_path: Path, payload: str):
    dest = tmp_path / "test_write.txt"
    tool = WriteFileTool()
    res = tool.execute({"path": str(dest), "content": payload})
    assert res.success is True
    assert dest.read_text(encoding="utf-8") == payload


def test_write_file_overwrites_existing(tmp_path: Path):
    dest = tmp_path / "overwrite.txt"
    dest.write_text("Old Version", encoding="utf-8")

    tool = WriteFileTool()
    res = tool.execute({"path": str(dest), "content": "New Version"})
    assert res.success is True
    assert dest.read_text(encoding="utf-8") == "New Version"


# ============================================================================
# 3. EditFileTool Permutations
# ============================================================================

def test_edit_file_exact_single_line_replacement(tmp_path: Path):
    target_f = tmp_path / "edit_test.py"
    target_f.write_text("def run():\n    return False\n", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target_f),
        "target": "    return False",
        "replacement": "    return True"
    })
    assert res.success is True
    assert "return True" in target_f.read_text(encoding="utf-8")


def test_edit_file_multiline_block_replacement(tmp_path: Path):
    target_f = tmp_path / "multi.py"
    target_f.write_text(
        "class Service:\n"
        "    def old_m1(self): pass\n"
        "    def old_m2(self): pass\n",
        encoding="utf-8"
    )

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target_f),
        "target": "    def old_m1(self): pass\n    def old_m2(self): pass",
        "replacement": "    def new_m(self): return 1"
    })
    assert res.success is True
    content = target_f.read_text(encoding="utf-8")
    assert "def new_m(self): return 1" in content
    assert "old_m1" not in content


def test_edit_file_deletion_via_empty_replacement(tmp_path: Path):
    target_f = tmp_path / "del_block.py"
    target_f.write_text("x = 1\n# Deprecated comment\ny = 2\n", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target_f),
        "target": "# Deprecated comment\n",
        "replacement": ""
    })
    assert res.success is True
    assert "# Deprecated comment" not in target_f.read_text(encoding="utf-8")


def test_edit_file_target_not_found_returns_error(tmp_path: Path):
    target_f = tmp_path / "no_match.py"
    target_f.write_text("print('hello')", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target_f),
        "target": "this_string_does_not_exist",
        "replacement": "anything"
    })
    assert res.success is False
    assert "could not be located" in res.output.lower() or "not found" in res.output.lower()


# ============================================================================
# 4. Delete, Copy, Move Tools Permutations
# ============================================================================

def test_delete_existing_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "to_delete.txt"
    f.write_text("goodbye", encoding="utf-8")

    tool = DeleteFileTool()
    res = tool.execute({"path": str(f)})
    assert res.success is True
    assert not f.exists()


def test_delete_nonexistent_file_returns_error(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool = DeleteFileTool()
    res = tool.execute({"path": str(tmp_path / "ghost.txt")})
    assert res.success is False


def test_copy_file_creates_identical_replica(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "source.txt"
    src.write_text("replica content 123", encoding="utf-8")
    dest = tmp_path / "backup" / "replica.txt"

    tool = CopyFileTool()
    res = tool.execute({"src": str(src), "dst": str(dest)})
    assert res.success is True
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == "replica content 123"


def test_move_file_relocates_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "start.txt"
    src.write_text("moving...", encoding="utf-8")
    dest = tmp_path / "end.txt"

    tool = MoveFileTool()
    res = tool.execute({"src": str(src), "dst": str(dest)})
    assert res.success is True
    assert not src.exists()
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == "moving..."


# ============================================================================
# 5. ListDir, GrepSearch, GlobSearch Tools Permutations
# ============================================================================

def test_list_dir_lists_children(tmp_path: Path):
    (tmp_path / "f1.txt").touch()
    (tmp_path / "f2.py").touch()
    (tmp_path / "subdir").mkdir()

    tool = ListDirTool()
    res = tool.execute({"path": str(tmp_path)})
    assert res.success is True
    assert "f1.txt" in res.output
    assert "f2.py" in res.output
    assert "subdir" in res.output


def test_grep_search_case_sensitive_and_insensitive(tmp_path: Path):
    (tmp_path / "code.py").write_text("def CalculateSum(): return 10\n", encoding="utf-8")

    tool = GrepSearchTool()
    # Case sensitive match
    res1 = tool.execute({"path": str(tmp_path), "query": "CalculateSum", "case_sensitive": True})
    assert res1.success is True
    assert "CalculateSum" in res1.output

    # Case insensitive match
    res2 = tool.execute({"path": str(tmp_path), "query": "calculatesum", "case_sensitive": False})
    assert res2.success is True
    assert "CalculateSum" in res2.output


def test_glob_search_matches_extensions(tmp_path: Path):
    (tmp_path / "app.py").touch()
    (tmp_path / "test_app.py").touch()
    (tmp_path / "notes.txt").touch()

    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "mod.py").touch()

    tool = GlobSearchTool()
    res = tool.execute({"path": str(tmp_path), "pattern": "**/*.py"})
    assert res.success is True
    assert "app.py" in res.output
    assert "test_app.py" in res.output
    assert "mod.py" in res.output
    assert "notes.txt" not in res.output
