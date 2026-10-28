"""RankCentralFilesTool: Calculates PageRank centrality of repository files to identify core architectural modules."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult


class RankCentralFilesTool(BaseTool):
    """Calculates PageRank centrality of workspace files based on the import dependency graph."""

    name = "rank_central_files"
    description = "Ranks repository files by PageRank architectural importance, revealing the most critical foundation modules."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of ranked files to return (default 20).",
            required=False,
            default=20,
        ),
        ToolParameter(
            name="damping",
            type="number",
            description="PageRank damping factor (default 0.85).",
            required=False,
            default=0.85,
        ),
    ]

    def execute(self, args: Optional[Dict[str, Any]] = None, context: Any = None, **kwargs) -> ToolResult:
        params = dict(args or {}) | kwargs
        limit = max(1, int(params.get("limit", 20)))
        damping = float(params.get("damping", 0.85))

        ws_root = Path(getattr(context, "workspace_root", None) or self.workspace_root)
        index = IncrementalCodeIndex(ws_root)
        index.sync_index()
        graph = index.load_graph()

        ranked = graph.rank_central_files(damping=damping)
        if not ranked:
            return ToolResult.ok(
                "No import relationships found to rank.",
                metadata={"ranked_count": 0, "ranked": []},
            )

        top = ranked[:limit]
        lines = [f"Architectural Centrality Ranking (Top {len(top)} files by PageRank score):"]
        for rank, (file_path, score) in enumerate(top, start=1):
            pct = round(score * 100, 2)
            lines.append(f"  #{rank:2d} [{pct:5.2f}%] {file_path}")

        return ToolResult.ok(
            "\n".join(lines),
            metadata={"ranked_count": len(ranked), "top_ranked": top},
        )
