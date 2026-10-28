"""ExplainSymbolTool: Assembles deep contextual dossiers for symbols including callers, callees, and types."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class ExplainSymbolTool(BaseTool):
    """Assembles a complete structural and relational dossier explaining a code symbol."""

    name = "explain_symbol"
    description = "Assembles a comprehensive dossier on a symbol: definition, signature, docstring, callers, callees, and inheritance."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="symbol_name",
            type="string",
            description="Name of the symbol (function, method, class) to explain.",
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

        matches = index.search_symbols(symbol_name, limit=5)
        exact = [s for s in matches if s.name == symbol_name]
        targets = exact if exact else matches

        if not targets:
            return ToolResult.fail(f"Symbol '{symbol_name}' not found in workspace.")

        callers = graph.find_callers(symbol_name)
        callees = graph.find_callees(symbol_name)

        target = targets[0]
        lines = [
            f"=== Symbol Dossier: '{target.name}' ===",
            f"Kind:        {target.kind.value}",
            f"Location:    {target.file_path}:{target.start_line}-{target.end_line}",
            f"Signature:   {target.signature}",
        ]

        if target.parent_symbol:
            lines.append(f"Parent:      Class {target.parent_symbol}")

        if target.bases:
            lines.append(f"Inheritance: {', '.join(target.bases)}")

        if target.decorators:
            lines.append(f"Decorators:  {', '.join(target.decorators)}")

        if target.docstring:
            lines.append(f"\nDocstring:\n  {target.docstring.strip()}")

        lines.append(f"\nCallers ({len(callers)} incoming):")
        if callers:
            for c in callers[:10]:
                lines.append(f"  - {c.name} ({c.file_path}:L{c.start_line})")
        else:
            lines.append("  (No direct internal callers recorded)")

        lines.append(f"\nCallees ({len(callees)} outgoing):")
        if callees:
            for cl in callees[:10]:
                lines.append(f"  - Calls '{cl['callee_name']}'")
        else:
            lines.append("  (No outgoing calls detected)")

        if target.body_snippet:
            lines.append("\nCode Preview:")
            lines.append("```\n" + target.body_snippet + "\n```")

        return ToolResult.ok(
            "\n".join(lines),
            metadata={
                "symbol": target.to_dict(),
                "caller_count": len(callers),
                "callee_count": len(callees),
            },
        )
