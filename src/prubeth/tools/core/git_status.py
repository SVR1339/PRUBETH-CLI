"""PRUBETH Git Status Tool.

Returns clean git status summary (staged, unstaged, untracked files).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class GitStatusTool(BaseTool):
    """Inspects the git working tree and returns short status summary."""

    name = "git_status"
    description = "Show the working tree status (modified, staged, and untracked files)."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Directory path to inspect (defaults to workspace root).",
            required=False,
            default="."
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        workspace_root = str(getattr(context, "workspace_root", os.getcwd()))
        raw_path = str(args.get("path", ".") or ".")
        target = Path(workspace_root) / raw_path if not Path(raw_path).is_absolute() else Path(raw_path)

        try:
            proc = subprocess.run(
                ["git", "status", "--short", "--branch"],
                cwd=str(target),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                encoding="utf-8",
                errors="replace"
            )
            if proc.returncode != 0:
                err = proc.stderr.strip()
                if "not a git repository" in err.lower():
                    return ToolResult(
                        success=False,
                        output="Notice: Current workspace directory is not a Git repository.",
                        exit_code=proc.returncode
                    )
                return ToolResult(success=False, output=f"Git Error: {err}", exit_code=proc.returncode)

            output = proc.stdout.strip()
            return ToolResult(
                success=True,
                output=output if output else "Clean working tree: no changes detected.",
                exit_code=0
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                output="Notice: Git command line binary is not installed or not found on system PATH.",
                exit_code=127
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Error inspecting git status: {e}", exit_code=500)
