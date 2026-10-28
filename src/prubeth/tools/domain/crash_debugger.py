"""PRUBETH Automated Crash & Traceback Debugger Tool."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class CrashDebuggerTool(BaseTool):
    """Parses exception stack traces, pinpoints root failure frames, and loads source contexts."""

    name = "crash_debugger"
    description = "Parses raw stack traces (Python, JS/TS, Go, Rust), pinpoints failing frames, and extracts source context."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="traceback",
                type="string",
                description="Raw error output or exception stack trace to analyse.",
                required=True
            ),
            ToolParameter(
                name="context_lines",
                type="integer",
                description="Number of source lines to inspect surrounding the failure line (default 5).",
                required=False,
                default=5
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        tb_text = arguments.get("traceback", "").strip()
        ctx_lines = int(arguments.get("context_lines", 5))

        if not tb_text:
            return ToolResult.fail("No traceback provided.", exit_code=1)

        frames = self._parse_frames(tb_text)
        exception_info = self._extract_exception_info(tb_text)

        # Enhance frames with source lines if file exists locally
        for f in frames:
            p = Path(f["file"])
            if p.is_file():
                try:
                    all_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                    target_idx = f["line"] - 1
                    start = max(0, target_idx - ctx_lines)
                    end = min(len(all_lines), target_idx + ctx_lines + 1)
                    snippet = []
                    for i in range(start, end):
                        prefix = ">>>" if i == target_idx else "   "
                        snippet.append(f"{prefix} {i+1:4d} | {all_lines[i]}")
                    f["source_context"] = "\n".join(snippet)
                except Exception:
                    f["source_context"] = None

        root_frame = frames[-1] if frames else None

        summary_parts = [
            f"Crash Analysis Summary:",
            f"  Exception:   {exception_info.get('type', 'UnknownError')}: {exception_info.get('message', '')}",
            f"  Total Frames: {len(frames)}",
        ]
        if root_frame:
            summary_parts.append(
                f"  Root Failure Locus: {root_frame['file']}:{root_frame['line']} in `{root_frame.get('scope', '?')}`"
            )
            if root_frame.get("source_context"):
                summary_parts.append("\nSource Context:")
                summary_parts.append(root_frame["source_context"])

        return ToolResult.ok(
            "\n".join(summary_parts),
            metadata={
                "exception": exception_info,
                "frames": frames,
                "root_frame": root_frame
            }
        )

    def _parse_frames(self, tb: str) -> List[Dict[str, Any]]:
        frames: List[Dict[str, Any]] = []

        # Python pattern: File "path/to/file.py", line 123, in func_name
        py_matches = re.finditer(r'File "([^"]+)", line (\d+)(?:, in (\w+))?', tb)
        for m in py_matches:
            frames.append({
                "language": "python",
                "file": m.group(1),
                "line": int(m.group(2)),
                "scope": m.group(3) or "<module>"
            })

        # JS / Node pattern: at functionName (/path/to/file.js:123:45)
        js_matches = re.finditer(r'at (?:([a-zA-Z0-9_\.<>]+)\s+)?\(([^:]+):(\d+):\d+\)', tb)
        for m in js_matches:
            frames.append({
                "language": "javascript",
                "file": m.group(2),
                "line": int(m.group(3)),
                "scope": m.group(1) or "<anonymous>"
            })

        return frames

    def _extract_exception_info(self, tb: str) -> Dict[str, str]:
        lines = [l.strip() for l in tb.splitlines() if l.strip()]
        if not lines:
            return {"type": "Unknown", "message": ""}

        # Last non-empty line often holds ErrorType: message
        last = lines[-1]
        m = re.match(r"^([a-zA-Z0-9_]+(?:Error|Exception|Warning|Fault))(?::\s*(.*))?$", last)
        if m:
            return {"type": m.group(1), "message": m.group(2) or ""}

        return {"type": "Error", "message": last}
