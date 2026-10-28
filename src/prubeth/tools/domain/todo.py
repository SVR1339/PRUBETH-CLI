"""PRUBETH Codebase Task & Technical Debt Scanner Tool."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel

TODO_PATTERN = re.compile(
    r"(?i)\b(TODO|FIXME|HACK|BUG|XXX|OPTIMISE|OPTIMIZE|NOTE)(?:\(([^)]+)\))?\s*[:\-]?\s*(.*)"
)

PRIORITY_MAP = {
    "BUG": "CRITICAL",
    "FIXME": "HIGH",
    "XXX": "HIGH",
    "HACK": "MEDIUM",
    "TODO": "MEDIUM",
    "OPTIMISE": "LOW",
    "OPTIMIZE": "LOW",
    "NOTE": "LOW",
}


class TodoTool(BaseTool):
    """Scans repository for TODO, FIXME, HACK, and technical debt markers with line locations."""

    name = "todo"
    description = "Discovers and catalogues TODO, FIXME, HACK, and BUG comments across the codebase."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Target directory or file path to scan (default current directory).",
                required=False,
                default="."
            ),
            ToolParameter(
                name="tag",
                type="string",
                description="Filter by specific tag: 'TODO', 'FIXME', 'HACK', 'BUG', or 'ALL'.",
                required=False,
                default="ALL"
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of items to return (default 50).",
                required=False,
                default=50
            ),
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path_str = arguments.get("path", ".").strip() or "."
        target_tag = arguments.get("tag", "ALL").upper().strip()
        limit = int(arguments.get("limit", 50))

        root = Path(path_str)
        if not root.exists():
            return ToolResult.fail(f"Path '{path_str}' does not exist.", exit_code=1)

        ignored_dirs = {".git", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}

        items: List[Dict[str, Any]] = []

        if root.is_file():
            files = [root]
        else:
            files = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in ignored_dirs and not d.startswith(".")]
                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in (".py", ".ts", ".js", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".md", ".sh"):
                        files.append(Path(dirpath) / fn)

        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                for idx, line in enumerate(content.splitlines(), start=1):
                    match = TODO_PATTERN.search(line)
                    if match:
                        tag = match.group(1).upper()
                        if target_tag != "ALL" and tag != target_tag:
                            continue

                        author = match.group(2) or ""
                        comment_text = match.group(3).strip()
                        priority = PRIORITY_MAP.get(tag, "MEDIUM")

                        items.append({
                            "tag": tag,
                            "priority": priority,
                            "file": str(f.as_posix()),
                            "line": idx,
                            "author": author,
                            "text": comment_text,
                            "raw_line": line.strip()
                        })
                        if len(items) >= limit:
                            break
            except Exception:
                continue

            if len(items) >= limit:
                break

        summary_lines = [f"Found {len(items)} technical debt annotations in '{path_str}':"]
        for it in items:
            author_str = f" [{it['author']}]" if it['author'] else ""
            summary_lines.append(
                f"- [{it['priority']}] {it['tag']}{author_str} at {it['file']}:{it['line']} -> {it['text']}"
            )

        return ToolResult.ok(
            "\n".join(summary_lines),
            metadata={"items": items, "count": len(items)}
        )
