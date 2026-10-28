"""PRUBETH Automated Test Coverage Analysis Tool."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class CoverageAnalyserTool(BaseTool):
    """Analyses test coverage reports (coverage.py, lcov) or runs coverage dynamically."""

    name = "coverage_analyser"
    description = "Analyses test coverage reports and pinpoints uncovered lines, branches, and critical gaps."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="target_dir",
                type="string",
                description="Directory or file path to evaluate coverage for (e.g. 'src/prubeth').",
                required=False,
                default="src"
            ),
            ToolParameter(
                name="min_coverage",
                type="number",
                description="Minimum acceptable coverage percentage (e.g. 80.0).",
                required=False,
                default=0.0
            ),
            ToolParameter(
                name="report_file",
                type="string",
                description="Optional existing coverage report path (e.g. 'coverage.json' or 'lcov.info').",
                required=False,
                default=""
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        target_dir = arguments.get("target_dir", "src").strip()
        min_cov = float(arguments.get("min_coverage", 0.0))
        report_file = arguments.get("report_file", "").strip()

        # If a coverage report file was specified and exists
        if report_file and Path(report_file).exists():
            return self._parse_report_file(Path(report_file), min_cov)

        # Dynamic check with coverage.py if installed
        try:
            cmd = f"python -m coverage report --format=json"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                totals = data.get("totals", {})
                pct = totals.get("percent_covered", 0.0)
                files = data.get("files", {})

                file_summaries = []
                for fname, fmeta in files.items():
                    if target_dir in fname:
                        summary = fmeta.get("summary", {})
                        file_summaries.append({
                            "file": fname,
                            "coverage_pct": round(summary.get("percent_covered", 0.0), 1),
                            "missing_lines": fmeta.get("missing_lines", [])[:20]
                        })

                success = pct >= min_cov
                full_out = f"Total Project Coverage: {pct:.1f}%\n" + json.dumps(file_summaries[:20], indent=2)
                meta = {"total_coverage_pct": pct, "files_evaluated": len(file_summaries)}
                if success:
                    return ToolResult.ok(full_out, metadata=meta)
                else:
                    return ToolResult.fail(full_out, exit_code=1, metadata=meta)
        except Exception:
            pass

        # Static file estimation fallback
        return self._estimate_source_and_test_ratio(Path(target_dir), min_cov)

    def _parse_report_file(self, report_path: Path, min_cov: float) -> ToolResult:
        try:
            content = report_path.read_text(encoding="utf-8", errors="replace")
            if report_path.suffix == ".json":
                data = json.loads(content)
                pct = data.get("totals", {}).get("percent_covered", 0.0)
                success = pct >= min_cov
                msg = f"Report File: {report_path.name}\nTotal Coverage: {pct:.1f}%"
                if success:
                    return ToolResult.ok(msg, metadata={"coverage_pct": pct})
                else:
                    return ToolResult.fail(f"Coverage {pct:.1f}% is below minimum threshold {min_cov:.1f}%.\n" + msg, exit_code=1, metadata={"coverage_pct": pct})
        except Exception as e:
            return ToolResult.fail(f"Failed parsing report: {str(e)}", exit_code=1)

        return ToolResult.ok(f"Loaded coverage report from {report_path}")

    def _estimate_source_and_test_ratio(self, src_path: Path, min_cov: float) -> ToolResult:
        """Estimates test ratio based on source LOC vs test LOC."""
        src_files = list(src_path.rglob("*.py")) if src_path.exists() else []
        test_path = Path("tests")
        test_files = list(test_path.rglob("*.py")) if test_path.exists() else []

        src_lines = sum(len(f.read_text(encoding="utf-8", errors="replace").splitlines()) for f in src_files)
        test_lines = sum(len(f.read_text(encoding="utf-8", errors="replace").splitlines()) for f in test_files)

        ratio = (test_lines / src_lines * 100) if src_lines > 0 else 0.0

        summary = (
            f"Static Test Ratio Assessment:\n"
            f"  Source Lines of Code: {src_lines:,} ({len(src_files)} files)\n"
            f"  Test Lines of Code:   {test_lines:,} ({len(test_files)} files)\n"
            f"  Test-to-Code Ratio:   {ratio:.1f}%\n"
        )
        return ToolResult.ok(
            summary,
            metadata={
                "src_lines": src_lines,
                "test_lines": test_lines,
                "ratio_pct": round(ratio, 1)
            }
        )
