"""PRUBETH Snapshot Rollback, Memory Vault & Pinned Context Matrix.

Exhaustively verifies filesystem snapshot preservation, atomic rollback,
continuous intelligence memory ledgers, pinned context anchors, and
conversation time-travel tree branching.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from prubeth.persistence.checkpoints import SnapshotManager
from prubeth.persistence.memory import MemoryVault
from prubeth.persistence.pinned import PinnedContextManager
from prubeth.persistence.tree import ConversationTree, ConversationNode


# ============================================================================
# 1. SnapshotManager Lifecycle & Atomic Rollback Tests
# ============================================================================

def test_snapshot_manager_create_and_list(tmp_path: Path):
    """Creates a filesystem snapshot and verifies listing and count."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "main.py").write_text("x = 1\n", encoding="utf-8")
    (ws / "README.md").write_text("# Project\n", encoding="utf-8")

    mgr = SnapshotManager(workspace_root=ws, task_id="test_task")
    res = mgr.create_snapshot("baseline")
    assert "baseline" in res
    assert "preserved" in res

    snapshots = mgr.list_snapshots()
    assert "baseline" in snapshots


def test_snapshot_manager_manifest_json_format(tmp_path: Path):
    """Snapshot directory contains a valid .manifest.json recording all tracked files."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "file1.txt").write_text("content 1", encoding="utf-8")
    (ws / "sub").mkdir()
    (ws / "sub" / "file2.txt").write_text("content 2", encoding="utf-8")

    mgr = SnapshotManager(workspace_root=ws, task_id="manifest_task")
    mgr.create_snapshot("snap1")

    snap_dir = ws / ".prubeth" / "snapshots" / "manifest_task" / "snap1"
    manifest_file = snap_dir / ".manifest.json"
    assert manifest_file.exists()

    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert "timestamp" in data
    files = data.get("files", [])
    assert "file1.txt" in files
    assert "sub/file2.txt" in files


def test_snapshot_manager_ignores_build_and_git_dirs(tmp_path: Path):
    """Snapshot ignore list skips .git, node_modules, and cache directories."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "src.py").write_text("code", encoding="utf-8")
    (ws / ".git").mkdir()
    (ws / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (ws / "node_modules").mkdir()
    (ws / "node_modules" / "pkg.js").write_text("js", encoding="utf-8")

    mgr = SnapshotManager(workspace_root=ws, task_id="ignore_task")
    mgr.create_snapshot("clean_snap")

    snap_dir = ws / ".prubeth" / "snapshots" / "ignore_task" / "clean_snap"
    manifest = json.loads((snap_dir / ".manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]

    assert "src.py" in files
    assert not any(".git" in f for f in files)
    assert not any("node_modules" in f for f in files)


def test_snapshot_manager_rollback_restores_modified_file(tmp_path: Path):
    """Rollback restores modified files back to exact snapshot state."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    target_file = ws / "core.py"
    target_file.write_text("original_version = 1.0\n", encoding="utf-8")

    mgr = SnapshotManager(workspace_root=ws, task_id="rollback_task")
    mgr.create_snapshot("v1")

    # Mutate the file
    target_file.write_text("corrupted_version = 9.9\n", encoding="utf-8")
    assert "corrupted" in target_file.read_text(encoding="utf-8")

    # Roll back
    ok = mgr.rollback_to_snapshot("v1")
    assert ok is True
    assert target_file.read_text(encoding="utf-8") == "original_version = 1.0\n"


def test_snapshot_manager_rollback_removes_new_files(tmp_path: Path):
    """Rollback deletes any new untracked files added after the snapshot."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "stable.py").write_text("stable", encoding="utf-8")

    mgr = SnapshotManager(workspace_root=ws, task_id="remove_untracked")
    mgr.create_snapshot("clean")

    # Add unwanted file
    unwanted = ws / "unwanted_temp.py"
    unwanted.write_text("bad data", encoding="utf-8")
    assert unwanted.exists()

    # Roll back
    mgr.rollback_to_snapshot("clean")
    assert not unwanted.exists()
    assert (ws / "stable.py").exists()


def test_snapshot_manager_compute_snapshot_diff(tmp_path: Path):
    """Computes a unified diff between current workspace and snapshot."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    f = ws / "calc.py"
    f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    mgr = SnapshotManager(workspace_root=ws, task_id="diff_task")
    mgr.create_snapshot("before_change")

    # Edit file
    f.write_text("def add(a, b):\n    return a + b + 1\n", encoding="utf-8")

    diff = mgr.compute_snapshot_diff("before_change")
    assert "--- a/calc.py" in diff
    assert "+++ b/calc.py" in diff
    assert "+    return a + b + 1" in diff


def test_snapshot_manager_delete_and_clear_snapshots(tmp_path: Path):
    """Deletes individual snapshots and clears all snapshots."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "doc.txt").write_text("text", encoding="utf-8")

    mgr = SnapshotManager(workspace_root=ws, task_id="clear_task")
    mgr.create_snapshot("s1")
    mgr.create_snapshot("s2")
    mgr.create_snapshot("s3")
    assert len(mgr.list_snapshots()) == 3

    # Delete s2
    ok = mgr.delete_snapshot("s2")
    assert ok is True
    assert mgr.list_snapshots() == ["s1", "s3"]

    # Clear all
    cleared = mgr.clear_all_snapshots()
    assert cleared == 2
    assert mgr.list_snapshots() == []


def test_snapshot_manager_timeline_metadata(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "app.py").write_text("code", encoding="utf-8")

    mgr = SnapshotManager(workspace_root=ws, task_id="timeline_task")
    mgr.create_snapshot("first")
    timeline = mgr.get_timeline()
    assert len(timeline) == 1
    assert timeline[0]["label"] == "first"
    assert timeline[0]["files_count"] == 1


# ============================================================================
# 2. MemoryVault Continuous Intelligence Tests
# ============================================================================

def test_memory_vault_initializes_markdown_ledgers(tmp_path: Path):
    """MemoryVault creates anti-patterns.md and decisions.md with standard headers."""
    mem_dir = tmp_path / "memory"
    vault = MemoryVault(memory_dir=mem_dir)

    assert vault.anti_patterns_file.exists()
    assert vault.decisions_file.exists()
    assert "PRUBETH Learned Anti-Patterns Ledger" in vault.anti_patterns_file.read_text(encoding="utf-8")
    assert "PRUBETH Architectural Decisions Ledger" in vault.decisions_file.read_text(encoding="utf-8")


def test_memory_vault_record_anti_pattern(tmp_path: Path):
    """Records an anti-pattern and verifies Markdown formatting."""
    vault = MemoryVault(memory_dir=tmp_path / "mem")
    vault.record_anti_pattern(
        failing_component="JSON Parser",
        error_symptom="Unterminated string literal",
        root_cause="Raw regex slicing broke escaped quotes",
        prevention_rule="Always use json.loads with balanced brace parser"
    )

    content = vault.anti_patterns_file.read_text(encoding="utf-8")
    assert "### [Anti-Pattern] JSON Parser" in content
    assert "**Error Symptom**: `Unterminated string literal`" in content
    assert "**Root Cause**: Raw regex slicing" in content
    assert "**Rule to Prevent Recurrence**: Always use json.loads" in content


def test_memory_vault_record_decision(tmp_path: Path):
    """Records an architectural decision with affected modules."""
    vault = MemoryVault(memory_dir=tmp_path / "mem")
    vault.record_decision(
        decision_title="SQLite WAL Mode for Checkpoints",
        rationale="Eliminates database write contention during parallel subagent execution",
        affected_modules=["prubeth.persistence.database", "prubeth.runtime.controller"]
    )

    content = vault.decisions_file.read_text(encoding="utf-8")
    assert "### [Decision] SQLite WAL Mode for Checkpoints" in content
    assert "`prubeth.persistence.database`" in content
    assert "Eliminates database write contention" in content


def test_memory_vault_get_memory_context_formatting(tmp_path: Path):
    """Formats combined anti-patterns and decisions for system prompt injection."""
    vault = MemoryVault(memory_dir=tmp_path / "mem")
    vault.record_anti_pattern("Auth Gate", "401 error", "Missing bearer prefix", "Prepend Bearer")
    vault.record_decision("Auth Architecture", "Use JWT tokens", ["auth.py"])

    ctx = vault.get_memory_context(max_chars=4000)
    assert "Learned Anti-Patterns:" in ctx or "Auth Gate" in ctx
    assert "Architectural Decisions:" in ctx or "Auth Architecture" in ctx


def test_memory_vault_truncation_limits(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path / "mem")
    vault.record_anti_pattern("LongComponent" * 50, "Symptom" * 50, "Cause" * 50, "Rule" * 50)
    ctx = vault.get_memory_context(max_chars=100)
    assert len(ctx) <= 150  # Accounts for truncation notice


# ============================================================================
# 3. PinnedContextManager Tests
# ============================================================================

def test_pinned_context_manager_pin_existing_file(tmp_path: Path):
    """Pins an existing file into permanent context and verifies pinned.json."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    target = ws / "schema.sql"
    target.write_text("CREATE TABLE users (id INT);", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=ws)
    ok = mgr.pin("schema.sql")
    assert ok is True

    pinned = mgr.load_pinned()
    assert "schema.sql" in pinned


def test_pinned_context_manager_pin_missing_file_rejected(tmp_path: Path):
    """Pinning a non-existent file returns False and leaves pinned list empty."""
    mgr = PinnedContextManager(workspace_root=tmp_path)
    ok = mgr.pin("missing_file.py")
    assert ok is False
    assert mgr.load_pinned() == []


def test_pinned_context_manager_idempotent_pinning(tmp_path: Path):
    """Pinning the same file multiple times does not create duplicates."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "types.ts").write_text("export type User = { id: string };", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=ws)
    mgr.pin("types.ts")
    mgr.pin("types.ts")

    pinned = mgr.load_pinned()
    assert len(pinned) == 1
    assert pinned[0] == "types.ts"


def test_pinned_context_manager_unpin_exact_and_basename(tmp_path: Path):
    """Unpins files by exact relative path or filename basename."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "sub").mkdir()
    (ws / "sub" / "constants.py").write_text("PI = 3.14\n", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=ws)
    mgr.pin("sub/constants.py")
    assert "sub/constants.py" in mgr.load_pinned()

    # Unpin using basename
    ok = mgr.unpin("constants.py")
    assert ok is True
    assert mgr.load_pinned() == []


def test_pinned_context_manager_clear(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "f1.txt").write_text("1", encoding="utf-8")
    (ws / "f2.txt").write_text("2", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=ws)
    mgr.pin("f1.txt")
    mgr.pin("f2.txt")
    assert len(mgr.load_pinned()) == 2

    mgr.clear()
    assert mgr.load_pinned() == []


# ============================================================================
# 4. ConversationTree Non-Linear Branching Tests
# ============================================================================

def test_conversation_tree_add_turn_and_heads(tmp_path: Path):
    """Adds conversation turns and links parent nodes sequentially."""
    tree = ConversationTree(storage_dir=tmp_path / "history")

    t1 = tree.add_turn("Add user login", "Implemented UserAuth class")
    t2 = tree.add_turn("Add JWT support", "Integrated pyjwt with secret rotation")

    assert t1 == "turn_001"
    assert t2 == "turn_002"
    assert tree.nodes[t2].parent_id == t1
    assert tree.head_turn_id == t2
    assert tree.branches["main"] == t2


def test_conversation_tree_branching_and_switch(tmp_path: Path):
    """Forks a new branch from a historical turn and tracks branch head."""
    tree = ConversationTree(storage_dir=tmp_path / "history")
    t1 = tree.add_turn("Turn 1 prompt", "Turn 1 answer")
    t2 = tree.add_turn("Turn 2 prompt", "Turn 2 answer")

    # Create new experiment branch
    tree.branches["experiment"] = t1
    tree.current_branch = "experiment"
    tree.head_turn_id = t1

    t3 = tree.add_turn("Alternative prompt", "Alternative implementation")
    assert tree.nodes[t3].parent_id == t1
    assert tree.nodes[t3].branch == "experiment"
    assert tree.branches["main"] == t2
    assert tree.branches["experiment"] == t3


def test_conversation_tree_persistence_across_reloads(tmp_path: Path):
    """Tree JSON survives instance reload from disk."""
    dir_path = tmp_path / "hist"
    tree1 = ConversationTree(storage_dir=dir_path)
    t1 = tree1.add_turn("Persistent prompt", "Persistent response")

    tree2 = ConversationTree(storage_dir=dir_path)
    assert t1 in tree2.nodes
    assert tree2.nodes[t1].user_prompt == "Persistent prompt"
    assert tree2.head_turn_id == t1
