"""PRUBETH Write File Tool.

Atomically creates or overwrites files with polyglot pre-flight syntax gating.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel
from prubeth.tools.file_ops import atomic_write_file
from prubeth.verification.polyglot import PolyglotSyntaxGate


class WriteFileTool(BaseTool):
    """Atomically writes content to a file with syntax safety gating."""

    name = "write_file"
    description = "Create a new file or completely overwrite an existing file atomically with safety validation."
    clearance_level = ToolClearanceLevel.WORKSPACE_MUTATION
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="The workspace-relative or absolute file path to create or overwrite.",
            required=True
        ),
        ToolParameter(
            name="content",
            type="string",
            description="The full content to write to the file.",
            required=True
        ),
        ToolParameter(
            name="encoding",
            type="string",
            description="Text encoding (default 'utf-8').",
            required=False,
            default="utf-8"
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force file write even if syntax gate detects flaws, logging an advisory instead of blocking (default False).",
            required=False,
            default=False
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return ToolResult(success=False, output="Error: File path cannot be empty.", exit_code=1)

        content = str(args.get("content", ""))
        encoding = args.get("encoding", "utf-8")
        force = bool(args.get("force", False))
        unrestricted = bool(
            getattr(context, "developer_mode", False) or
            getattr(context, "unrestricted_mode", False) or
            os.environ.get("PRUBETH_UNRESTRICTED_DEVELOPER_MODE") == "1"
        )

        target = Path(raw_path)
        if not target.is_absolute() and context and hasattr(context, "workspace_root"):
            target = Path(context.workspace_root) / target

        # Pre-Flight Polyglot Syntax Check
        syntax_ok, syntax_err = PolyglotSyntaxGate.validate_content(str(target), content)
        advisory = ""
        if not syntax_ok:
            if force or unrestricted:
                advisory = f" [Advisory: Syntax invariant notice: {syntax_err} (bypassed via force/developer clearance)]"
            else:
                return ToolResult(
                    success=False,
                    output=f"Error: Pre-flight syntax invariant failed: {syntax_err}",
                    exit_code=422
                )

        try:
            atomic_write_file(target, content, encoding=encoding)
            line_count = len(content.splitlines())
            meta = {
                "path": str(target),
                "bytes_written": len(content.encode(encoding, errors="replace")),
                "lines": line_count
            }
            if advisory:
                meta["syntax_advisory"] = syntax_err
                meta["forced"] = True

            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters ({line_count} lines) to {raw_path}{advisory}",
                exit_code=0,
                metadata=meta
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Error writing to file '{raw_path}': {e}",
                exit_code=500
            )
