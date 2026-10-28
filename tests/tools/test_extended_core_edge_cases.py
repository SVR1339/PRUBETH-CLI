"""Extended edge cases, unicode preservation, lifecycle chains, and polyglot safety tests for PRUBETH core tools."""

import os
import sys
import pytest
from pathlib import Path

from prubeth.tools.core.read_file import ReadFileTool
from prubeth.tools.core.write_file import WriteFileTool
from prubeth.tools.core.edit_file import EditFileTool
from prubeth.tools.core.list_dir import ListDirTool
from prubeth.tools.core.delete_file import DeleteFileTool
from prubeth.tools.core.copy_file import CopyFileTool
from prubeth.tools.core.move_file import MoveFileTool
from prubeth.tools.core.grep_search import GrepSearchTool
from prubeth.tools.core.glob_search import GlobSearchTool
from prubeth.tools.core.run_shell import RunShellTool
from prubeth.tools.core.run_python import RunPythonTool
from prubeth.tools.registry import ToolRegistry


class MockContext:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root


# =========================================================================
# End-to-End Tool Lifecycle Chain
# =========================================================================

def test_full_tool_lifecycle_chain(tmp_path: Path):
    """Executes a complete 7-step autonomous development lifecycle chain."""
    ctx = MockContext(workspace_root=tmp_path)
    write_tool = WriteFileTool()
    read_tool = ReadFileTool()
    edit_tool = EditFileTool()
    list_tool = ListDirTool()
    copy_tool = CopyFileTool()
    move_tool = MoveFileTool()
    grep_tool = GrepSearchTool()
    glob_tool = GlobSearchTool()
    del_tool = DeleteFileTool()

    # Step 1: Write file
    r1 = write_tool.execute({
        "path": "service.py",
        "content": "def calculate(a, b):\n    return a + b\n"
    }, context=ctx)
    assert r1.success is True

    # Step 2: Read file back
    r2 = read_tool.execute({"path": "service.py"}, context=ctx)
    assert r2.success is True
    assert "calculate" in r2.output

    # Step 3: Search for symbol via grep
    r3 = grep_tool.execute({"query": "calculate", "file_pattern": "*.py"}, context=ctx)
    assert r3.success is True
    assert "service.py:1:" in r3.output

    # Step 4: Edit file
    r4 = edit_tool.execute({
        "path": "service.py",
        "target": "return a + b",
        "replacement": "return (a + b) * 2"
    }, context=ctx)
    assert r4.success is True
    assert "* 2" in (tmp_path / "service.py").read_text(encoding="utf-8")

    # Step 5: Copy file to backup
    r5 = copy_tool.execute({"src": "service.py", "dst": "service_backup.py"}, context=ctx)
    assert r5.success is True
    assert (tmp_path / "service_backup.py").is_file()

    # Step 6: Move / Rename original
    r6 = move_tool.execute({"src": "service.py", "dst": "service_v2.py"}, context=ctx)
    assert r6.success is True
    assert not (tmp_path / "service.py").exists()
    assert (tmp_path / "service_v2.py").is_file()

    # Step 7: Glob search finds both
    r7 = glob_tool.execute({"pattern": "service*.py"}, context=ctx)
    assert r7.success is True
    assert r7.metadata["count"] == 2

    # Step 8: Clean up with delete
    r8 = del_tool.execute({"path": "service_backup.py"}, context=ctx)
    assert r8.success is True
    assert not (tmp_path / "service_backup.py").exists()


# =========================================================================
# Unicode Invariant Preservation
# =========================================================================

@pytest.mark.parametrize("sample_text", [
    "CJK Characters: 这是一个中文测试, 日本語のテスト, 한국어 테스트",
    "Cyrillic: Тестирование автономного агента PRUBETH на русском языке",
    "Arabic: اختبار وكيل الذكاء الاصطناعي باللغة العربية",
    "Emoji & Symbols: 🚀 ⚡ 🛡️ 💎 🧠 π ≈ 3.14159, ∑(x_i), ∫f(x)dx, © 2026",
    "Accented Latin: Café résumé naïve señor façade Übergrößen",
])
def test_unicode_preservation_across_file_tools(tmp_path: Path, sample_text: str):
    ctx = MockContext(workspace_root=tmp_path)
    filename = "unicode_test.txt"

    # Write
    w = WriteFileTool()
    res_w = w.execute({"path": filename, "content": sample_text + "\n"}, context=ctx)
    assert res_w.success is True

    # Read
    r = ReadFileTool()
    res_r = r.execute({"path": filename}, context=ctx)
    assert res_r.success is True
    assert sample_text in res_r.output

    # Grep
    g = GrepSearchTool()
    query = sample_text.split()[1]  # Take second word as search query
    res_g = g.execute({"query": query}, context=ctx)
    assert res_g.success is True
    assert res_g.metadata["matches"] >= 1


# =========================================================================
# Deep Directory Slicing & Pagination
# =========================================================================

def test_large_file_line_pagination(tmp_path: Path):
    target = tmp_path / "large_dataset.txt"
    lines = [f"Record_{i:04d}: status=OK value={i*10}" for i in range(1, 1001)]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tool = ReadFileTool()
    ctx = MockContext(workspace_root=tmp_path)

    # Slice page 1: lines 1-50
    page1 = tool.execute({"path": "large_dataset.txt", "start_line": 1, "end_line": 50}, context=ctx)
    assert page1.success is True
    assert "Record_0001" in page1.output
    assert "Record_0050" in page1.output
    assert "Record_0051" not in page1.output
    assert page1.metadata["lines_rendered"] == 50

    # Slice page 10: lines 951-1000
    page10 = tool.execute({"path": "large_dataset.txt", "start_line": 951, "end_line": 1000}, context=ctx)
    assert page10.success is True
    assert "Record_0951" in page10.output
    assert "Record_1000" in page10.output
    assert "Record_0950" not in page10.output
    assert page10.metadata["lines_rendered"] == 50


def test_deep_directory_nesting_list_dir(tmp_path: Path):
    deep = tmp_path / "l1" / "l2" / "l3" / "l4" / "l5"
    deep.mkdir(parents=True)
    (deep / "leaf.py").write_text("print('leaf')", encoding="utf-8")

    tool = ListDirTool()
    ctx = MockContext(workspace_root=tmp_path)

    # Max depth 2 should not reach leaf
    res_shallow = tool.execute({"path": ".", "recursive": True, "max_depth": 2}, context=ctx)
    assert res_shallow.success is True
    assert "leaf.py" not in res_shallow.output

    # Max depth 6 should reach leaf
    res_deep = tool.execute({"path": ".", "recursive": True, "max_depth": 6}, context=ctx)
    assert res_deep.success is True
    assert "leaf.py" in res_deep.output


# =========================================================================
# Python Tool Isolated Computation Tests
# =========================================================================

def test_run_python_tool_standard_library_imports():
    tool = RunPythonTool()
    script = (
        "import json, math, itertools\n"
        "data = {'sqrt': math.isqrt(144), 'perms': len(list(itertools.permutations([1, 2, 3])))}\n"
        "print(json.dumps(data))\n"
    )
    res = tool.execute({"code": script})
    assert res.success is True
    assert '"sqrt": 12' in res.output
    assert '"perms": 6' in res.output
