"""TraceDataFlowTool: Traces multi-level call and invocation trees across workspace symbols."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class TraceDataFlowTool(BaseTool):
    """Traces multi-level call hierarchy trees forward (callees) or backward (callers)."""

    name = "trace_data_flow"
    description = "Traces invocation flows starting from a symbol, either forward (what it calls) or backward (who calls it) up to N levels."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="symbol_name",
            type="string",
            description="Name of the root symbol to trace from.",
            required=True,
        ),
        ToolParameter(
            name="depth",
            type="integer",
            description="Maximum traversal depth (default 3, range 1-5).",
            required=False,
            default=3,
        ),
        ToolParameter(
            name="direction",
            type="string",
            description="Direction of trace: 'forward' (callees) or 'backward' (callers).",
            required=False,
            default="forward",
            enum=["forward", "backward"],
        ),
    ]

    def execute(self, args: Optional[Dict[str, Any]] = None, context: Any = None, **kwargs) -> ToolResult:
        params = dict(args or {}) | kwargs
        symbol_name = str(params.get("symbol_name", "")).strip()
        if not symbol_name:
            return ToolResult.fail("Parameter 'symbol_name' cannot be empty.")

        depth = min(max(int(params.get("depth", 3)), 1), 5)
        direction = str(params.get("direction", "forward")).lower()
        if direction not in {"forward", "backward"}:
            direction = "forward"

        ws_root = Path(getattr(context, "workspace_root", None) or self.workspace_root)
        index = IncrementalCodeIndex(ws_root)
        index.sync_index()
        graph = index.load_graph()

        tree = graph.trace_data_flow(symbol_name, max_depth=depth, direction=direction)

        def _format_tree(node: Dict[str, Any], prefix: str = "") -> List[str]:
            out = [f"{prefix}* {node['name']} (depth {node['depth']})"]
            child_nodes = node.get("nodes", [])
            for i, child in enumerate(child_nodes):
                is_last = (i == len(child_nodes) - 1)
                sub_prefix = prefix + ("  " if is_last else "| ")
                out.extend(_format_tree(child, sub_prefix))
            return out

        rendered = _format_tree(tree)
        dir_label = "Callee Invocation Tree (Forward)" if direction == "forward" else "Caller Dependency Tree (Backward)"
        header = f"=== {dir_label} for '{symbol_name}' (Depth {depth}) ===\n"

        return ToolResult.ok(
            header + "\n".join(rendered),
            metadata={"root": symbol_name, "depth": depth, "direction": direction, "tree": tree},
        )
