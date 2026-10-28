"""PRUBETH DAG Multi-Branch Conversation Tree Engine.

Enables non-linear developer workflows: exploring alternative architectural hypotheses,
branching dialogue trees, comparing competing implementations, and merging findings.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set


@dataclass
class ConversationNode:
    """A single dialogue or action node in the conversation DAG."""
    node_id: str
    parent_id: Optional[str]
    role: str                       # "user", "assistant", "tool", "system"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    children_ids: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "children_ids": self.children_ids,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConversationNode:
        return cls(
            node_id=data["node_id"],
            parent_id=data.get("parent_id"),
            role=data.get("role", "user"),
            content=data.get("content", ""),
            tool_calls=data.get("tool_calls"),
            children_ids=data.get("children_ids", []),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )


class ConversationDAG:
    """Directed Acyclic Graph (DAG) managing conversation branching and tree history."""

    def __init__(self):
        self.nodes: Dict[str, ConversationNode] = {}
        self.root_node_id: Optional[str] = None
        self.current_node_id: Optional[str] = None
        self.branches: Dict[str, str] = {}  # branch_name -> head_node_id
        self.active_branch: str = "main"

    def add_turn(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Appends a new turn to the current active branch."""
        node_id = f"node_{uuid.uuid4().hex[:10]}"
        eff_parent = parent_id or self.current_node_id

        node = ConversationNode(
            node_id=node_id,
            parent_id=eff_parent,
            role=role,
            content=content,
            tool_calls=tool_calls,
            metadata=metadata or {}
        )

        self.nodes[node_id] = node

        if eff_parent and eff_parent in self.nodes:
            self.nodes[eff_parent].children_ids.append(node_id)
        elif self.root_node_id is None:
            self.root_node_id = node_id

        self.current_node_id = node_id
        self.branches[self.active_branch] = node_id
        return node_id

    def create_branch(self, branch_name: str, from_node_id: Optional[str] = None) -> str:
        """Forks a new conversation branch from specified node or current head."""
        if not branch_name:
            raise ValueError("Branch name cannot be empty.")

        source_node = from_node_id or self.current_node_id
        if source_node and source_node not in self.nodes:
            raise KeyError(f"Node '{source_node}' does not exist in DAG.")

        self.branches[branch_name] = source_node
        self.active_branch = branch_name
        self.current_node_id = source_node
        return branch_name

    def switch_branch(self, branch_name: str) -> bool:
        """Switches active branch to branch_name."""
        if branch_name not in self.branches:
            return False
        self.active_branch = branch_name
        self.current_node_id = self.branches[branch_name]
        return True

    def get_active_path(self) -> List[ConversationNode]:
        """Returns the linear path of nodes from root to current node for prompt generation."""
        if not self.current_node_id or self.current_node_id not in self.nodes:
            return []

        path: List[ConversationNode] = []
        curr: Optional[str] = self.current_node_id
        visited: Set[str] = set()

        while curr and curr in self.nodes:
            if curr in visited:
                break
            visited.add(curr)
            node = self.nodes[curr]
            path.append(node)
            curr = node.parent_id

        path.reverse()
        return path

    def export_linear_messages(self) -> List[Dict[str, Any]]:
        """Exports the active linear path as provider-compatible messages."""
        path = self.get_active_path()
        messages = []
        for n in path:
            msg: Dict[str, Any] = {"role": n.role, "content": n.content}
            if n.tool_calls:
                msg["tool_calls"] = n.tool_calls
            messages.append(msg)
        return messages

    def to_dict(self) -> Dict[str, Any]:
        """Serialises the complete DAG state."""
        return {
            "root_node_id": self.root_node_id,
            "current_node_id": self.current_node_id,
            "active_branch": self.active_branch,
            "branches": dict(self.branches),
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConversationDAG:
        """Restores DAG state from dictionary."""
        dag = cls()
        dag.root_node_id = data.get("root_node_id")
        dag.current_node_id = data.get("current_node_id")
        dag.active_branch = data.get("active_branch", "main")
        dag.branches = data.get("branches", {})
        nodes_raw = data.get("nodes", {})
        for nid, nd in nodes_raw.items():
            dag.nodes[nid] = ConversationNode.from_dict(nd)
        return dag
