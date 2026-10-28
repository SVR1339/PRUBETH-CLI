"""PRUBETH Automated Linting & Style Diagnostic Tool."""

from __future__ import annotations

import ast
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class LintCheckerTool(BaseTool):
    """Runs code linters (ruff, flake8, eslint, or built-in AST scanner) and returns structured diagnostics."""

    name = "lint_checker"
    description = "Checks code for syntax, style, and lint errors using ruff, eslint, or built-in AST inspection."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Target file or directory path to lint.",
                required=True
            ),
            ToolParameter(
                name="linter",
                type="string",
                description="Linter engine: 'ast' (built-in, zero-dependency), 'ruff', 'flake8', or 'eslint'.",
                required=False,
                default="ast"
            ),
            ToolParameter(
                name="fix",
                type="boolean",
                description="Whether to attempt automatic fixes if supported by linter (e.g. ruff --fix).",
                required=False,
                default=False
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path_str = arguments.get("path", "").strip()
        linter = arguments.get("linter", "ast").lower()
        fix = bool(arguments.get("fix", False))

        if not path_str:
            return ToolResult.fail("Missing target path to lint.", exit_code=1)

        p = Path(path_str)
        if not p.exists():
            return ToolResult.fail(f"Target path '{path_str}' does not exist.", exit_code=1)

        if linter == "ast":
            return self._run_ast_linter(p)

        # External linters
        if linter == "ruff":
            fix_flag = "--fix" if fix else ""
            cmd = f"ruff check {path_str} {fix_flag} --output-format=json"
        elif linter == "flake8":
            cmd = f"flake8 {path_str}"
        elif linter == "eslint":
            fix_flag = "--fix" if fix else ""
            cmd = f"npx eslint {path_str} {fix_flag} -f json"
        else:
            return self._run_ast_linter(p)

        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
            if proc.returncode == 0:
                return ToolResult.ok(proc.stdout or proc.stderr, metadata={"linter": linter, "command": cmd})
            else:
                return ToolResult.fail(proc.stdout or proc.stderr, exit_code=proc.returncode, metadata={"linter": linter, "command": cmd})
        except Exception as e:
            return ToolResult.fail(f"Failed to run linter '{linter}': {str(e)}", exit_code=1)

    def _run_ast_linter(self, target_path: Path) -> ToolResult:
        """Zero-dependency built-in AST syntax & style checker."""
        files = [target_path] if target_path.is_file() else list(target_path.rglob("*.py"))
        diagnostics: List[Dict[str, Any]] = []

        for f in files:
            if not f.name.endswith(".py"):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content, filename=str(f))

                # Simple structural inspections
                for node in ast.walk(tree):
                    # Check for bare except:
                    if isinstance(node, ast.ExceptHandler) and node.type is None:
                        diagnostics.append({
                            "file": str(f),
                            "line": node.lineno,
                            "col": node.col_offset,
                            "code": "E722",
                            "severity": "WARNING",
                            "message": "Do not use bare 'except'; specify Exception or specific error type."
                        })
                    # Check for assert False or assert 0
                    elif isinstance(node, ast.Assert):
                        if isinstance(node.test, ast.Constant) and not node.test.value:
                            diagnostics.append({
                                "file": str(f),
                                "line": node.lineno,
                                "col": node.col_offset,
                                "code": "B011",
                                "severity": "WARNING",
                                "message": "Do not assert False or falsy constant; raise an exception instead."
                            })
            except SyntaxError as e:
                diagnostics.append({
                    "file": str(f),
                    "line": e.lineno or 1,
                    "col": e.offset or 0,
                    "code": "E999",
                    "severity": "ERROR",
                    "message": f"SyntaxError: {e.msg}"
                })
            except Exception as e:
                diagnostics.append({
                    "file": str(f),
                    "line": 1,
                    "col": 0,
                    "code": "E000",
                    "severity": "ERROR",
                    "message": f"Read error: {str(e)}"
                })

        success = len([d for d in diagnostics if d["severity"] == "ERROR"]) == 0
        summary = f"Scanned {len(files)} files. Found {len(diagnostics)} issues ({len([d for d in diagnostics if d['severity'] == 'ERROR'])} errors, {len([d for d in diagnostics if d['severity'] == 'WARNING'])} warnings)."
        full_out = summary + "\n" + json.dumps(diagnostics, indent=2)

        if success:
            return ToolResult.ok(full_out, metadata={"diagnostics": diagnostics, "scanned_files": len(files)})
        else:
            return ToolResult.fail(full_out, exit_code=1, metadata={"diagnostics": diagnostics, "scanned_files": len(files)})
