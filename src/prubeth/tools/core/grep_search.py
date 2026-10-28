"""PRUBETH Grep Search Tool.

Fast multi-file text and regex pattern matching across workspace files with smart exclusions.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class GrepSearchTool(BaseTool):
    """Searches workspace files for literal text or regular expressions."""

    name = "grep_search"
    description = "Search for a regex or text query across files in the workspace."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="The regex or literal pattern to search for.",
            required=True
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Directory or file path to search within (default '.').",
            required=False,
            default="."
        ),
        ToolParameter(
            name="case_sensitive",
            type="boolean",
            description="Whether match should be case-sensitive (default False).",
            required=False,
            default=False
        ),
        ToolParameter(
            name="file_pattern",
            type="string",
            description="Glob filter for filenames (e.g. '*.py', '*.ts') (default '*').",
            required=False,
            default="*"
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maximum number of matching lines to return (default 100).",
            required=False,
            default=100
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        query = str(args.get("query", ""))
        if not query:
            return ToolResult(success=False, output="Error: Search query cannot be empty.", exit_code=1)

        raw_path = str(args.get("path", ".") or ".")
        case_sensitive = bool(args.get("case_sensitive", False))
        file_pattern = str(args.get("file_pattern", "*") or "*")
        max_results = int(args.get("max_results", 100) or 100)

        workspace_root = Path(getattr(context, "workspace_root", os.getcwd())).resolve()
        target = (workspace_root / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()

        if not target.exists():
            return ToolResult(success=False, output=f"Error: Path not found: {raw_path}", exit_code=404)

        # Compile regex
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags)
        except re.error as e:
            # Fallback to escaped literal if regex syntax error
            pattern = re.compile(re.escape(query), flags)

        ignored_dirs = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv", "dist", "build"}
        results: List[str] = []
        files_scanned = 0
        matches_found = 0

        files_to_search: List[Path] = []
        if target.is_file():
            files_to_search = [target]
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
                for f in files:
                    fp = Path(root) / f
                    if fp.match(file_pattern):
                        files_to_search.append(fp)

        truncated = False
        for fp in files_to_search:
            files_scanned += 1
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, 1):
                        if pattern.search(line):
                            matches_found += 1
                            rel_path = fp.relative_to(workspace_root) if fp.is_relative_to(workspace_root) else fp
                            results.append(f"{rel_path}:{line_no}: {line.rstrip()}")
                            if len(results) >= max_results:
                                truncated = True
                                break
            except Exception:
                continue

            if len(results) >= max_results:
                truncated = True
                break

        if not results:
            return ToolResult(
                success=True,
                output=f"No matches found for '{query}' across {files_scanned} files.",
                exit_code=0,
                metadata={"query": query, "files_scanned": files_scanned, "matches": 0}
            )

        summary = f"Found {matches_found} match(es) across {files_scanned} file(s) (showing top {len(results)}):"
        rendered = f"{summary}\n" + "\n".join(results)

        return ToolResult(
            success=True,
            output=rendered,
            exit_code=0,
            metadata={
                "query": query,
                "matches": matches_found,
                "files_scanned": files_scanned,
                "truncated": truncated or (matches_found > len(results))
            }
        )
