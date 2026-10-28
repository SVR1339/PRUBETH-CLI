"""FindCalleesTool: Locates all functions, methods, and routines called by a target symbol."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class FindCalleesTool(BaseTool):
    """Finds all functions, methods, and routines invoked by a specified function or method."""

    name = "find_callees"
    description = "Locates all functions and methods invoked or called by a specified function or method."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="symbol_name",
            type="string",
            description="Name of the caller function or method whose invoked callees to locate.",
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

        callees = graph.find_callees(symbol_name)
        if not callees:
            return ToolResult.ok(
                f"No callees recorded for '{symbol_name}'.",
                metadata={"callees_count": 0, "symbol_name": symbol_name},
            )

        lines = [f"Found {len(callees)} callee(s) called by '{symbol_name}':"]
        for c in callees:
            res_str = ""
            if c["resolved"]:
                first_res = c["resolved"][0]
                res_str = f" -> resolved to {first_res['file_path']}:L{first_res['start_line']}"
            else:
                res_str = " (external or built-in)"
            lines.append(f"  - Calls '{c['callee_name']}'{res_str} [from {c['caller_file']}]")

        return ToolResult.ok(
            "\n".join(lines),
            metadata={
                "callees_count": len(callees),
                "symbol_name": symbol_name,
                "callees": callees,
            },
        )
