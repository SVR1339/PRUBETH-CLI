"""PRUBETH Copy File Tool.

Safely copies files or directories within workspace boundaries.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class CopyFileTool(BaseTool):
    """Safely copies a file or directory tree within workspace bounds."""

    name = "copy_file"
    description = "Copy a file or directory from source to destination within the workspace."
    clearance_level = ToolClearanceLevel.WORKSPACE_MUTATION
    parameters = [
        ToolParameter(
            name="src",
            type="string",
            description="The source file or directory path.",
            required=True
        ),
        ToolParameter(
            name="dst",
            type="string",
            description="The destination file or directory path.",
            required=True
        ),
        ToolParameter(
            name="overwrite",
            type="boolean",
            description="Whether to overwrite existing destination (default False).",
            required=False,
            default=False
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        raw_src = str(args.get("src", "")).strip()
        raw_dst = str(args.get("dst", "")).strip()
        overwrite = bool(args.get("overwrite", False))

        if not raw_src or not raw_dst:
            return ToolResult(success=False, output="Error: Source and destination paths cannot be empty.", exit_code=1)

        workspace_root = Path(
            getattr(context, "workspace_root", None)
            or getattr(self, "workspace_root", None)
            or os.getcwd()
        ).resolve()

        src = (workspace_root / raw_src).resolve() if not Path(raw_src).is_absolute() else Path(raw_src).resolve()
        dst = (workspace_root / raw_dst).resolve() if not Path(raw_dst).is_absolute() else Path(raw_dst).resolve()

        # Workspace boundary check
        try:
            src.relative_to(workspace_root)
            dst.relative_to(workspace_root)
        except ValueError:
            return ToolResult(
                success=False,
                output="Security Violation: Source or destination path escapes workspace root.",
                exit_code=403
            )

        if not src.exists():
            return ToolResult(success=False, output=f"Error: Source does not exist: {raw_src}", exit_code=404)

        if dst.exists() and not overwrite:
            return ToolResult(success=False, output=f"Error: Destination already exists: {raw_dst} (set overwrite=True).", exit_code=409)

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copy2(src, dst)
                return ToolResult(
                    success=True,
                    output=f"Successfully copied file '{raw_src}' -> '{raw_dst}'",
                    exit_code=0,
                    metadata={"src": str(src), "dst": str(dst), "type": "file"}
                )
            elif src.is_dir():
                if dst.exists() and overwrite:
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                return ToolResult(
                    success=True,
                    output=f"Successfully copied directory '{raw_src}' -> '{raw_dst}'",
                    exit_code=0,
                    metadata={"src": str(src), "dst": str(dst), "type": "directory"}
                )
            else:
                return ToolResult(success=False, output=f"Error: Unsupported file type for '{raw_src}'", exit_code=400)
        except Exception as e:
            return ToolResult(success=False, output=f"Error copying '{raw_src}' -> '{raw_dst}': {e}", exit_code=500)
