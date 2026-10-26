"""PRUBETH Conversation Time-Travel Tree & Non-Linear Branching Engine.

Allows branching dialogues into parallel experiments, inspecting the full
chronological decision graph, and rewinding both conversational memory and
disk workspace state to any historical turn.
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

@dataclass
class ConversationNode:
    turn_id: str
    parent_id: Optional[str]
    branch: str
    user_prompt: str
    response_summary: str
    snapshot_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

class ConversationTree:
    """Manages tree-structured conversation nodes with filesystem checkpoint links."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (Path.cwd() / ".prubeth" / "history")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.tree_file = self.storage_dir / "conversation_tree.json"
        self.nodes: Dict[str, ConversationNode] = {}
        self.branches: Dict[str, str] = {"main": ""}  # branch_name -> head_turn_id
        self.current_branch: str = "main"
        self.head_turn_id: Optional[str] = None
        self._load()

    def _load(self):
        """Loads conversation tree from disk."""
        if self.tree_file.exists():
            try:
                data = json.loads(self.tree_file.read_text(encoding="utf-8"))
                for k, v in data.get("nodes", {}).items():
                    self.nodes[k] = ConversationNode(**v)
                self.branches = data.get("branches", {"main": ""})
                self.current_branch = data.get("current_branch", "main")
                self.head_turn_id = self.branches.get(self.current_branch)
            except Exception:
                pass

    def _save(self):
        """Persists tree state to disk."""
        data = {
            "current_branch": self.current_branch,
            "branches": self.branches,
            "nodes": {k: asdict(v) for k, v in self.nodes.items()}
        }
        self.tree_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_turn(
        self,
        user_prompt: str,
        response_text: str,
        snapshot_id: Optional[str] = None
    ) -> str:
        """Appends a new turn to the current active branch."""
        turn_num = len(self.nodes) + 1
        turn_id = f"turn_{turn_num:03d}"
        
        node = ConversationNode(
            turn_id=turn_id,
            parent_id=self.head_turn_id,
            branch=self.current_branch,
            user_prompt=user_prompt[:80],
            response_summary=response_text[:120].replace("\n", " "),
            snapshot_id=snapshot_id
        )
        self.nodes[turn_id] = node
        self.head_turn_id = turn_id
        self.branches[self.current_branch] = turn_id
        self._save()
        return turn_id

    def fork(self, new_branch_name: str) -> str:
        """Forks a new branch from current head turn."""
        clean_name = new_branch_name.strip().replace(" ", "_").lower()
        self.branches[clean_name] = self.head_turn_id or ""
        self.current_branch = clean_name
        self._save()
        return clean_name

    def switch_branch(self, branch_name: str) -> bool:
        """Switches active branch pointer."""
        clean_name = branch_name.strip().lower()
        if clean_name in self.branches:
            self.current_branch = clean_name
            self.head_turn_id = self.branches[clean_name]
            self._save()
            return True
        return False

    def rewind(self, turn_id: str) -> Tuple[bool, Optional[str]]:
        """Rewinds active branch back to a historical turn and returns its snapshot_id."""
        if turn_id in self.nodes:
            node = self.nodes[turn_id]
            self.head_turn_id = turn_id
            self.branches[self.current_branch] = turn_id
            self._save()
            return True, node.snapshot_id
        return False, None

    def compact(self) -> int:
        """Compresses conversation history by distilling previous turns into a single summary node."""
        if len(self.nodes) <= 2:
            return 0
        pruned_count = len(self.nodes) - 1
        last_node_id = self.head_turn_id or list(self.nodes.keys())[-1]
        last_node = self.nodes[last_node_id]

        summary_prompt = f"Compacted Context ({pruned_count} historical turns compressed)"
        summary_resp = f"Preserved context up to {last_node.turn_id}. Active goal: {last_node.user_prompt}"

        self.nodes.clear()
        compact_id = "turn_compacted"
        compact_node = ConversationNode(
            turn_id=compact_id,
            parent_id=None,
            branch=self.current_branch,
            user_prompt=summary_prompt,
            response_summary=summary_resp,
            snapshot_id=last_node.snapshot_id
        )
        self.nodes[compact_id] = compact_node
        self.head_turn_id = compact_id
        self.branches[self.current_branch] = compact_id
        self._save()
        return pruned_count

    def clear(self):
        """Clears all conversation turns on the current branch."""
        self.nodes.clear()
        self.head_turn_id = None
        self.branches[self.current_branch] = ""
        self._save()

    def render_history_table(self) -> Any:
        """Builds a Rich Table visualization of conversation history."""
        from rich.table import Table
        from rich import box

        table = Table(title="PRUBETH Conversation & Decision History Tree", box=box.ROUNDED)
        table.add_column("Turn ID", style="bold cyan")
        table.add_column("Branch", style="magenta")
        table.add_column("Time", style="dim")
        table.add_column("User Prompt / Action", style="white")
        table.add_column("Linked Disk Snapshot", style="yellow")
        table.add_column("Head Pointer", justify="center", style="bold green")

        for tid in sorted(self.nodes.keys()):
            n = self.nodes[tid]
            is_head = "● ACTIVE HEAD" if tid == self.head_turn_id else ""
            table.add_row(
                n.turn_id,
                n.branch,
                n.timestamp,
                n.user_prompt,
                n.snapshot_id or "-",
                is_head
            )

        return table
