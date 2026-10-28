"""PRUBETH ConversationTree Time-Travel & Branch Rewind Matrix Tests.

Exhaustively verifies ConversationTree node addition, branch forking,
branch switching, rewind-to-historical-turn, snapshot_id linkage,
compact/distillation, and clear invariants.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.persistence.tree import ConversationTree, ConversationNode


# ============================================================================
# 1. Initialisation Invariants
# ============================================================================

def test_tree_initialises_with_main_branch(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    assert "main" in tree.branches
    assert tree.current_branch == "main"
    assert tree.head_turn_id is None


def test_tree_storage_dir_created(tmp_path: Path):
    storage = tmp_path / "history"
    tree = ConversationTree(storage_dir=storage)
    assert storage.exists()


# ============================================================================
# 2. Adding Turns
# ============================================================================

def test_add_turn_increments_nodes(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    t1 = tree.add_turn("Hello PRUBETH", "Hello! How may I assist?")
    assert t1 in tree.nodes
    assert len(tree.nodes) == 1


def test_add_turn_updates_head(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    tree.add_turn("First", "One")
    tree.add_turn("Second", "Two")
    assert tree.head_turn_id == "turn_002"


def test_add_turn_with_snapshot_id(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    t = tree.add_turn("Deploy", "Deployed.", snapshot_id="snap_001")
    node = tree.nodes[t]
    assert node.snapshot_id == "snap_001"


def test_add_turn_truncates_long_prompt(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    long_prompt = "X" * 200
    t = tree.add_turn(long_prompt, "Ok.")
    node = tree.nodes[t]
    assert len(node.user_prompt) <= 80


def test_add_turn_truncates_long_response(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    long_resp = "R" * 300
    t = tree.add_turn("Prompt", long_resp)
    node = tree.nodes[t]
    assert len(node.response_summary) <= 120


def test_add_multiple_turns_links_parent(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    t1 = tree.add_turn("First", "First response.")
    t2 = tree.add_turn("Second", "Second response.")
    assert tree.nodes[t2].parent_id == t1


# ============================================================================
# 3. Branch Forking & Switching
# ============================================================================

def test_fork_creates_new_branch(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    tree.add_turn("Setup", "Ready.")
    branch_name = tree.fork("experiment")
    assert "experiment" in tree.branches
    assert tree.current_branch == "experiment"


def test_fork_name_normalised(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    tree.add_turn("Turn 1", "Response.")
    branch_name = tree.fork("My Experiment Branch")
    assert " " not in branch_name
    assert branch_name == branch_name.lower()


def test_switch_branch_succeeds(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    tree.add_turn("T1", "R1.")
    tree.fork("feature")
    tree.add_turn("Feature turn", "Feature response.")
    ok = tree.switch_branch("main")
    assert ok is True
    assert tree.current_branch == "main"


def test_switch_nonexistent_branch_returns_false(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    ok = tree.switch_branch("ghost_branch")
    assert ok is False


def test_fork_preserves_head_pointer(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    t1 = tree.add_turn("Anchor", "Anchor response.")
    _ = tree.fork("new_branch")
    # The new branch should point to the same head as main
    assert tree.branches["new_branch"] == t1


# ============================================================================
# 4. Rewind (Time-Travel)
# ============================================================================

def test_rewind_to_valid_turn(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    t1 = tree.add_turn("T1", "R1.", snapshot_id="snap_1")
    t2 = tree.add_turn("T2", "R2.")
    t3 = tree.add_turn("T3", "R3.")

    ok, snap_id = tree.rewind(t1)
    assert ok is True
    assert snap_id == "snap_1"
    assert tree.head_turn_id == t1


def test_rewind_to_invalid_turn(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    tree.add_turn("T1", "R1.")
    ok, snap = tree.rewind("turn_999")
    assert ok is False
    assert snap is None


def test_rewind_updates_branch_head(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    t1 = tree.add_turn("T1", "R1.")
    t2 = tree.add_turn("T2", "R2.")
    tree.rewind(t1)
    assert tree.branches[tree.current_branch] == t1


# ============================================================================
# 5. Compaction & Clear
# ============================================================================

def test_compact_with_many_nodes(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    for i in range(10):
        tree.add_turn(f"User {i}", f"Response {i}.")
    pruned = tree.compact()
    assert pruned > 0
    assert len(tree.nodes) == 1


def test_compact_returns_pruned_count(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    for i in range(6):
        tree.add_turn(f"Turn {i}", "resp.")
    pruned = tree.compact()
    assert pruned == 5  # 6 nodes, compacted to 1, pruned 5


def test_compact_with_only_two_nodes_does_nothing(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    tree.add_turn("T1", "R1.")
    tree.add_turn("T2", "R2.")
    pruned = tree.compact()
    assert pruned == 0


def test_clear_removes_all_nodes(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    for i in range(5):
        tree.add_turn(f"T{i}", f"R{i}.")
    tree.clear()
    assert len(tree.nodes) == 0
    assert tree.head_turn_id is None


# ============================================================================
# 6. Persistence (Save & Load Cycle)
# ============================================================================

def test_tree_persists_and_reloads(tmp_path: Path):
    tree1 = ConversationTree(storage_dir=tmp_path)
    tree1.add_turn("First turn", "First response.")
    tree1.add_turn("Second turn", "Second response.")
    tree1.fork("experimental")

    # Reload from same directory
    tree2 = ConversationTree(storage_dir=tmp_path)
    assert len(tree2.nodes) == 2
    assert "experimental" in tree2.branches


def test_tree_file_created_on_disk(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path)
    tree.add_turn("Turn", "Response.")
    assert (tmp_path / "conversation_tree.json").exists()
