"""CodeStructureTool: Generates hierarchical symbol outline of files or repository."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from prubeth.repository.ast_parser import CodeSymbol, PolyglotASTParser
from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class CodeStructureTool(BaseTool):
    """Generates structured architectural outline of symbols, classes, and functions."""

    name = "code_structure"
    description = "Extracts hierarchical symbol structure (classes, functions, methods, signatures, docstrings) from a file or workspace."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Relative path of file to inspect. If omitted, returns project-wide symbol overview.",
            required=False,
            default="",
        ),
    ]

    def execute(self, args: Optional[Dict[str, Any]] = None, context: Any = None, **kwargs) -> ToolResult:
        params = dict(args or {}) | kwargs
        ws_root = Path(getattr(context, "workspace_root", None) or self.workspace_root)
        file_path_str = str(params.get("file_path", "")).strip()
        index = IncrementalCodeIndex(ws_root)

        if file_path_str:
            target = (ws_root / file_path_str).resolve()
            if not target.is_file():
                return ToolResult.fail(f"File not found: {file_path_str}", metadata={"file_path": file_path_str})

            parser = PolyglotASTParser(ws_root)
            symbols = parser.parse_file(target)
            if not symbols:
                return ToolResult.ok(
                    f"No top-level AST symbols detected in {file_path_str}.",
                    metadata={"count": 0, "file_path": file_path_str},
                )

            lines = [f"Structure of {file_path_str}:"]
            for s in symbols:
                indent = "    " if s.parent_symbol else "  "
                parent_tag = f" (in {s.parent_symbol})" if s.parent_symbol else ""
                lines.append(f"{indent}- [{s.kind.value}] {s.signature}{parent_tag} [L{s.start_line}-L{s.end_line}]")
                if s.docstring:
                    first_doc_line = s.docstring.strip().splitlines()[0][:80]
                    lines.append(f"{indent}    /// {first_doc_line}")

            return ToolResult.ok(
                "\n".join(lines),
                metadata={"count": len(symbols), "file_path": file_path_str},
            )
        else:
            # Sync and get global overview
            index.sync_index()
            symbols = index.search_symbols("", limit=100)
            lines = [f"Repository Symbol Overview ({len(symbols)} symbols listed):"]
            for s in symbols[:50]:
                lines.append(f"  - [{s.kind.value}] {s.name} in {s.file_path}:L{s.start_line} (`{s.signature}`)")

            return ToolResult.ok(
                "\n".join(lines),
                metadata={"count": len(symbols)},
            )
