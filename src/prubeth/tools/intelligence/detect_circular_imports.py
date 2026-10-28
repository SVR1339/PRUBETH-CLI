"""DetectCircularImportsTool: Identifies circular module dependency cycles across the workspace."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class DetectCircularImportsTool(BaseTool):
    """Detects circular import dependency cycles across the workspace."""

    name = "detect_circular_imports"
    description = "Analyses the workspace import graph and detects any circular dependency cycles (e.g. module A imports B, B imports A)."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = []

    def execute(self, args: Optional[Dict[str, Any]] = None, context: Any = None, **kwargs) -> ToolResult:
        ws_root = Path(getattr(context, "workspace_root", None) or self.workspace_root)
        index = IncrementalCodeIndex(ws_root)
        index.sync_index()
        graph = index.load_graph()

        cycles = graph.detect_circular_imports()
        if not cycles:
            return ToolResult.ok(
                "No circular import dependency cycles detected. Clean DAG architecture verified.",
                metadata={"cycles_count": 0, "cycles": []},
            )

        lines = [f"Detected {len(cycles)} circular import cycle(s):"]
        for idx, cycle in enumerate(cycles, start=1):
            cycle_str = " -> ".join(cycle)
            lines.append(f"  Cycle #{idx}: {cycle_str}")

        return ToolResult.ok(
            "\n".join(lines),
            metadata={"cycles_count": len(cycles), "cycles": cycles},
        )
