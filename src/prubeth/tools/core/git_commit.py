"""PRUBETH Git Commit Tool.

Stages workspace modifications and creates atomic git commits.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class GitCommitTool(BaseTool):
    """Stages files and creates a new git commit with message."""

    name = "git_commit"
    description = "Record changes to the repository with a commit message."
    clearance_level = ToolClearanceLevel.WORKSPACE_MUTATION
    parameters = [
        ToolParameter(
            name="message",
            type="string",
            description="The commit log message.",
            required=True
        ),
        ToolParameter(
            name="files",
            type="array",
            description="List of specific files to stage (optional, stages all modified if empty).",
            required=False,
            default=None
        ),
        ToolParameter(
            name="all",
            type="boolean",
            description="Automatically stage tracked files that have been modified (default True).",
            required=False,
            default=True
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        msg = str(args.get("message", "")).strip()
        if not msg:
            return ToolResult(success=False, output="Error: Commit message cannot be empty.", exit_code=1)

        workspace_root = str(getattr(context, "workspace_root", os.getcwd()))
        files = args.get("files")
        stage_all = bool(args.get("all", True))

        try:
            # 1. Stage files
            if files and isinstance(files, list):
                add_cmd = ["git", "add"] + [str(f) for f in files]
            elif stage_all:
                add_cmd = ["git", "add", "-A"]
            else:
                add_cmd = None

            if add_cmd:
                add_proc = subprocess.run(
                    add_cmd,
                    cwd=workspace_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=20,
                    encoding="utf-8",
                    errors="replace"
                )
                if add_proc.returncode != 0:
                    return ToolResult(
                        success=False,
                        output=f"Git Add Failed: {add_proc.stderr.strip()}",
                        exit_code=add_proc.returncode
                    )

            # 2. Commit
            commit_proc = subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
                encoding="utf-8",
                errors="replace"
            )
            out = commit_proc.stdout.strip()
            err_out = commit_proc.stderr.strip()

            if commit_proc.returncode != 0:
                if "nothing to commit" in out.lower() or "nothing to commit" in err_out.lower():
                    return ToolResult(success=True, output="Notice: Nothing to commit, working tree clean.", exit_code=0)
                return ToolResult(success=False, output=f"Git Commit Failed: {err_out or out}", exit_code=commit_proc.returncode)

            return ToolResult(
                success=True,
                output=f"Successfully committed:\n{out}",
                exit_code=0,
                metadata={"message": msg}
            )
        except FileNotFoundError:
            return ToolResult(success=False, output="Notice: Git command line binary is not installed.", exit_code=127)
        except Exception as e:
            return ToolResult(success=False, output=f"Error executing git commit: {e}", exit_code=500)
