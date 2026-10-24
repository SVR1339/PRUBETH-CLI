import subprocess
import re
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class VerificationEvidence:
    """Structured verifiable proof of correctness."""
    success: bool
    framework: str
    exit_code: int
    tests_passed: int = 0
    tests_failed: int = 0
    duration_s: float = 0.0
    stdout: str = ""
    stderr: str = ""
    unresolved_failures: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASSED" if self.success else "FAILED"
        return f"[{status}] {self.framework} | Passed: {self.tests_passed}, Failed: {self.tests_failed} (Exit code: {self.exit_code})"

class IndependentVerifier:
    """Subsystem 7: Verification and Quality Engine.
    
    Executes deterministic checks independently of the LLM.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()

    def detect_test_framework(self) -> str:
        """Inspects repository to detect active test runner."""
        if (self.workspace_root / "pytest.ini").exists() or (self.workspace_root / "conftest.py").exists():
            return "pytest"
        if (self.workspace_root / "package.json").exists():
            return "npm_test"
        if (self.workspace_root / "Cargo.toml").exists():
            return "cargo_test"
        # Check for tests directory with test_*.py
        test_dir = self.workspace_root / "tests"
        if test_dir.exists() and any(test_dir.glob("test_*.py")):
            return "pytest"
        return "python_unittest"

    def run_verification(self, custom_command: Optional[str] = None, timeout: int = 60) -> VerificationEvidence:
        """Executes test verification and extracts structured evidence."""
        framework = "custom" if custom_command else self.detect_test_framework()
        
        cmd = custom_command
        if not cmd:
            if framework == "pytest":
                cmd = "python -m pytest -v --tb=short"
            elif framework == "npm_test":
                cmd = "npm test"
            elif framework == "cargo_test":
                cmd = "cargo test"
            else:
                start_dir = "tests" if (self.workspace_root / "tests").exists() else "."
                cmd = f'python -m unittest discover -s {start_dir} -p "test_*.py"'

        try:
            start_time = os.times().elapsed
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self.workspace_root),
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            duration = os.times().elapsed - start_time
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            exit_code = proc.returncode

            # Parse Pytest Output
            passed = 0
            failed = 0
            failures = []

            # Match pytest summary lines like: "5 passed, 1 failed in 0.12s"
            pytest_match = re.search(r"(\d+)\s+passed", stdout)
            if pytest_match:
                passed = int(pytest_match.group(1))

            fail_match = re.search(r"(\d+)\s+failed", stdout)
            if fail_match:
                failed = int(fail_match.group(1))

            # Match python unittest output like: "Ran 5 tests in ... FAILED (failures=1)"
            if not pytest_match and "Ran " in stderr:
                ran_match = re.search(r"Ran (\d+) tests", stderr)
                if ran_match:
                    total = int(ran_match.group(1))
                    if exit_code == 0:
                        passed = total
                    else:
                        fail_count = re.search(r"failures=(\d+)", stderr)
                        failed = int(fail_count.group(1)) if fail_count else 1
                        passed = max(0, total - failed)

            if exit_code != 0:
                # Extract relevant failure traces
                lines = (stdout + "\n" + stderr).splitlines()
                failure_lines = [l for l in lines if "FAIL:" in l or "ERROR:" in l or "AssertionError" in l or "FAILED" in l]
                failures = failure_lines[:10]

            is_success = (exit_code == 0) and (failed == 0)
            return VerificationEvidence(
                success=is_success,
                framework=framework,
                exit_code=exit_code,
                tests_passed=passed,
                tests_failed=failed,
                duration_s=duration,
                stdout=stdout,
                stderr=stderr,
                unresolved_failures=failures
            )

        except subprocess.TimeoutExpired:
            return VerificationEvidence(
                success=False,
                framework=framework,
                exit_code=-1,
                stderr=f"Verification timed out after {timeout} seconds.",
                unresolved_failures=["Timeout expired during test run."]
            )
        except Exception as e:
            return VerificationEvidence(
                success=False,
                framework=framework,
                exit_code=-1,
                stderr=str(e),
                unresolved_failures=[f"Exception during test run: {str(e)}"]
            )
