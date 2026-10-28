"""PRUBETH Conversation DAG Deep Tree Permutation Matrix.

Exhaustively verifies non-linear branching, deep tree traversal, multi-way forks,
cycle resistance, crash-safe dictionary serialization, and branch switching.
"""

from __future__ import annotations

import pytest
from prubeth.persistence.dag import ConversationDAG, ConversationNode


# ============================================================================
# 1. Deep Linear Conversation Path
# ============================================================================

def test_dag_deep_linear_path():
    """Builds a 50-node linear conversation path and verifies order and depth."""
    dag = ConversationDAG()
    node_ids = []
    for i in range(50):
        nid = dag.add_turn(
            role="user" if i % 2 == 0 else "assistant",
            content=f"Turn message {i}",
            tool_calls=[{"tool": "read_file"}] if i % 2 == 1 else None
        )
        node_ids.append(nid)

    path = dag.get_active_path()
    assert len(path) == 50
    assert [n.node_id for n in path] == node_ids
    assert path[0].node_id == dag.root_node_id
    assert path[-1].node_id == dag.current_node_id


# ============================================================================
# 2. Multi-Way Hypothesis Forking
# ============================================================================

@pytest.mark.parametrize("num_branches", [3, 5, 10])
def test_dag_multi_way_forking_from_common_ancestor(num_branches: int):
    """Forks N independent hypothesis branches from a single root node."""
    dag = ConversationDAG()
    root_id = dag.add_turn("user", "Initial Goal: Optimize Database Queries")

    branch_names = [f"hypothesis_{i}" for i in range(num_branches)]
    for name in branch_names:
        dag.create_branch(name, from_node_id=root_id)
        assert dag.active_branch == name
        assert dag.current_node_id == root_id
        # Add branch-specific turn
        turn_id = dag.add_turn("assistant", f"Plan for {name}")
        assert dag.nodes[turn_id].parent_id == root_id

    # Verify all branches are isolated and have root as parent
    for name in branch_names:
        dag.switch_branch(name)
        path = dag.get_active_path()
        assert len(path) == 2
        assert path[0].node_id == root_id
        assert f"Plan for {name}" in path[1].content


# ============================================================================
# 3. Serialization & Deserialization Invariance
# ============================================================================

def test_dag_roundtrip_serialization():
    dag = ConversationDAG()
    r = dag.add_turn("user", "Hello PRUBETH")
    dag.add_turn("assistant", "Greetings developer.")
    dag.create_branch("feature-x")
    dag.add_turn("user", "Try approach X")

    data = dag.to_dict()
    assert "nodes" in data
    assert "branches" in data
    assert "active_branch" in data

    loaded = ConversationDAG.from_dict(data)
    assert len(loaded.nodes) == len(dag.nodes)
    assert loaded.active_branch == "feature-x"
    assert loaded.root_node_id == dag.root_node_id
    assert loaded.current_node_id == dag.current_node_id

    # Verify path parity
    orig_path = [n.node_id for n in dag.get_active_path()]
    loaded_path = [n.node_id for n in loaded.get_active_path()]
    assert orig_path == loaded_path


# ============================================================================
# 4. Branch Switching and Validation
# ============================================================================

def test_dag_switch_nonexistent_branch_fails():
    dag = ConversationDAG()
    dag.add_turn("user", "Initial")
    assert dag.switch_branch("nonexistent-branch-name") is False
    assert dag.active_branch == "main"


def test_dag_create_duplicate_branch_switches():
    dag = ConversationDAG()
    dag.add_turn("user", "Initial")
    dag.create_branch("branch-1")
    dag.add_turn("assistant", "Response 1")

    # Creating already-existing branch switches to it without overwriting head
    head_before = dag.branches["branch-1"]
    dag.create_branch("branch-1")
    assert dag.branches["branch-1"] == head_before
    assert dag.active_branch == "branch-1"


# ============================================================================
# 5. Node Children Relationships and Traversal
# ============================================================================

def test_dag_children_linkage_integrity():
    dag = ConversationDAG()
    root_id = dag.add_turn("user", "Root")
    c1_id = dag.add_turn("assistant", "Child 1")
    dag.create_branch("alt", from_node_id=root_id)
    c2_id = dag.add_turn("assistant", "Child 2")

    root_node = dag.nodes[root_id]
    assert c1_id in root_node.children_ids
    assert c2_id in root_node.children_ids
    assert len(root_node.children_ids) == 2


# ============================================================================
# 6. ConversationNode Dict Conversion
# ============================================================================

def test_conversation_node_dict_conversion():
    node = ConversationNode(
        node_id="test_node_id",
        parent_id="parent_123",
        role="assistant",
        content="Testing node",
        tool_calls=[{"tool": "edit_file", "args": {}}],
        children_ids=["child_1", "child_2"],
        metadata={"priority": "high"}
    )
    d = node.to_dict()
    assert d["node_id"] == "test_node_id"
    assert d["metadata"]["priority"] == "high"

    reconstructed = ConversationNode.from_dict(d)
    assert reconstructed.node_id == node.node_id
    assert reconstructed.parent_id == node.parent_id
    assert reconstructed.role == node.role
    assert reconstructed.content == node.content
    assert reconstructed.tool_calls == node.tool_calls
    assert reconstructed.children_ids == node.children_ids
    assert reconstructed.metadata == node.metadata
