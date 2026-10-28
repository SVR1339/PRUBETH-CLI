"""Comprehensive Matrix Tests for PRUBETH Domain Tools."""

import os
from pathlib import Path
import pytest

from prubeth.tools.domain.todo import TodoTool
from prubeth.tools.domain.test_gen import TestGenTool
from prubeth.tools.domain.security_linter import SecurityLinterTool
from prubeth.tools.domain.crash_debugger import CrashDebuggerTool
from prubeth.tools.domain.benchmark import BenchmarkTool
from prubeth.tools.domain.heal import HealTool
from prubeth.tools.domain.spec_contract import SpecContractTool


# =========================================================================
# TodoTool Tests
# =========================================================================

def test_todo_tool_discovers_tags_and_priorities(tmp_path: Path):
    code_file = tmp_path / "app.py"
    code_file.write_text(
        "# TODO(alice): implement caching layer\n"
        "# FIXME: memory leak on disconnect\n"
        "# BUG: returns -1 on zero input\n"
        "# NOTE: internal helper function\n",
        encoding="utf-8"
    )

    tool = TodoTool()
    res = tool.execute({"path": str(tmp_path)})
    assert res.success is True
    assert res.metadata["count"] == 4

    items = res.metadata["items"]
    tag_map = {it["tag"]: it for it in items}

    assert tag_map["TODO"]["author"] == "alice"
    assert tag_map["TODO"]["priority"] == "MEDIUM"
    assert tag_map["FIXME"]["priority"] == "HIGH"
    assert tag_map["BUG"]["priority"] == "CRITICAL"
    assert tag_map["NOTE"]["priority"] == "LOW"


def test_todo_tool_filter_by_tag(tmp_path: Path):
    code_file = tmp_path / "app.py"
    code_file.write_text(
        "# TODO: first todo\n"
        "# FIXME: immediate fix\n",
        encoding="utf-8"
    )
    tool = TodoTool()
    res = tool.execute({"path": str(tmp_path), "tag": "FIXME"})
    assert res.success is True
    assert res.metadata["count"] == 1
    assert res.metadata["items"][0]["tag"] == "FIXME"


# =========================================================================
# TestGenTool Tests
# =========================================================================

def test_test_gen_synthesizes_function_tests(tmp_path: Path):
    src_file = tmp_path / "calculator.py"
    src_file.write_text(
        "def multiply(x: int, y: int) -> int:\n"
        "    '''Multiplies two numbers.'''\n"
        "    return x * y\n",
        encoding="utf-8"
    )

    tool = TestGenTool()
    res = tool.execute({"file_path": str(src_file), "symbol_name": "multiply"})
    assert res.success is True
    assert "def test_multiply_baseline():" in res.output
    assert "def test_multiply_edge_cases():" in res.output
    assert "from calculator import multiply" in res.output


def test_test_gen_synthesizes_class_tests(tmp_path: Path):
    src_file = tmp_path / "auth.py"
    src_file.write_text(
        "class TokenManager:\n"
        "    def create_token(self, user_id: str) -> str:\n"
        "        return 'token'\n",
        encoding="utf-8"
    )

    tool = TestGenTool()
    res = tool.execute({"file_path": str(src_file), "symbol_name": "TokenManager"})
    assert res.success is True
    assert "@pytest.fixture" in res.output
    assert "def tokenmanager_instance():" in res.output
    assert "test_tokenmanager_initialisation" in res.output


# =========================================================================
# SecurityLinterTool Tests
# =========================================================================

def test_security_linter_detects_secrets(tmp_path: Path):
    leak_file = tmp_path / "config.py"
    # Using dummy secret with OpenAI pattern
    leak_file.write_text("OPENAI_KEY = 'sk-1234567890abcdef1234567890abcdef1234567890'\n", encoding="utf-8")

    linter = SecurityLinterTool()
    res = linter.execute({"path": str(leak_file)})
    assert res.success is False
    assert res.metadata["count"] >= 1
    assert any(f["type"] == "SECRET" for f in res.metadata["findings"])


def test_security_linter_detects_eval(tmp_path: Path):
    vuln_file = tmp_path / "insecure.py"
    vuln_file.write_text("result = eval(user_input)\n", encoding="utf-8")

    linter = SecurityLinterTool()
    res = linter.execute({"path": str(vuln_file)})
    assert res.success is False
    assert any("eval()" in f["description"] for f in res.metadata["findings"])


# =========================================================================
# CrashDebuggerTool Tests
# =========================================================================

def test_crash_debugger_parses_python_traceback(tmp_path: Path):
    src_file = tmp_path / "math_ops.py"
    src_file.write_text(
        "def divide(a, b):\n"
        "    return a / b\n",
        encoding="utf-8"
    )

    tb = (
        f'Traceback (most recent call last):\n'
        f'  File "{src_file.as_posix()}", line 2, in divide\n'
        f'    return a / b\n'
        f'ZeroDivisionError: division by zero\n'
    )

    dbg = CrashDebuggerTool()
    res = dbg.execute({"traceback": tb})
    assert res.success is True
    assert res.metadata["exception"]["type"] == "ZeroDivisionError"
    assert len(res.metadata["frames"]) == 1
    root = res.metadata["root_frame"]
    assert root["line"] == 2
    assert ">>>    2 |     return a / b" in res.output


# =========================================================================
# BenchmarkTool Tests
# =========================================================================

def test_benchmark_executes_and_reports_percentiles():
    bm = BenchmarkTool()
    res = bm.execute({
        "code": "x = [i * 2 for i in range(1000)]",
        "iterations": 15,
        "warmup": 3
    })
    assert res.success is True
    assert res.metadata["iterations"] == 15
    assert res.metadata["mean_ms"] >= 0.0
    assert res.metadata["p95_ms"] >= res.metadata["min_ms"]
    assert "Benchmark Results" in res.output


# =========================================================================
# SpecContractTool Tests
# =========================================================================

def test_spec_contract_tool_detects_breaking_change(tmp_path: Path):
    svc_file = tmp_path / "service.py"
    svc_file.write_text("def send_notification(user_id: int) -> bool:\n    return True\n", encoding="utf-8")

    tool = SpecContractTool()
    # Proposed edit adds mandatory parameter 'priority'
    proposed = "def send_notification(user_id: int, priority: str) -> bool:\n    return True\n"
    res = tool.execute({"file_path": str(svc_file), "new_content": proposed})
    assert res.success is False
    assert res.metadata["valid"] is False
    assert res.metadata["has_errors"] is True
    assert "mandatory parameter 'priority'" in res.output
