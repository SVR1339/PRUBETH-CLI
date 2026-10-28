"""PRUBETH List Directory Tool.

Lists workspace directory contents with metadata (file/directory tags, sizes, permissions).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class ListDirTool(BaseTool):
    """Lists files and subdirectories with sizes and metadata."""

    name = "list_dir"
    description = "List entries in a directory with file sizes and type indicators."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="The workspace-relative or absolute directory path to list (defaults to '.').",
            required=False,
            default="."
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Whether to list subdirectories recursively (default False).",
            required=False,
            default=False
        ),
        ToolParameter(
            name="max_depth",
            type="integer",
            description="Maximum recursion depth when recursive=True (default 2).",
            required=False,
            default=2
        ),
        ToolParameter(
            name="show_hidden",
            type="boolean",
            description="Whether to include hidden files starting with '.' (default False).",
            required=False,
            default=False
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        raw_path = str(args.get("path", ".") or ".")
        target = Path(raw_path)
        if not target.is_absolute() and context and hasattr(context, "workspace_root"):
            target = Path(context.workspace_root) / target

        if not target.exists():
            return ToolResult(success=False, output=f"Error: Directory not found: {raw_path}", exit_code=404)
        if not target.is_dir():
            return ToolResult(success=False, output=f"Error: Path is not a directory: {raw_path}", exit_code=400)

        recursive = bool(args.get("recursive", False))
        max_depth = int(args.get("max_depth", 2) or 2)
        show_hidden = bool(args.get("show_hidden", False))

        ignored_dirs = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv"}

        entries: List[str] = []
        file_count = 0
        dir_count = 0

        def scan(current_dir: Path, current_depth: int):
            nonlocal file_count, dir_count
            if current_depth > max_depth:
                return

            try:
                items = sorted(list(current_dir.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
            except Exception as e:
                entries.append(f"  [ACCESS DENIED: {e}]")
                return

            for item in items:
                if not show_hidden and item.name.startswith("."):
                    continue
                if item.is_dir() and item.name in ignored_dirs and not show_hidden:
                    continue

                rel = item.relative_to(target)
                indent = "  " * (current_depth - 1)
                if item.is_dir():
                    dir_count += 1
                    entries.append(f"{indent}[DIR]  {rel}/")
                    if recursive:
                        scan(item, current_depth + 1)
                else:
                    file_count += 1
                    try:
                        sz = item.stat().st_size
                        if sz > 1024 * 1024:
                            sz_str = f"{sz / (1024 * 1024):.1f} MB"
                        elif sz > 1024:
                            sz_str = f"{sz / 1024:.1f} KB"
                        else:
                            sz_str = f"{sz} B"
                    except Exception:
                        sz_str = "unknown"
                    entries.append(f"{indent}[FILE] {rel} ({sz_str})")

        scan(target, 1)

        summary = f"Total: {dir_count} directories, {file_count} files in '{raw_path}'"
        rendered = f"{summary}\n" + "\n".join(entries) if entries else f"{summary}\n(empty directory)"

        return ToolResult(
            success=True,
            output=rendered,
            exit_code=0,
            metadata={
                "path": str(target),
                "directories": dir_count,
                "files": file_count,
            }
        )
