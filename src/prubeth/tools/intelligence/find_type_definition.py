"""FindTypeDefinitionTool: Locates the exact source definition of a class, struct, interface, or type."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class FindTypeDefinitionTool(BaseTool):
    """Locates the exact declaration and definition of a class, struct, interface, or type alias."""

    name = "find_type_definition"
    description = "Locates the exact source definition and declaration of a class, interface, struct, or type across the workspace."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="symbol_name",
            type="string",
            description="Name of the type, class, struct, or interface to locate.",
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

        symbols = index.search_symbols(symbol_name, limit=10)
        exact_matches = [s for s in symbols if s.name == symbol_name]
        matches = exact_matches if exact_matches else symbols

        if not matches:
            return ToolResult.ok(
                f"No type definition found matching '{symbol_name}'.",
                metadata={"matches_count": 0, "symbol_name": symbol_name},
            )

        lines = [f"Found {len(matches)} definition(s) for '{symbol_name}':"]
        for m in matches:
            lines.append(f"\n--- [{m.kind.value}] {m.name} in {m.file_path}:L{m.start_line}-L{m.end_line} ---")
            lines.append(f"Signature: {m.signature}")
            if m.bases:
                lines.append(f"Bases/Inheritance: {', '.join(m.bases)}")
            if m.docstring:
                lines.append(f"Docstring: {m.docstring.strip()}")
            if m.body_snippet:
                lines.append("```\n" + m.body_snippet + "\n```")

        return ToolResult.ok(
            "\n".join(lines),
            metadata={
                "matches_count": len(matches),
                "symbol_name": symbol_name,
                "definitions": [m.to_dict() for m in matches],
            },
        )
