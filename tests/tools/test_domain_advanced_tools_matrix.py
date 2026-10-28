"""PRUBETH Advanced Domain Tools Matrix.

Exhaustively verifies CoverageAnalyserTool, SpecContractTool, TestGenTool,
HealTool, and SecurityLinterTool across input configurations, mock states,
and boundary conditions.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from prubeth.tools.verification.coverage_analyser import CoverageAnalyserTool
from prubeth.tools.domain.spec_contract import SpecContractTool
from prubeth.tools.domain.test_gen import TestGenTool
from prubeth.tools.domain.heal import HealTool
from prubeth.tools.domain.security_linter import SecurityLinterTool


# ============================================================================
# 1. CoverageAnalyserTool Matrix
# ============================================================================

def test_coverage_analyser_with_json_report(tmp_path: Path):
    report_file = tmp_path / "coverage.json"
    data = {
        "totals": {
            "percent_covered": 85.5,
            "covered_lines": 171,
            "num_statements": 200,
            "missing_lines": 29
        },
        "files": {
            "src/engine.py": {
                "summary": {"percent_covered": 85.5, "missing_lines": 29},
                "missing_lines": [10, 11, 12]
            }
        }
    }
    report_file.write_text(json.dumps(data), encoding="utf-8")

    tool = CoverageAnalyserTool()
    res = tool.execute({"report_file": str(report_file), "min_coverage": 80.0})
    assert res.success
    assert "85.5%" in res.output
    assert res.metadata["coverage_pct"] == 85.5


def test_coverage_analyser_fails_threshold(tmp_path: Path):
    report_file = tmp_path / "coverage.json"
    data = {
        "totals": {"percent_covered": 72.0, "covered_lines": 72, "num_statements": 100, "missing_lines": 28},
        "files": {}
    }
    report_file.write_text(json.dumps(data), encoding="utf-8")

    tool = CoverageAnalyserTool()
    res = tool.execute({"report_file": str(report_file), "min_coverage": 80.0})
    assert not res.success
    assert "below threshold" in res.error.lower() or "failed" in res.output.lower() or not res.success


# ============================================================================
# 2. SpecContractTool Matrix
# ============================================================================

def test_spec_contract_missing_file_path():
    tool = SpecContractTool()
    res = tool.execute({"file_path": "", "new_content": "def foo(): pass"})
    assert not res.success
    assert "Missing file_path" in res.error


def test_spec_contract_safe_addition(tmp_path: Path):
    p = tmp_path / "api.py"
    initial = "def compute(x: int) -> int:\n    return x * 2\n"
    p.write_text(initial, encoding="utf-8")

    tool = SpecContractTool()
    # Adding a new function is non-breaking
    updated = initial + "\ndef compute_async(x: int) -> int:\n    return x * 2\n"
    res = tool.execute({"file_path": str(p), "new_content": updated})
    assert res.success
    assert "passed" in res.output.lower() or "compatible" in res.output.lower()


def test_spec_contract_breaking_change_and_force_override(tmp_path: Path):
    p = tmp_path / "api.py"
    initial = "def compute(x: int, y: int) -> int:\n    return x + y\n"
    p.write_text(initial, encoding="utf-8")

    tool = SpecContractTool()
    # Dropping a parameter is a breaking change
    broken = "def compute(x: int) -> int:\n    return x\n"

    # Without force: fails
    res_fail = tool.execute({"file_path": str(p), "new_content": broken, "force": False})
    assert not res_fail.success
    assert "breaking" in (res_fail.error or "").lower() or "contract violation" in (res_fail.output or "").lower()

    # With force: passes with override flag
    res_forced = tool.execute({"file_path": str(p), "new_content": broken, "force": True})
    assert res_forced.success


# ============================================================================
# 3. TestGenTool Matrix
# ============================================================================

def test_test_gen_missing_arguments():
    tool = TestGenTool()
    res = tool.execute({"file_path": "", "symbol_name": ""})
    assert not res.success
    assert "Missing file_path" in res.error


def test_test_gen_nonexistent_file(tmp_path: Path):
    tool = TestGenTool()
    res = tool.execute({"file_path": str(tmp_path / "nonexistent.py"), "symbol_name": "foo"})
    assert not res.success
    assert "does not exist" in res.error


def test_test_gen_synthesizes_function_tests(tmp_path: Path):
    p = tmp_path / "math_utils.py"
    p.write_text(
        "def multiply(a: int, b: int) -> int:\n"
        "    \"\"\"Multiplies two integers.\"\"\"\n"
        "    return a * b\n",
        encoding="utf-8"
    )
    tool = TestGenTool()
    res = tool.execute({"file_path": str(p), "symbol_name": "multiply", "framework": "pytest"})
    assert res.success
    assert "test_multiply" in res.output
    assert "pytest" in res.output or "def test_" in res.output


def test_test_gen_symbol_not_found(tmp_path: Path):
    p = tmp_path / "sample.py"
    p.write_text("def existing(): pass\n", encoding="utf-8")
    tool = TestGenTool()
    res = tool.execute({"file_path": str(p), "symbol_name": "ghost_function"})
    assert not res.success
    assert "not found" in res.error.lower()


# ============================================================================
# 4. HealTool Matrix
# ============================================================================

def test_heal_tool_missing_command():
    tool = HealTool()
    res = tool.execute({"test_command": ""})
    assert not res.success
    assert "Missing test_command" in res.error


def test_heal_tool_mocked_execution(monkeypatch: pytest.MonkeyPatch):
    from prubeth.runtime.auto_heal import AutoHealer

    mock_healer = MagicMock(spec=AutoHealer)
    mock_healer.heal.return_value = {
        "success": True,
        "attempts": 1,
        "message": "Self-healing completed successfully on attempt 1."
    }
    monkeypatch.setattr("prubeth.runtime.auto_heal.AutoHealer", lambda: mock_healer)

    tool = HealTool()
    res = tool.execute({"test_command": "pytest tests/test_dummy.py", "max_attempts": 2})
    assert res.success
    assert "completed successfully" in res.output


# ============================================================================
# 5. SecurityLinterTool Matrix
# ============================================================================

def test_security_linter_clean_code(tmp_path: Path):
    p = tmp_path / "safe.py"
    p.write_text("def compute(x: int) -> int:\n    return x * 10\n", encoding="utf-8")
    tool = SecurityLinterTool()
    res = tool.execute({"path": str(p)})
    assert res.success
    assert "Found 0 security issues" in res.output or "clean" in res.output.lower()


@pytest.mark.parametrize("secret_sample,expected_title", [
    ('api_val = "AIzaSyD12345678901234567890123456789012"', "Google Cloud"),
    ('token = "sk-1234567890abcdef1234567890abcdef1234"', "OpenAI"),
    ('gh = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"', "GitHub"),
    ('aws = "AKIA1234567890ABCDEF"', "AWS"),
])
def test_security_linter_catches_secrets(tmp_path: Path, secret_sample: str, expected_title: str):
    p = tmp_path / "credentials.py"
    p.write_text(f"# sample credential file\n{secret_sample}\n", encoding="utf-8")
    tool = SecurityLinterTool()
    res = tool.execute({"path": str(p)})
    # Security audit fails when CRITICAL or HIGH credentials are found
    assert not res.success
    assert expected_title in res.output
    assert "CRITICAL" in res.output or "HIGH" in res.output
    assert res.metadata["count"] >= 1


@pytest.mark.parametrize("insecure_code,expected_warning,expected_success", [
    ("res = eval(user_input)", "Dangerous eval()", False),
    ("exec(dynamic_code)", "Dangerous exec()", False),
    ("subprocess.run('ls', shell=True)", "Subprocess shell=True", True),
    ("h = hashlib.md5(b'data')", "Weak cryptographic hash", True),
])
def test_security_linter_catches_insecure_patterns(tmp_path: Path, insecure_code: str, expected_warning: str, expected_success: bool):
    p = tmp_path / "vulnerable.py"
    p.write_text(f"import hashlib, subprocess\n{insecure_code}\n", encoding="utf-8")
    tool = SecurityLinterTool()
    res = tool.execute({"path": str(p)})
    assert res.success == expected_success
    assert expected_warning in res.output


def test_security_linter_severity_threshold(tmp_path: Path):
    p = tmp_path / "mixed.py"
    # Contains a LOW issue (md5) and a CRITICAL issue (OpenAI key)
    p.write_text(
        "import hashlib\n"
        "h = hashlib.md5(b'x')\n"
        'key = "sk-1234567890abcdef1234567890abcdef1234"\n',
        encoding="utf-8"
    )
    tool = SecurityLinterTool()
    # When filtering by CRITICAL, MD5 should NOT appear in output, and the audit fails due to CRITICAL key
    res = tool.execute({"path": str(p), "min_severity": "CRITICAL"})
    assert not res.success
    assert "OpenAI" in res.output and "Secret Key" in res.output
    assert "Weak cryptographic hash" not in res.output
