"""PRUBETH Git Diff Tool.

Inspects unified differences across working directory, staged changes, or commits.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class GitDiffTool(BaseTool):
    """Produces unified diffs for staged or unstaged modifications."""

    name = "git_diff"
    description = "View changes between commits, commit and working tree, etc."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="staged",
            type="boolean",
            description="Whether to view staged changes (--staged/--cached) (default False).",
            required=False,
            default=False
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Optional file or directory path to limit diff.",
            required=False,
            default=None
        ),
        ToolParameter(
            name="commit",
            type="string",
            description="Optional commit ref (e.g. 'HEAD~1', 'main') to diff against.",
            required=False,
            default=None
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        workspace_root = str(getattr(context, "workspace_root", os.getcwd()))
        staged = bool(args.get("staged", False))
        commit = args.get("commit")
        path_filter = args.get("path")

        cmd = ["git", "diff"]
        if staged:
            cmd.append("--staged")
        if commit:
            cmd.append(str(commit))
        if path_filter:
            cmd.extend(["--", str(path_filter)])

        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
                encoding="utf-8",
                errors="replace"
            )
            if proc.returncode != 0:
                err = proc.stderr.strip()
                if "not a git repository" in err.lower():
                    return ToolResult(success=False, output="Notice: Current workspace is not a Git repository.", exit_code=proc.returncode)
                return ToolResult(success=False, output=f"Git Error: {err}", exit_code=proc.returncode)

            diff = proc.stdout
            if not diff:
                scope = "staged changes" if staged else "working tree changes"
                return ToolResult(success=True, output=f"No {scope} detected.", exit_code=0)

            # Cap diff size at 24,000 characters
            if len(diff) > 24000:
                diff = diff[:24000] + f"\n... [Diff truncated: {len(diff) - 24000} additional characters]"

            return ToolResult(success=True, output=diff, exit_code=0)
        except FileNotFoundError:
            return ToolResult(success=False, output="Notice: Git command line binary is not installed.", exit_code=127)
        except Exception as e:
            return ToolResult(success=False, output=f"Error running git diff: {e}", exit_code=500)
