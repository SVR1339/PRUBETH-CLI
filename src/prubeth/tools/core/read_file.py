"""PRUBETH Read File Tool.

Safely reads files with line-number formatting, line ranges, and truncation budgeting.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class ReadFileTool(BaseTool):
    """Reads content from workspace files with line numbering and range slicing."""

    name = "read_file"
    description = "Read lines from a file in the workspace with line-number prefixes."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="The workspace-relative or absolute file path to read.",
            required=True
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="Optional 1-based start line index to begin reading from (default 1).",
            required=False,
            default=1
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="Optional 1-based end line index to stop reading at (inclusive).",
            required=False,
            default=None
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of characters to return before truncation.",
            required=False,
            default=None
        ),
        ToolParameter(
            name="encoding",
            type="string",
            description="Text encoding (default 'utf-8').",
            required=False,
            default="utf-8"
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return ToolResult(success=False, output="Error: File path cannot be empty.", exit_code=1)

        target = Path(raw_path)
        if not target.is_absolute() and context and hasattr(context, "workspace_root"):
            target = Path(context.workspace_root) / target

        if not target.is_file():
            return ToolResult(success=False, output=f"Error: File not found: {raw_path}", exit_code=404)

        encoding = args.get("encoding", "utf-8")
        try:
            with open(target, "r", encoding=encoding, errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return ToolResult(success=False, output=f"Error reading file '{raw_path}': {e}", exit_code=500)

        start_line = args.get("start_line", 1) or 1
        end_line = args.get("end_line")
        limit = args.get("limit")

        s_idx = max(0, start_line - 1)
        e_idx = len(lines) if end_line is None else min(len(lines), end_line)
        selected = lines[s_idx:e_idx]

        rendered = "".join([f"{s_idx + i + 1:4d} | {l}" for i, l in enumerate(selected)])

        truncated = False
        if limit and len(rendered) > limit:
            rendered = rendered[:limit] + f"\n... [Truncated {len(rendered) - limit} characters for context budgeting]"
            truncated = True

        return ToolResult(
            success=True,
            output=rendered,
            exit_code=0,
            metadata={
                "path": str(target),
                "total_lines": len(lines),
                "lines_rendered": len(selected),
                "truncated": truncated
            }
        )
