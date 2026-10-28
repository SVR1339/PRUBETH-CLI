"""FindDeadCodeTool: Identifies unused functions, methods, and symbols with zero callers."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class FindDeadCodeTool(BaseTool):
    """Detects potentially unused functions, methods, and classes that have zero callers."""

    name = "find_dead_code"
    description = "Scans the workspace call graph to identify unused functions, methods, and classes with zero internal callers."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="ignore_tests",
            type="boolean",
            description="Whether to ignore test files and fixtures (default true).",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="ignore_entrypoints",
            type="boolean",
            description="Whether to ignore common CLI and server entrypoint names like main, run, handler (default true).",
            required=False,
            default=True,
        ),
    ]

    def execute(self, args: Optional[Dict[str, Any]] = None, context: Any = None, **kwargs) -> ToolResult:
        params = dict(args or {}) | kwargs
        ignore_tests = bool(params.get("ignore_tests", True))
        ignore_entrypoints = bool(params.get("ignore_entrypoints", True))

        ws_root = Path(getattr(context, "workspace_root", None) or self.workspace_root)
        index = IncrementalCodeIndex(ws_root)
        index.sync_index()
        graph = index.load_graph()

        dead_symbols = graph.find_dead_code(
            ignore_tests=ignore_tests,
            ignore_entrypoints=ignore_entrypoints,
        )

        if not dead_symbols:
            return ToolResult.ok(
                "No dead code or unreferenced symbols detected. High invocation cohesion.",
                metadata={"dead_symbols_count": 0},
            )

        lines = [f"Found {len(dead_symbols)} potentially uncalled symbol(s):"]
        for s in dead_symbols[:50]:
            parent_info = f" (in class {s.parent_symbol})" if s.parent_symbol else ""
            lines.append(f"  - [{s.kind.value}] {s.name}{parent_info} in {s.file_path}:L{s.start_line} (`{s.signature}`)")

        if len(dead_symbols) > 50:
            lines.append(f"\n... and {len(dead_symbols) - 50} more uncalled symbols.")

        return ToolResult.ok(
            "\n".join(lines),
            metadata={
                "dead_symbols_count": len(dead_symbols),
                "dead_symbols": [s.to_dict() for s in dead_symbols[:50]],
            },
        )
