"""FindCallersTool: Locates all functions, methods, and files calling a target symbol."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class FindCallersTool(BaseTool):
    """Finds all functions and methods that call a specified target symbol."""

    name = "find_callers"
    description = "Locates all functions and methods across the workspace that call or invoke a specified symbol."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="symbol_name",
            type="string",
            description="Name of the function, method, or class whose callers to locate.",
            required=True,
        ),
    ]

    def execute(self, args: Optional[Dict[str, Any]] = None, context: Any = None, **kwargs) -> ToolResult:
        params = dict(args or {}) | kwargs
        symbol_name = str(params.get("symbol_name", "")).strip()
        if not symbol_name:
            return ToolResult.fail("Parameter 'symbol_name' cannot be empty.")

        ws_root = Path(getattr(context, "workspace_root", None) or self.workspace_root)
        index = IncrementalCodeIndex(ws_root)
        index.sync_index()
        graph = index.load_graph()

        callers = graph.find_callers(symbol_name)
        if not callers:
            return ToolResult.ok(
                f"No callers found calling '{symbol_name}'.",
                metadata={"callers_count": 0, "symbol_name": symbol_name},
            )

        lines = [f"Found {len(callers)} caller(s) for '{symbol_name}':"]
        for c in callers:
            parent_info = f" (in class {c.parent_symbol})" if c.parent_symbol else ""
            lines.append(f"  - [{c.kind.value}] {c.name}{parent_info} at {c.file_path}:L{c.start_line} (`{c.signature}`)")

        return ToolResult.ok(
            "\n".join(lines),
            metadata={
                "callers_count": len(callers),
                "symbol_name": symbol_name,
                "callers": [c.to_dict() for c in callers],
            },
        )
