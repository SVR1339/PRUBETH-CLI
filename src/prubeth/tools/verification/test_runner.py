"""PRUBETH Unified Polyglot Test Runner Tool."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class TestRunnerTool(BaseTool):
    """Executes test frameworks (pytest, npm test, cargo test, go test) and returns structured pass/fail analytics."""

    __test__ = False
    name = "test_runner"
    description = "Executes unit/integration tests (pytest, npm, cargo, go) and extracts structured pass/fail diagnostics."
    clearance_level = ToolClearanceLevel.SYSTEM_EXECUTION

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="framework",
                type="string",
                description="Test framework: 'pytest', 'npm', 'cargo', 'go', or 'custom'.",
                required=False,
                default="pytest"
            ),
            ToolParameter(
                name="target",
                type="string",
                description="Specific test path, file, or filter pattern (e.g. 'tests/test_auth.py::test_login').",
                required=False,
                default=""
            ),
            ToolParameter(
                name="extra_args",
                type="string",
                description="Additional command-line arguments to pass to test runner.",
                required=False,
                default=""
            ),
            ToolParameter(
                name="timeout_s",
                type="integer",
                description="Command timeout in seconds (default 120s).",
                required=False,
                default=120
            ),
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        framework = arguments.get("framework", "pytest").lower()
        target = arguments.get("target", "").strip()
        extra_args = arguments.get("extra_args", "").strip()
        timeout_s = int(arguments.get("timeout_s", 120))

        if framework == "pytest":
            cmd = f"python -m pytest {target} {extra_args} -v --tb=short"
        elif framework in ("npm", "jest", "vitest"):
            cmd = f"npm test -- {target} {extra_args}"
        elif framework == "cargo":
            cmd = f"cargo test {target} {extra_args}"
        elif framework == "go":
            cmd = f"go test {target or './...'} {extra_args}"
        else:
            cmd = f"{target} {extra_args}".strip()

        if not cmd:
            return ToolResult.fail("No test command or target specified.", exit_code=1)

        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                encoding="utf-8",
                errors="replace"
            )
            raw_out = (proc.stdout + "\n" + proc.stderr).strip()
            parsed = self.parse_test_output(raw_out, framework)

            if proc.returncode == 0:
                return ToolResult.ok(raw_out, metadata={"command": cmd, "returncode": 0, "summary": parsed})
            else:
                return ToolResult.fail(raw_out or proc.stderr, exit_code=proc.returncode, metadata={"command": cmd, "returncode": proc.returncode, "summary": parsed})
        except subprocess.TimeoutExpired:
            return ToolResult.fail(f"Test run timed out after {timeout_s} seconds.", exit_code=124)
        except Exception as e:
            return ToolResult.fail(f"Execution failed: {str(e)}", exit_code=1)

    @classmethod
    def parse_test_output(cls, output: str, framework: str = "pytest") -> Dict[str, Any]:
        """Parses stdout/stderr into structured test summary counts and failure loci."""
        res = {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "total": 0,
            "failures": []
        }

        if framework == "pytest":
            # Pytest summary: e.g. "== 45 passed, 2 failed in 3.12s =="
            summary_match = re.search(r"==+\s*(.*?)\s*in\s+[\d\.]+s\s*==+", output)
            if summary_match:
                s_text = summary_match.group(1)
                for part in s_text.split(","):
                    p = part.strip()
                    m = re.match(r"(\d+)\s+([a-zA-Z]+)", p)
                    if m:
                        cnt = int(m.group(1))
                        status = m.group(2).lower()
                        if "pass" in status:
                            res["passed"] = cnt
                        elif "fail" in status:
                            res["failed"] = cnt
                        elif "error" in status:
                            res["errors"] = cnt
                        elif "skip" in status:
                            res["skipped"] = cnt

            # Pytest FAILED items: e.g. "FAILED tests/test_foo.py::test_bar"
            failed_items = re.findall(r"FAILED\s+([^\s]+)", output)
            for item in failed_items:
                res["failures"].append({"test_id": item, "reason": "FAILED"})

            res["total"] = res["passed"] + res["failed"] + res["errors"] + res["skipped"]

        return res
