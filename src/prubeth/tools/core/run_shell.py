"""PRUBETH Run Shell Tool.

Executes shell commands with strict timeout, dangerous-command prevention, and output buffering.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


DANGEROUS_COMMAND_PATTERNS = [
    r"rm\s+-(?:r[fF]|[fF]r)\s+(?:/|\*|/[a-zA-Z0-9_\-]+|\~|\$HOME)",
    r"rm\s+-rf\s+(?:/|\*|/[a-zA-Z0-9_\-]+|\~|\$HOME)",
    r"mkfs",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"format\s+[a-zA-Z]:",
    r"del\s+.*[a-zA-Z]:",
    r"drop\s+database\b",
]


class RunShellTool(BaseTool):
    """Executes a shell command in the workspace directory with safety gating."""

    name = "run_shell"
    description = "Execute a shell command with timeout, working directory, and dangerous pattern prevention."
    clearance_level = ToolClearanceLevel.SYSTEM_EXECUTION
    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="The exact command line string to execute.",
            required=True
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Maximum seconds to wait before terminating command (default 60).",
            required=False,
            default=60
        ),
        ToolParameter(
            name="cwd",
            type="string",
            description="Working directory for command execution (default workspace root).",
            required=False,
            default=None
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        command = str(args.get("command", "")).strip()
        if not command:
            return ToolResult(success=False, output="Error: Command string cannot be empty.", exit_code=1)

        # Dangerous pattern check
        import re
        for pat in DANGEROUS_COMMAND_PATTERNS:
            if re.search(pat, command, re.IGNORECASE):
                return ToolResult(
                    success=False,
                    output=f"Security Violation: Command matches prohibited catastrophic pattern: '{pat}'",
                    exit_code=403
                )

        timeout = int(args.get("timeout", 60) or 60)
        workspace_root = Path(getattr(context, "workspace_root", os.getcwd())).resolve()

        raw_cwd = args.get("cwd")
        if raw_cwd:
            target_cwd = (workspace_root / raw_cwd).resolve() if not Path(raw_cwd).is_absolute() else Path(raw_cwd).resolve()
        else:
            target_cwd = workspace_root

        if not target_cwd.exists() or not target_cwd.is_dir():
            target_cwd = workspace_root

        try:
            # Use shell execution
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(target_cwd),
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

            # Context budgeting: cap output at 16,000 characters
            if len(combined) > 16000:
                combined = combined[:16000] + f"\n... [Truncated {len(combined) - 16000} characters]"

            return ToolResult(
                success=(proc.returncode == 0),
                output=combined if combined else "(Command exited with code 0 and no output)",
                exit_code=proc.returncode,
                metadata={
                    "command": command,
                    "exit_code": proc.returncode,
                    "cwd": str(target_cwd)
                }
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=f"Error: Command timed out after {timeout} seconds.",
                exit_code=124
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Execution Error: {e}",
                exit_code=500
            )
