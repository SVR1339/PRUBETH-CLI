"""Comprehensive Matrix Tests for PRUBETH Verification Tools."""

import json
from pathlib import Path
import pytest

from prubeth.tools.verification.test_runner import TestRunnerTool
from prubeth.tools.verification.lint_checker import LintCheckerTool
from prubeth.tools.verification.type_checker import TypeCheckerTool
from prubeth.tools.verification.coverage_analyser import CoverageAnalyserTool
from prubeth.tools.verification.patch_verifier import PatchVerifierTool


# =========================================================================
# TestRunnerTool Tests
# =========================================================================

def test_test_runner_parse_pytest_output_clean():
    sample_output = (
        "============================= test session starts =============================\n"
        "tests/test_auth.py ..\n"
        "tests/test_db.py ...\n"
        "============================= 5 passed in 0.42s =============================\n"
    )
    parsed = TestRunnerTool.parse_test_output(sample_output, framework="pytest")
    assert parsed["passed"] == 5
    assert parsed["failed"] == 0
    assert parsed["total"] == 5
    assert len(parsed["failures"]) == 0


def test_test_runner_parse_pytest_output_with_failures():
    sample_output = (
        "tests/test_api.py .F.\n"
        "=================================== FAILURES ===================================\n"
        "FAILED tests/test_api.py::test_endpoint_timeout - TimeoutError\n"
        "========================= 1 failed, 2 passed in 1.10s =========================\n"
    )
    parsed = TestRunnerTool.parse_test_output(sample_output, framework="pytest")
    assert parsed["passed"] == 2
    assert parsed["failed"] == 1
    assert parsed["total"] == 3
    assert len(parsed["failures"]) == 1
    assert parsed["failures"][0]["test_id"] == "tests/test_api.py::test_endpoint_timeout"


def test_test_runner_missing_command_returns_error():
    runner = TestRunnerTool()
    res = runner.execute({"framework": "custom", "target": ""})
    assert res.success is False
    assert "No test command or target specified" in res.error


# =========================================================================
# LintCheckerTool Tests
# =========================================================================

def test_lint_checker_ast_detects_clean_code(tmp_path: Path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def add(x: int, y: int) -> int:\n    return x + y\n", encoding="utf-8")

    linter = LintCheckerTool()
    res = linter.execute({"path": str(clean_file), "linter": "ast"})
    assert res.success is True
    assert res.metadata["scanned_files"] == 1
    assert len(res.metadata["diagnostics"]) == 0


def test_lint_checker_ast_detects_bare_except_warning(tmp_path: Path):
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("try:\n    x = 1\nexcept:\n    pass\n", encoding="utf-8")

    linter = LintCheckerTool()
    res = linter.execute({"path": str(bad_file), "linter": "ast"})
    assert res.success is True  # Warning only, not blocking error
    assert any(d["code"] == "E722" for d in res.metadata["diagnostics"])


def test_lint_checker_ast_detects_syntax_error(tmp_path: Path):
    broken_file = tmp_path / "broken.py"
    broken_file.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")

    linter = LintCheckerTool()
    res = linter.execute({"path": str(broken_file), "linter": "ast"})
    assert res.success is False
    assert any(d["code"] == "E999" for d in res.metadata["diagnostics"])


# =========================================================================
# TypeCheckerTool Tests
# =========================================================================

def test_type_checker_calculates_coverage(tmp_path: Path):
    py_file = tmp_path / "typed.py"
    py_file.write_text(
        "def fully_typed(a: int, b: str) -> bool:\n    return True\n\n"
        "def untyped_func(x, y):\n    return x + y\n",
        encoding="utf-8"
    )

    tc = TypeCheckerTool()
    res = tc.execute({"path": str(py_file), "engine": "ast"})
    assert res.success is True
    assert res.metadata["total_functions"] == 2
    assert res.metadata["annotated_functions"] == 1
    assert res.metadata["coverage_pct"] == 50.0
    assert res.metadata["missing_count"] == 1


def test_type_checker_strict_mode_fails_on_untyped(tmp_path: Path):
    py_file = tmp_path / "untyped.py"
    py_file.write_text("def untyped(x):\n    return x\n", encoding="utf-8")

    tc = TypeCheckerTool()
    res = tc.execute({"path": str(py_file), "engine": "ast", "strict": True})
    assert res.success is False
    assert "Strict type checking failed" in res.error


# =========================================================================
# CoverageAnalyserTool Tests
# =========================================================================

def test_coverage_analyser_parses_json_report(tmp_path: Path):
    report_file = tmp_path / "coverage.json"
    report_file.write_text(json.dumps({
        "totals": {"percent_covered": 85.5},
        "files": {}
    }), encoding="utf-8")

    cov = CoverageAnalyserTool()
    res = cov.execute({"report_file": str(report_file), "min_coverage": 80.0})
    assert res.success is True
    assert res.metadata["coverage_pct"] == 85.5


def test_coverage_analyser_fails_below_threshold(tmp_path: Path):
    report_file = tmp_path / "low_coverage.json"
    report_file.write_text(json.dumps({
        "totals": {"percent_covered": 62.0},
        "files": {}
    }), encoding="utf-8")

    cov = CoverageAnalyserTool()
    res = cov.execute({"report_file": str(report_file), "min_coverage": 80.0})
    assert res.success is False
    assert "below minimum threshold" in res.error


# =========================================================================
# PatchVerifierTool Tests
# =========================================================================

def test_patch_verifier_valid_dry_run(tmp_path: Path):
    sample = tmp_path / "sample.py"
    sample.write_text("def test():\n    return 1\n", encoding="utf-8")

    verifier = PatchVerifierTool()
    res = verifier.execute({
        "path": str(sample),
        "target": "    return 1",
        "replacement": "    return 2"
    })
    assert res.success is True
    assert res.metadata["syntax_valid"] is True
    assert res.metadata["match_kind"] == "exact"
    # Ensure file on disk was NOT modified (dry run invariant)
    assert sample.read_text(encoding="utf-8") == "def test():\n    return 1\n"


def test_patch_verifier_detects_syntax_error_in_patch(tmp_path: Path):
    sample = tmp_path / "sample.py"
    sample.write_text("def test():\n    return 1\n", encoding="utf-8")

    verifier = PatchVerifierTool()
    res = verifier.execute({
        "path": str(sample),
        "target": "    return 1",
        "replacement": "    return (broken syntax"
    })
    assert res.success is False
    assert "SyntaxError in prospective patched code" in res.error
