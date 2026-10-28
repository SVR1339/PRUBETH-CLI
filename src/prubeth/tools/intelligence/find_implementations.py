"""FindImplementationsTool: Locates all classes, structs, or traits that inherit from or implement a base symbol."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class FindImplementationsTool(BaseTool):
    """Locates all classes, structs, or types implementing or extending a specified base symbol."""

    name = "find_implementations"
    description = "Locates all classes, structs, or types that implement or inherit from a specified base class, interface, or trait."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="symbol_name",
            type="string",
            description="Name of the base class, interface, or trait whose implementations to find.",
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

        implementations = graph.find_implementations(symbol_name)
        if not implementations:
            return ToolResult.ok(
                f"No implementations or subclasses found inheriting from '{symbol_name}'.",
                metadata={"count": 0, "symbol_name": symbol_name},
            )

        lines = [f"Found {len(implementations)} implementation(s) of '{symbol_name}':"]
        for impl in implementations:
            lines.append(f"  - [{impl.kind.value}] {impl.name} at {impl.file_path}:L{impl.start_line} (`{impl.signature}`)")
            if impl.bases:
                lines.append(f"      Inherits: {', '.join(impl.bases)}")

        return ToolResult.ok(
            "\n".join(lines),
            metadata={
                "count": len(implementations),
                "symbol_name": symbol_name,
                "implementations": [i.to_dict() for i in implementations],
            },
        )
