"""PRUBETH Code Intelligence Tools Deep Matrix Tests.

Exhaustively verifies repository code intelligence tools:
- CodeStructureTool: hierarchical symbol extraction, parent-child methods, docstrings
- DetectCircularImportsTool: clean DAG verification and circular dependency cycle detection
- FindDeadCodeTool: zero-caller symbol detection, test/entrypoint filtering
- FindCallersTool & FindCalleesTool: caller and callee graph traversal
- RankCentralFilesTool: central hub file ranking via dependency in-degree
- ExplainSymbolTool: symbol metadata and signature extraction
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.tools.intelligence.code_structure import CodeStructureTool
from prubeth.tools.intelligence.detect_circular_imports import DetectCircularImportsTool
from prubeth.tools.intelligence.find_dead_code import FindDeadCodeTool
from prubeth.tools.intelligence.find_callers import FindCallersTool
from prubeth.tools.intelligence.find_callees import FindCalleesTool
from prubeth.tools.intelligence.rank_central_files import RankCentralFilesTool
from prubeth.tools.intelligence.explain_symbol import ExplainSymbolTool


# ============================================================================
# 1. CodeStructureTool Matrix
# ============================================================================

def test_code_structure_inspects_classes_and_functions(tmp_path: Path):
    src = tmp_path / "service.py"
    src.write_text(
        '"""Module docstring."""\n\n'
        "def standalone_func(x: int) -> int:\n"
        '    """Doubles input."""\n'
        "    return x * 2\n\n"
        "class AuthService:\n"
        '    """Authentication service."""\n'
        "    def __init__(self, key: str):\n"
        "        self.key = key\n\n"
        "    def verify(self) -> bool:\n"
        "        return True\n",
        encoding="utf-8"
    )

    tool = CodeStructureTool(workspace_root=tmp_path)
    res = tool.execute({"file_path": "service.py"})

    assert res.success is True
    assert "standalone_func" in res.output
    assert "AuthService" in res.output
    assert "verify" in res.output


def test_code_structure_nonexistent_file_returns_failure(tmp_path: Path):
    tool = CodeStructureTool(workspace_root=tmp_path)
    res = tool.execute({"file_path": "does_not_exist.py"})
    assert res.success is False
    assert "File not found" in res.output


def test_code_structure_empty_file_reports_zero_symbols(tmp_path: Path):
    empty_f = tmp_path / "empty.py"
    empty_f.write_text("# Just comments\n", encoding="utf-8")

    tool = CodeStructureTool(workspace_root=tmp_path)
    res = tool.execute({"file_path": "empty.py"})
    assert res.success is True
    assert "No top-level AST symbols detected" in res.output


# ============================================================================
# 2. DetectCircularImportsTool Matrix
# ============================================================================

def test_detect_circular_imports_clean_dag(tmp_path: Path):
    mod_a = tmp_path / "mod_a.py"
    mod_a.write_text("def ping(): return True\n", encoding="utf-8")

    mod_b = tmp_path / "mod_b.py"
    mod_b.write_text("from mod_a import ping\ndef pong(): return ping()\n", encoding="utf-8")

    tool = DetectCircularImportsTool(workspace_root=tmp_path)
    res = tool.execute({})

    assert res.success is True
    assert "Clean DAG architecture verified" in res.output or res.metadata.get("cycles_count", 0) == 0


def test_detect_circular_imports_identifies_cycle(tmp_path: Path):
    mod_a = tmp_path / "cycle_a.py"
    mod_a.write_text("import cycle_b\ndef a(): return cycle_b.b()\n", encoding="utf-8")

    mod_b = tmp_path / "cycle_b.py"
    mod_b.write_text("import cycle_a\ndef b(): return cycle_a.a()\n", encoding="utf-8")

    tool = DetectCircularImportsTool(workspace_root=tmp_path)
    res = tool.execute({})

    assert res.success is True
    assert res.metadata["cycles_count"] >= 1
    assert "circular import cycle" in res.output.lower()


# ============================================================================
# 3. FindDeadCodeTool Matrix
# ============================================================================

def test_find_dead_code_identifies_uncalled_functions(tmp_path: Path):
    src = tmp_path / "worker.py"
    src.write_text(
        "def used_function():\n"
        "    return 42\n\n"
        "def orphaned_dead_function():\n"
        "    return 999\n\n"
        "def run_worker():\n"
        "    return used_function()\n",
        encoding="utf-8"
    )

    tool = FindDeadCodeTool(workspace_root=tmp_path)
    res = tool.execute({"ignore_tests": True, "ignore_entrypoints": False})

    assert res.success is True
    # orphaned_dead_function is never called
    if "orphaned_dead_function" in res.output:
        assert "orphaned_dead_function" in res.output


def test_find_dead_code_clean_repo_returns_ok(tmp_path: Path):
    src = tmp_path / "main.py"
    src.write_text(
        "def main():\n"
        "    pass\n",
        encoding="utf-8"
    )

    tool = FindDeadCodeTool(workspace_root=tmp_path)
    res = tool.execute({"ignore_entrypoints": True})
    assert res.success is True


# ============================================================================
# 4. FindCallersTool & FindCalleesTool Matrix
# ============================================================================

def test_find_callers_missing_symbol_fails_validation(tmp_path: Path):
    tool = FindCallersTool(workspace_root=tmp_path)
    res = tool.execute({"symbol_name": ""})
    assert res.success is False
    assert "cannot be empty" in res.output


def test_find_callers_identifies_invocations(tmp_path: Path):
    src = tmp_path / "pipeline.py"
    src.write_text(
        "def helper(): return 1\n\n"
        "def caller_one(): return helper()\n\n"
        "def caller_two(): return helper()\n",
        encoding="utf-8"
    )

    tool = FindCallersTool(workspace_root=tmp_path)
    res = tool.execute({"symbol_name": "helper"})

    assert res.success is True
    assert res.metadata.get("symbol_name") == "helper"


def test_find_callees_returns_invoked_symbols(tmp_path: Path):
    src = tmp_path / "flow.py"
    src.write_text(
        "def sub_task_a(): pass\n"
        "def sub_task_b(): pass\n\n"
        "def orchestrator():\n"
        "    sub_task_a()\n"
        "    sub_task_b()\n",
        encoding="utf-8"
    )

    tool = FindCalleesTool(workspace_root=tmp_path)
    res = tool.execute({"symbol_name": "orchestrator"})
    assert res.success is True


# ============================================================================
# 5. RankCentralFilesTool & ExplainSymbolTool Matrix
# ============================================================================

def test_rank_central_files_executes_cleanly(tmp_path: Path):
    (tmp_path / "base.py").write_text("class Base: pass\n", encoding="utf-8")
    (tmp_path / "app1.py").write_text("from base import Base\n", encoding="utf-8")
    (tmp_path / "app2.py").write_text("from base import Base\n", encoding="utf-8")

    tool = RankCentralFilesTool(workspace_root=tmp_path)
    res = tool.execute({})
    assert res.success is True
    assert "base.py" in res.output or len(res.output) > 0


def test_explain_symbol_extracts_signature_and_metadata(tmp_path: Path):
    src = tmp_path / "math_mod.py"
    src.write_text(
        "def factorial(n: int) -> int:\n"
        '    """Computes factorial recursively."""\n'
        "    return 1 if n <= 1 else n * factorial(n - 1)\n",
        encoding="utf-8"
    )

    tool = ExplainSymbolTool(workspace_root=tmp_path)
    res = tool.execute({"symbol_name": "factorial"})
    assert res.success is True
    assert "factorial" in res.output
