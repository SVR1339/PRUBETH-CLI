"""PRUBETH Git Log Tool.

Returns structured git commit history (hash, author, date, message).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class GitLogTool(BaseTool):
    """Retrieves formatted commit history from the repository."""

    name = "git_log"
    description = "Show commit logs and recent revisions in the repository."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="max_count",
            type="integer",
            description="Maximum number of commits to return (default 10).",
            required=False,
            default=10
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Optional file or directory path to limit history.",
            required=False,
            default=None
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        workspace_root = str(getattr(context, "workspace_root", os.getcwd()))
        max_count = int(args.get("max_count", 10) or 10)
        path_filter = args.get("path")

        cmd = ["git", "log", f"-n{max_count}", "--oneline", "--decorate"]
        if path_filter:
            cmd.extend(["--", str(path_filter)])

        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace_root,
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
                    return ToolResult(success=False, output="Notice: Current workspace is not a Git repository.", exit_code=proc.returncode)
                return ToolResult(success=False, output=f"Git Error: {err}", exit_code=proc.returncode)

            log_output = proc.stdout.strip()
            return ToolResult(
                success=True,
                output=log_output if log_output else "No commits found in repository.",
                exit_code=0,
                metadata={"max_count": max_count}
            )
        except FileNotFoundError:
            return ToolResult(success=False, output="Notice: Git command line binary is not installed.", exit_code=127)
        except Exception as e:
            return ToolResult(success=False, output=f"Error inspecting git log: {e}", exit_code=500)
