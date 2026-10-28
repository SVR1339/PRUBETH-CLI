"""Comprehensive Unit Test Matrix for PRUBETH Shadow Worktree Subsystem."""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.agents.worktree import WorktreeManager


def test_worktree_manager_initialization(tmp_path):
    """Validates WorktreeManager directory setup and baseline tracking."""
    mgr = WorktreeManager(workspace_root=tmp_path)
    assert mgr.workspace_root == tmp_path.resolve()
    assert mgr.worktrees_dir.is_dir()
    assert mgr.baselines == {}


def test_worktree_file_hashing(tmp_path):
    """Validates SHA-256 file hashing on valid, modified, and non-existent files."""
    mgr = WorktreeManager(workspace_root=tmp_path)
    test_f = tmp_path / "hello.txt"
    test_f.write_text("hello world", encoding="utf-8")

    h1 = mgr._hash_file(test_f)
    assert len(h1) == 64

    test_f.write_text("hello world 2", encoding="utf-8")
    h2 = mgr._hash_file(test_f)
    assert len(h2) == 64
    assert h1 != h2

    # Non-existent file returns empty string
    assert mgr._hash_file(tmp_path / "missing.txt") == ""


def test_create_worktree_and_ignore_rules(tmp_path):
    """Validates that ignored folders and extensions are excluded from shadow worktrees."""
    # Seed workspace
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "src" / "cache.pyc").write_bytes(b"\x00\x01")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git config", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("js", encoding="utf-8")
    (tmp_path / "debug.log").write_text("error", encoding="utf-8")

    mgr = WorktreeManager(workspace_root=tmp_path)
    wt_path = mgr.create_worktree("subagent-coder-1")

    assert wt_path.is_dir()
    assert (wt_path / "src" / "app.py").is_file()
    assert not (wt_path / "src" / "cache.pyc").exists()
    assert not (wt_path / ".git").exists()
    assert not (wt_path / "node_modules").exists()
    assert not (wt_path / "debug.log").exists()

    # Check baseline recorded
    assert "subagent-coder-1" in mgr.baselines
    assert "src/app.py" in mgr.baselines["subagent-coder-1"]


def test_worktree_diff_lifecycle(tmp_path):
    """Validates diff detection across added, modified, and deleted files."""
    (tmp_path / "base.py").write_text("def base():\n    return 1\n", encoding="utf-8")
    (tmp_path / "to_delete.py").write_text("# delete me\n", encoding="utf-8")

    mgr = WorktreeManager(workspace_root=tmp_path)
    wt_path = mgr.create_worktree("subagent-diff-test")

    # 1. Clean state
    clean_diff = mgr.get_worktree_diff("subagent-diff-test")
    assert clean_diff["has_changes"] is False
    assert clean_diff["modified"] == []
    assert clean_diff["added"] == []
    assert clean_diff["deleted"] == []
    assert clean_diff["diff"] == ""

    # 2. Add a new file
    (wt_path / "new_module.py").write_text("def new_func():\n    return 42\n", encoding="utf-8")
    diff_added = mgr.get_worktree_diff("subagent-diff-test")
    assert diff_added["has_changes"] is True
    assert "new_module.py" in diff_added["added"]
    assert "+def new_func():" in diff_added["diff"]

    # 3. Modify existing file
    (wt_path / "base.py").write_text("def base():\n    return 999\n", encoding="utf-8")
    diff_mod = mgr.get_worktree_diff("subagent-diff-test")
    assert "base.py" in diff_mod["modified"]
    assert "+    return 999" in diff_mod["diff"]

    # 4. Delete existing file
    (wt_path / "to_delete.py").unlink()
    diff_del = mgr.get_worktree_diff("subagent-diff-test")
    assert "to_delete.py" in diff_del["deleted"]


def test_merge_worktree_to_root(tmp_path):
    """Validates atomic merge of worktree modifications back to workspace root."""
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "obsolete.py").write_text("deprecated\n", encoding="utf-8")

    mgr = WorktreeManager(workspace_root=tmp_path)
    wt_path = mgr.create_worktree("subagent-merge-test")

    # Modifications in worktree
    (wt_path / "main.py").write_text("x = 2\ny = 3\n", encoding="utf-8")
    (wt_path / "feature.py").write_text("def feat(): pass\n", encoding="utf-8")
    (wt_path / "obsolete.py").unlink()

    ok, merged_files, diff = mgr.merge_worktree_to_root("subagent-merge-test")
    assert ok is True
    assert "main.py" in merged_files
    assert "feature.py" in merged_files
    assert "obsolete.py" in merged_files

    # Verify root filesystem was updated
    assert (tmp_path / "main.py").read_text(encoding="utf-8") == "x = 2\ny = 3\n"
    assert (tmp_path / "feature.py").is_file()
    assert not (tmp_path / "obsolete.py").exists()


def test_merge_worktree_no_changes(tmp_path):
    """Validates merge when worktree has no changes."""
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    mgr = WorktreeManager(workspace_root=tmp_path)
    mgr.create_worktree("subagent-no-changes")

    ok, merged, diff = mgr.merge_worktree_to_root("subagent-no-changes")
    assert ok is True
    assert merged == []
    assert "No modifications" in diff


def test_destroy_and_cleanup_worktrees(tmp_path):
    """Validates teardown of individual and all worktrees."""
    (tmp_path / "file.txt").write_text("content", encoding="utf-8")
    mgr = WorktreeManager(workspace_root=tmp_path)

    wt1 = mgr.create_worktree("wt-1")
    wt2 = mgr.create_worktree("wt-2")
    assert wt1.exists()
    assert wt2.exists()
    assert len(mgr.list_active_worktrees()) == 2

    # Destroy wt-1
    mgr.destroy_worktree("wt-1")
    assert not wt1.exists()
    assert "wt-1" not in mgr.baselines
    assert len(mgr.list_active_worktrees()) == 1

    # Cleanup all
    count = mgr.cleanup_all_worktrees()
    assert count == 1
    assert not wt2.exists()
    assert len(mgr.list_active_worktrees()) == 0


def test_concurrent_subagents_worktree_isolation(tmp_path):
    """Validates that concurrent subagents operate in completely isolated worktrees without collisions."""
    (tmp_path / "shared.py").write_text("version = 1.0\n", encoding="utf-8")

    mgr = WorktreeManager(workspace_root=tmp_path)
    wt_coder = mgr.create_worktree("subagent-coder")
    wt_tester = mgr.create_worktree("subagent-tester")

    # Coder edits shared.py and adds coder.py
    (wt_coder / "shared.py").write_text("version = 2.0 # coder edit\n", encoding="utf-8")
    (wt_coder / "coder.py").write_text("# coder\n", encoding="utf-8")

    # Tester edits shared.py differently and adds test.py
    (wt_tester / "shared.py").write_text("version = 1.0 # tester edit\n", encoding="utf-8")
    (wt_tester / "test.py").write_text("# test\n", encoding="utf-8")

    # Verify tester does NOT see coder's files
    assert not (wt_tester / "coder.py").exists()
    assert not (wt_coder / "test.py").exists()

    # Verify diffs are isolated
    coder_diff = mgr.get_worktree_diff("subagent-coder")
    tester_diff = mgr.get_worktree_diff("subagent-tester")

    assert "coder.py" in coder_diff["added"]
    assert "coder.py" not in tester_diff["added"]

    assert "test.py" in tester_diff["added"]
    assert "test.py" not in coder_diff["added"]
