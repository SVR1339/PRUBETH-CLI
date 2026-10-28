"""PRUBETH Independent Verification & Polyglot Quality Engine (SE 3.0).

Executes deterministic test and lint checks independently of the LLM across
Python, Rust, Go, TypeScript/JavaScript, Java, C#, C/C++, Dart, PHP, and Ruby.
"""

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
    
    Executes deterministic checks independently of the LLM across polyglot ecosystems.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()

    def detect_test_framework(self) -> str:
        """Inspects repository to detect active test runner across polyglot ecosystems."""
        if (self.workspace_root / "pytest.ini").exists() or (self.workspace_root / "conftest.py").exists():
            return "pytest"
        if (self.workspace_root / "package.json").exists():
            return "npm_test"
        if (self.workspace_root / "Cargo.toml").exists():
            return "cargo_test"
        test_dir = self.workspace_root / "tests"
        if test_dir.exists() and any(test_dir.glob("test_*.py")):
            return "pytest"

        from prubeth.polyglot.manager import PolyglotLanguageManager
        mgr = PolyglotLanguageManager(self.workspace_root)
        pref = mgr.get_configured_language()
        if pref not in ["auto", "python"]:
            return pref

        stack = mgr.resolve_active_stack()
        if stack.id == "python":
            return "python_unittest"
        return stack.id

    def run_verification(self, custom_command: Optional[str] = None, timeout: int = 60) -> VerificationEvidence:
        """Executes test verification and extracts structured evidence."""
        from prubeth.polyglot.manager import PolyglotLanguageManager
        mgr = PolyglotLanguageManager(self.workspace_root)
        active_stack = mgr.resolve_active_stack()

        framework = "custom" if custom_command else active_stack.id
        cmd = custom_command or active_stack.default_test_cmd

        # Specific Python legacy fallback if pytest.ini / test_*.py not present
        if not custom_command and active_stack.id == "python":
            if not ((self.workspace_root / "pytest.ini").exists() or (self.workspace_root / "conftest.py").exists() or any((self.workspace_root / "tests").glob("test_*.py") if (self.workspace_root / "tests").exists() else [])):
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

            passed = 0
            failed = 0
            failures = []
            combined = stdout + "\n" + stderr

            # 1. Pytest Parsing
            pytest_match = re.search(r"(\d+)\s+passed", combined)
            if pytest_match:
                passed = int(pytest_match.group(1))
            fail_match = re.search(r"(\d+)\s+failed", combined)
            if fail_match:
                failed = int(fail_match.group(1))

            # 2. Cargo (Rust) Parsing: "test result: ok. 5 passed; 0 failed"
            cargo_match = re.search(r"test result:\s*\w+\.\s*(\d+)\s+passed;\s*(\d+)\s+failed", combined)
            if cargo_match:
                passed = int(cargo_match.group(1))
                failed = int(cargo_match.group(2))

            # 3. Go Test Parsing: count "--- PASS:" vs "--- FAIL:"
            if "--- PASS:" in combined or "--- FAIL:" in combined:
                passed = len(re.findall(r"--- PASS:", combined))
                failed = len(re.findall(r"--- FAIL:", combined))

            # 4. Jest / Vitest Parsing: "Tests: 4 passed, 4 total"
            jest_match = re.search(r"Tests:\s+(\d+)\s+passed(?:,\s+(\d+)\s+failed)?", combined)
            if jest_match:
                passed = int(jest_match.group(1))
                failed = int(jest_match.group(2)) if jest_match.group(2) else 0

            # 5. Dotnet Parsing: "Passed! - Failed: 0, Passed: 5"
            dotnet_match = re.search(r"Passed:\s*(\d+)(?:,\s*Failed:\s*(\d+))?", combined)
            if dotnet_match and not pytest_match:
                passed = int(dotnet_match.group(1))
                failed = int(dotnet_match.group(2)) if dotnet_match.group(2) else 0

            # 6. Python unittest fallback: "Ran 5 tests in ... FAILED (failures=1)"
            if not pytest_match and "Ran " in combined:
                ran_match = re.search(r"Ran (\d+) tests", combined)
                if ran_match:
                    total = int(ran_match.group(1))
                    if exit_code == 0:
                        passed = total
                    else:
                        fail_count = re.search(r"failures=(\d+)", combined)
                        failed = int(fail_count.group(1)) if fail_count else 1
                        passed = max(0, total - failed)

            # Generic fallback if no specific regex matched
            if passed == 0 and failed == 0:
                if exit_code == 0:
                    passed = 1
                else:
                    failed = 1

            if exit_code != 0:
                lines = combined.splitlines()
                failure_lines = [l for l in lines if any(k in l for k in ["FAIL:", "ERROR:", "AssertionError", "FAILED", "panic:", "error[E"])]
                failures = failure_lines[:10]

            is_success = (exit_code == 0) and (failed == 0)
            return VerificationEvidence(
                success=is_success,
                framework=framework,
                exit_code=exit_code,
                tests_passed=passed,
                tests_failed=failed,
                duration_s=round(duration, 3),
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
