"""PRUBETH Conversation Tree, Pinned Context & Snapshot Persistence Matrix.

Exhaustively verifies ConversationTree non-linear branching, parent node lineage,
branch switching, rewinds, history compaction, PinnedContextManager KV cache
anchoring, and SnapshotManager filesystem rollback invariants.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from prubeth.persistence.tree import ConversationTree, ConversationNode
from prubeth.persistence.pinned import PinnedContextManager
from prubeth.persistence.compactor import ContextCompactor, CompactionStrategy, PinnedItem
from prubeth.persistence.checkpoints import SnapshotManager


# ============================================================================
# 1. ConversationTree Branching & Lineage Matrix
# ============================================================================

def test_conversation_tree_initial_state(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path / "history")
    assert tree.current_branch == "main"
    assert tree.head_turn_id is None
    assert len(tree.nodes) == 0


def test_conversation_tree_sequential_turns_on_main(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path / "history")

    t1 = tree.add_turn("User prompt 1", "Response summary 1", snapshot_id="snap_01")
    assert t1 == "turn_001"
    assert tree.head_turn_id == "turn_001"
    assert tree.nodes[t1].parent_id is None
    assert tree.nodes[t1].branch == "main"
    assert tree.nodes[t1].snapshot_id == "snap_01"

    t2 = tree.add_turn("User prompt 2", "Response summary 2", snapshot_id="snap_02")
    assert t2 == "turn_002"
    assert tree.head_turn_id == "turn_002"
    assert tree.nodes[t2].parent_id == "turn_001"

    t3 = tree.add_turn("User prompt 3", "Response summary 3")
    assert t3 == "turn_003"
    assert tree.head_turn_id == "turn_003"
    assert tree.nodes[t3].parent_id == "turn_002"


@pytest.mark.parametrize("branch_name", [
    "feature-auth", "experiment_ml", "hotfix-99", "dev/sandbox"
])
def test_conversation_tree_fork_and_branch_turns(tmp_path: Path, branch_name: str):
    tree = ConversationTree(storage_dir=tmp_path / "history")
    t1 = tree.add_turn("Initial prompt", "Initial response")

    # Fork new branch
    forked_branch = tree.fork(branch_name)
    assert tree.current_branch == forked_branch
    assert tree.head_turn_id == t1

    # Add turn on forked branch
    t_fork = tree.add_turn(f"Prompt on {branch_name}", "Branch response")
    assert tree.nodes[t_fork].parent_id == t1
    assert tree.nodes[t_fork].branch == forked_branch
    assert tree.branches[forked_branch] == t_fork

    # Switch back to main
    assert tree.switch_branch("main") is True
    assert tree.current_branch == "main"
    assert tree.head_turn_id == t1


def test_conversation_tree_rewind(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path / "history")
    t1 = tree.add_turn("Turn 1", "Resp 1", snapshot_id="snap_01")
    t2 = tree.add_turn("Turn 2", "Resp 2", snapshot_id="snap_02")
    t3 = tree.add_turn("Turn 3", "Resp 3", snapshot_id="snap_03")

    # Rewind to t1
    ok, snap = tree.rewind(t1)
    assert ok is True
    assert snap == "snap_01"
    assert tree.head_turn_id == t1
    assert tree.branches["main"] == t1

    # Rewind to nonexistent turn
    ok_ghost, snap_ghost = tree.rewind("nonexistent_turn")
    assert ok_ghost is False
    assert snap_ghost is None


def test_conversation_tree_compact(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path / "history")
    for i in range(5):
        tree.add_turn(f"Prompt {i}", f"Response {i}", snapshot_id=f"snap_{i}")

    assert len(tree.nodes) == 5
    pruned = tree.compact()
    assert pruned == 4
    assert len(tree.nodes) == 1
    assert "turn_compacted" in tree.nodes
    compact_node = tree.nodes["turn_compacted"]
    assert "Compacted Context" in compact_node.user_prompt
    assert compact_node.snapshot_id == "snap_4"


def test_conversation_tree_clear(tmp_path: Path):
    tree = ConversationTree(storage_dir=tmp_path / "history")
    tree.add_turn("Prompt 1", "Response 1")
    tree.add_turn("Prompt 2", "Response 2")
    assert len(tree.nodes) == 2

    tree.clear()
    assert len(tree.nodes) == 0
    assert tree.head_turn_id is None
    assert tree.branches["main"] == ""


def test_conversation_tree_disk_persistence(tmp_path: Path):
    hist_dir = tmp_path / "history"
    tree1 = ConversationTree(storage_dir=hist_dir)
    tree1.add_turn("Persisted prompt", "Persisted response", snapshot_id="snap_p")
    tree1.fork("persistent_branch")
    tree1.add_turn("Turn on branch", "Branch resp")

    # Reload in fresh instance from same directory
    tree2 = ConversationTree(storage_dir=hist_dir)
    assert len(tree2.nodes) == 2
    assert "persistent_branch" in tree2.branches
    assert tree2.current_branch == "persistent_branch"


# ============================================================================
# 2. PinnedContextManager Matrix
# ============================================================================

def test_pinned_manager_empty_initial(tmp_path: Path):
    mgr = PinnedContextManager(workspace_root=tmp_path)
    assert mgr.load_pinned() == []


def test_pinned_manager_pin_and_unpin(tmp_path: Path):
    # Create sample files
    f1 = tmp_path / "src" / "api.py"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("class API: pass\n", encoding="utf-8")

    f2 = tmp_path / "README.md"
    f2.write_text("# Docs\n", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)

    # 1. Pin f1
    assert mgr.pin("src/api.py") is True
    assert "src/api.py" in mgr.load_pinned()

    # 2. Pin f2
    assert mgr.pin("README.md") is True
    assert len(mgr.load_pinned()) == 2

    # 3. Duplicate pin should be idempotent
    assert mgr.pin("src/api.py") is True
    assert len(mgr.load_pinned()) == 2

    # 4. Pin non-existent file fails
    assert mgr.pin("ghost_file.txt") is False

    # 5. Unpin f1
    assert mgr.unpin("src/api.py") is True
    assert "src/api.py" not in mgr.load_pinned()
    assert len(mgr.load_pinned()) == 1

    # 6. Unpin non-pinned file returns False
    assert mgr.unpin("nonexistent.py") is False


# ============================================================================
# 3. ContextCompactor Matrix
# ============================================================================

def test_context_compactor_initial_state():
    compactor = ContextCompactor(token_limit=10000, target_token_budget=8000)
    assert compactor.token_limit == 10000
    assert compactor.target_token_budget == 8000


def test_context_compactor_token_estimation():
    compactor = ContextCompactor()
    text = "Hello world! This is a unit test."
    tokens = compactor.estimate_tokens(text)
    assert tokens > 0
    assert tokens == int(len(text) / compactor.chars_per_token)


def test_context_compactor_folds_tool_outputs():
    # Setting token_limit low triggers compaction
    compactor = ContextCompactor(token_limit=200, target_token_budget=100)
    messages = [
        {"role": "user", "content": "Run tests please"},
        {"role": "assistant", "content": "Running tests now..."},
        {
            "role": "tool",
            "name": "run_shell",
            "content": "A" * 5000  # Massive output
        },
        {"role": "user", "content": "Check coverage"},
        {"role": "assistant", "content": "Coverage is 88%"},
        {"role": "user", "content": "Next turn"},
        {"role": "assistant", "content": "Next answer"},
        {"role": "assistant", "content": "Tests complete."}
    ]

    compacted_msgs, res = compactor.compact(messages, keep_recent_turns=2)
    assert res.estimated_tokens_after < res.estimated_tokens_before
    assert res.reduction_percentage > 0


def test_context_compactor_preserves_pinned_items():
    compactor = ContextCompactor(token_limit=200, target_token_budget=100)
    pin_id = compactor.pin(
        content="CRITICAL INVARIANT: NEVER REMOVE SECURITY GATE",
        kind="rule",
        label="Security Rule"
    )
    assert compactor.is_pinned(pin_id)
    assert len(compactor.get_pinned_items()) == 1

    formatted = compactor.format_pinned_context()
    assert "CRITICAL INVARIANT" in formatted

    # Compaction retains pinned items
    messages = [
        {"role": "user", "content": "Do task"},
        {"role": "tool", "name": "shell", "content": "B" * 2000},
        {"role": "assistant", "content": "Done"}
    ]
    _, res = compactor.compact(messages)
    assert res.pinned_retained_count == 1


# ============================================================================
# 4. SnapshotManager Filesystem Rollback Matrix
# ============================================================================

def test_snapshot_manager_lifecycle(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    code_file = ws / "main.py"
    code_file.write_text("print('version 1')\n", encoding="utf-8")

    snap_mgr = SnapshotManager(workspace_root=ws, task_id="test_task")

    # 1. Create snapshot
    msg = snap_mgr.create_snapshot("v1_snap")
    assert "Snapshot 'v1_snap' created" in msg or "1 files preserved" in msg

    # Verify listing
    snapshots = snap_mgr.list_snapshots()
    assert "v1_snap" in snapshots

    # 2. Mutate file
    code_file.write_text("print('version 2 - modified')\n", encoding="utf-8")
    assert "version 2" in code_file.read_text(encoding="utf-8")

    # 3. Rollback to snapshot
    roll_ok = snap_mgr.rollback_to_snapshot("v1_snap")
    assert roll_ok is True

    # 4. Verify original content restored
    assert code_file.read_text(encoding="utf-8") == "print('version 1')\n"

    # Timeline verification
    timeline = snap_mgr.get_timeline()
    assert len(timeline) == 1
    assert timeline[0]["label"] == "v1_snap"
