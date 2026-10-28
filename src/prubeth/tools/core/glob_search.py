"""PRUBETH Glob Search Tool.

Finds files matching wildcard / glob patterns across the workspace with sorting and size metrics.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class GlobSearchTool(BaseTool):
    """Searches workspace files using glob patterns."""

    name = "glob_search"
    description = "Find files matching a glob pattern (e.g. '**/*.py', 'src/**/*.ts') in the workspace."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="pattern",
            type="string",
            description="The glob pattern to search for (e.g. '**/*.py', '*.json').",
            required=True
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Directory path to search within (default '.').",
            required=False,
            default="."
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maximum number of files to return (default 100).",
            required=False,
            default=100
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        pattern = str(args.get("pattern", "")).strip()
        if not pattern:
            return ToolResult(success=False, output="Error: Glob pattern cannot be empty.", exit_code=1)

        raw_path = str(args.get("path", ".") or ".")
        max_results = int(args.get("max_results", 100) or 100)

        workspace_root = Path(getattr(context, "workspace_root", os.getcwd())).resolve()
        target = (workspace_root / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()

        if not target.exists():
            return ToolResult(success=False, output=f"Error: Path not found: {raw_path}", exit_code=404)

        ignored_parts = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv", "dist", "build"}

        matched: List[Path] = []
        try:
            for p in target.glob(pattern):
                # Filter out ignored directories
                if any(part in ignored_parts for part in p.parts):
                    continue
                if p.is_file():
                    matched.append(p)
                    if len(matched) >= max_results:
                        break
        except Exception as e:
            return ToolResult(success=False, output=f"Error executing glob pattern '{pattern}': {e}", exit_code=500)

        if not matched:
            return ToolResult(
                success=True,
                output=f"No files matched glob pattern '{pattern}' in '{raw_path}'.",
                exit_code=0,
                metadata={"pattern": pattern, "count": 0}
            )

        rendered_items = []
        for p in matched:
            rel = p.relative_to(workspace_root) if p.is_relative_to(workspace_root) else p
            try:
                sz = p.stat().st_size
                sz_str = f"{sz / 1024:.1f} KB" if sz > 1024 else f"{sz} B"
            except Exception:
                sz_str = ""
            rendered_items.append(f"{rel} ({sz_str})" if sz_str else str(rel))

        summary = f"Found {len(matched)} file(s) matching '{pattern}':"
        rendered = f"{summary}\n" + "\n".join(rendered_items)

        return ToolResult(
            success=True,
            output=rendered,
            exit_code=0,
            metadata={
                "pattern": pattern,
                "count": len(matched),
                "files": [str(p) for p in matched]
            }
        )
