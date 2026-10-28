"""PRUBETH Independent Verifier & Quality Engine Matrix Tests.

Exhaustively verifies Subsystem 7: IndependentVerifier test runner detection,
multi-language test output parsing (pytest, Cargo, Go, Jest, dotnet, unittest),
timeout recovery, and structured VerificationEvidence invariants.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from prubeth.verification.verifier import IndependentVerifier, VerificationEvidence


# ============================================================================
# 1. VerificationEvidence Data Invariants
# ============================================================================

def test_verification_evidence_summary_passed():
    ev = VerificationEvidence(
        success=True,
        framework="pytest",
        exit_code=0,
        tests_passed=42,
        tests_failed=0,
        duration_s=1.23,
    )
    summary = ev.summary()
    assert "[PASSED] pytest" in summary
    assert "Passed: 42, Failed: 0" in summary
    assert "Exit code: 0" in summary


def test_verification_evidence_summary_failed():
    ev = VerificationEvidence(
        success=False,
        framework="cargo_test",
        exit_code=101,
        tests_passed=10,
        tests_failed=2,
        duration_s=3.45,
    )
    summary = ev.summary()
    assert "[FAILED] cargo_test" in summary
    assert "Passed: 10, Failed: 2" in summary
    assert "Exit code: 101" in summary


# ============================================================================
# 2. Test Framework Auto-Detection Matrix
# ============================================================================

def test_detect_framework_pytest_ini(tmp_path: Path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    verifier = IndependentVerifier(str(tmp_path))
    assert verifier.detect_test_framework() == "pytest"


def test_detect_framework_conftest(tmp_path: Path):
    (tmp_path / "conftest.py").write_text("# fixtures\n", encoding="utf-8")
    verifier = IndependentVerifier(str(tmp_path))
    assert verifier.detect_test_framework() == "pytest"


def test_detect_framework_tests_dir_with_python_tests(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_example.py").write_text("def test_one(): pass\n", encoding="utf-8")
    verifier = IndependentVerifier(str(tmp_path))
    assert verifier.detect_test_framework() == "pytest"


def test_detect_framework_npm_package_json(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}\n', encoding="utf-8")
    verifier = IndependentVerifier(str(tmp_path))
    assert verifier.detect_test_framework() == "npm_test"


def test_detect_framework_cargo_toml(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "app"\n', encoding="utf-8")
    verifier = IndependentVerifier(str(tmp_path))
    assert verifier.detect_test_framework() == "cargo_test"


# ============================================================================
# 3. Test Output Parsing Matrix (Mocks)
# ============================================================================

@patch("subprocess.run")
def test_parse_pytest_output_clean(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="==================== 25 passed in 0.42s ====================\n",
        stderr="",
    )
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="pytest")
    assert ev.success is True
    assert ev.exit_code == 0
    assert ev.tests_passed == 25
    assert ev.tests_failed == 0


@patch("subprocess.run")
def test_parse_pytest_output_with_failures(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="FAILED test_calc.py::test_div\n==================== 22 passed, 3 failed in 1.15s ====================\n",
        stderr="",
    )
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="pytest")
    assert ev.success is False
    assert ev.exit_code == 1
    assert ev.tests_passed == 22
    assert ev.tests_failed == 3
    assert any("FAILED" in line for line in ev.unresolved_failures)


@patch("subprocess.run")
def test_parse_cargo_rust_output(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="running 8 tests\ntest result: ok. 8 passed; 0 failed; 0 ignored;\n",
        stderr="",
    )
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="cargo test")
    assert ev.success is True
    assert ev.tests_passed == 8
    assert ev.tests_failed == 0


@patch("subprocess.run")
def test_parse_go_test_output(mock_run, tmp_path: Path):
    stdout = (
        "=== RUN   TestAdd\n"
        "--- PASS: TestAdd (0.00s)\n"
        "=== RUN   TestSub\n"
        "--- PASS: TestSub (0.00s)\n"
        "=== RUN   TestDiv\n"
        "--- FAIL: TestDiv (0.00s)\n"
        "FAIL\n"
    )
    mock_run.return_value = MagicMock(returncode=1, stdout=stdout, stderr="")
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="go test ./...")
    assert ev.success is False
    assert ev.tests_passed == 2
    assert ev.tests_failed == 1


@patch("subprocess.run")
def test_parse_jest_output(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="PASS src/math.test.ts\nTests:  14 passed, 14 total\nTime: 1.45 s\n",
        stderr="",
    )
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="npm test")
    assert ev.success is True
    assert ev.tests_passed == 14
    assert ev.tests_failed == 0


@patch("subprocess.run")
def test_parse_dotnet_output(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="Passed!  - Failed: 0, Passed: 18, Skipped: 0, Total: 18, Duration: 200 ms\n",
        stderr="",
    )
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="dotnet test")
    assert ev.success is True
    assert ev.tests_passed == 18
    assert ev.tests_failed == 0


@patch("subprocess.run")
def test_parse_python_unittest_success(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="Ran 12 tests in 0.050s\n\nOK\n",
        stderr="",
    )
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="python -m unittest")
    assert ev.success is True
    assert ev.tests_passed == 12
    assert ev.tests_failed == 0


@patch("subprocess.run")
def test_parse_python_unittest_failure(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="FAIL: test_broken (test_mod.TestClass)\nAssertionError: 1 != 2\n\nRan 10 tests in 0.040s\n\nFAILED (failures=2)\n",
        stderr="",
    )
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="python -m unittest")
    assert ev.success is False
    assert ev.tests_passed == 8
    assert ev.tests_failed == 2
    assert len(ev.unresolved_failures) >= 1


# ============================================================================
# 4. Error Handling & Timeout Recovery
# ============================================================================

@patch("subprocess.run")
def test_run_verification_timeout_handling(mock_run, tmp_path: Path):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=30)
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="pytest", timeout=30)
    assert ev.success is False
    assert ev.exit_code == -1
    assert "timed out after 30 seconds" in ev.stderr
    assert "Timeout expired" in ev.unresolved_failures[0]


@patch("subprocess.run")
def test_run_verification_generic_exception(mock_run, tmp_path: Path):
    mock_run.side_effect = PermissionError("Permission denied")
    verifier = IndependentVerifier(str(tmp_path))
    ev = verifier.run_verification(custom_command="pytest")
    assert ev.success is False
    assert ev.exit_code == -1
    assert "Permission denied" in ev.stderr
    assert "Exception during test run" in ev.unresolved_failures[0]
