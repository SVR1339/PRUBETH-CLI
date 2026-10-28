"""PRUBETH Run Python Tool.

Executes inline Python code snippets in an isolated subprocess.
"""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class RunPythonTool(BaseTool):
    """Executes a Python snippet in an isolated subprocess using current interpreter."""

    name = "run_python"
    description = "Execute a Python script or snippet in an isolated subprocess with stdout/stderr capture."
    clearance_level = ToolClearanceLevel.SYSTEM_EXECUTION
    parameters = [
        ToolParameter(
            name="code",
            type="string",
            description="The Python code to execute.",
            required=True
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Maximum seconds to wait before terminating execution (default 30).",
            required=False,
            default=30
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        code = str(args.get("code", "")).strip()
        if not code:
            return ToolResult(success=False, output="Error: Python code cannot be empty.", exit_code=1)

        timeout = int(args.get("timeout", 30) or 30)
        workspace_root = str(getattr(context, "workspace_root", "."))

        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            combined = stdout
            if stderr:
                combined += ("\n[STDERR]\n" if combined else "") + stderr

            if len(combined) > 16000:
                combined = combined[:16000] + f"\n... [Truncated {len(combined) - 16000} characters]"

            return ToolResult(
                success=(proc.returncode == 0),
                output=combined if combined else "(Executed successfully with no output)",
                exit_code=proc.returncode,
                metadata={"exit_code": proc.returncode}
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=f"Error: Python execution timed out after {timeout} seconds.",
                exit_code=124
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Execution Error: {e}",
                exit_code=500
            )
