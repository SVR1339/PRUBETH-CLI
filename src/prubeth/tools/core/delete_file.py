"""PRUBETH Delete File Tool.

Safely removes files or directories within workspace boundaries, preventing accidental root deletion.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class DeleteFileTool(BaseTool):
    """Safely deletes a file or directory within workspace bounds."""

    name = "delete_file"
    description = "Delete a file or directory inside the workspace."
    clearance_level = ToolClearanceLevel.WORKSPACE_MUTATION
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="The workspace-relative or absolute path of the file or directory to delete.",
            required=True
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Whether to delete a directory and all its contents recursively (default False).",
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
            return ToolResult(success=False, output="Error: Path cannot be empty.", exit_code=1)

        target = Path(raw_path)
        workspace_root = Path(
            getattr(context, "workspace_root", None)
            or getattr(self, "workspace_root", None)
            or os.getcwd()
        ).resolve()

        if not target.is_absolute():
            target = (workspace_root / target).resolve()
        else:
            target = target.resolve()

        # Workspace boundary check
        try:
            target.relative_to(workspace_root)
        except ValueError:
            return ToolResult(
                success=False,
                output=f"Security Violation: Target path '{raw_path}' escapes workspace root '{workspace_root}'.",
                exit_code=403
            )

        # Invariant: Prevent deletion of workspace root itself
        if target == workspace_root:
            return ToolResult(
                success=False,
                output="Security Violation: Cannot delete the entire workspace root.",
                exit_code=403
            )

        # Invariant: Prevent deletion of .git
        if target.name == ".git":
            return ToolResult(
                success=False,
                output="Security Violation: Deletion of .git repository metadata is prohibited.",
                exit_code=403
            )

        if not target.exists():
            return ToolResult(success=False, output=f"Error: Path does not exist: {raw_path}", exit_code=404)

        try:
            if target.is_file():
                target.unlink()
                return ToolResult(
                    success=True,
                    output=f"Successfully deleted file: {raw_path}",
                    exit_code=0,
                    metadata={"path": str(target), "type": "file"}
                )
            elif target.is_dir():
                recursive = bool(args.get("recursive", False))
                if not recursive:
                    # Check if empty
                    if any(target.iterdir()):
                        return ToolResult(
                            success=False,
                            output=f"Error: Directory '{raw_path}' is not empty. Set recursive=True to delete.",
                            exit_code=400
                        )
                    target.rmdir()
                else:
                    shutil.rmtree(target)
                return ToolResult(
                    success=True,
                    output=f"Successfully deleted directory: {raw_path}",
                    exit_code=0,
                    metadata={"path": str(target), "type": "directory", "recursive": recursive}
                )
            else:
                return ToolResult(success=False, output=f"Error: Path '{raw_path}' is neither file nor directory.", exit_code=400)
        except Exception as e:
            return ToolResult(success=False, output=f"Error deleting '{raw_path}': {e}", exit_code=500)
