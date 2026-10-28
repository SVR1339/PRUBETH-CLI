"""PRUBETH Pinned Context & KV Cache Anchor Matrix Tests.

Exhaustively verifies PinnedContextManager: load, save, pin, unpin, clear,
relative path normalisation, duplicate prevention, non-existent file handling,
context attachments formatting, and rich console render output.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from prubeth.persistence.pinned import PinnedContextManager


# ============================================================================
# 1. Initialization and Directory Creation
# ============================================================================

def test_pinned_manager_creates_prubeth_directory(tmp_path: Path):
    mgr = PinnedContextManager(workspace_root=tmp_path)
    assert (tmp_path / ".prubeth").exists()
    assert mgr.load_pinned() == []


def test_pinned_manager_empty_when_no_file(tmp_path: Path):
    mgr = PinnedContextManager(workspace_root=tmp_path)
    assert mgr.load_pinned() == []


# ============================================================================
# 2. Pinning Files
# ============================================================================

def test_pin_valid_file(tmp_path: Path):
    f = tmp_path / "src" / "schema.sql"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("CREATE TABLE users (id INT PRIMARY KEY);", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    ok = mgr.pin("src/schema.sql")
    assert ok is True
    pinned = mgr.load_pinned()
    assert len(pinned) == 1
    assert pinned[0] == "src/schema.sql"


def test_pin_non_existent_file_returns_false(tmp_path: Path):
    mgr = PinnedContextManager(workspace_root=tmp_path)
    ok = mgr.pin("does_not_exist.py")
    assert ok is False
    assert mgr.load_pinned() == []


def test_pin_duplicate_file_idempotent(tmp_path: Path):
    f = tmp_path / "types.ts"
    f.write_text("export interface User { id: string; }", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    ok1 = mgr.pin("types.ts")
    ok2 = mgr.pin("types.ts")
    assert ok1 is True
    assert ok2 is True
    pinned = mgr.load_pinned()
    assert len(pinned) == 1


def test_pin_windows_backslash_normalized(tmp_path: Path):
    f = tmp_path / "models" / "user.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("class User: pass", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    ok = mgr.pin(r"models\user.py")
    assert ok is True
    pinned = mgr.load_pinned()
    assert "models/user.py" in pinned
    assert "\\" not in pinned[0]


# ============================================================================
# 3. Unpinning Files
# ============================================================================

def test_unpin_existing_file(tmp_path: Path):
    f = tmp_path / "config.yaml"
    f.write_text("env: prod", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    mgr.pin("config.yaml")
    assert len(mgr.load_pinned()) == 1

    ok = mgr.unpin("config.yaml")
    assert ok is True
    assert mgr.load_pinned() == []


def test_unpin_non_pinned_file_returns_false(tmp_path: Path):
    mgr = PinnedContextManager(workspace_root=tmp_path)
    ok = mgr.unpin("never_pinned.py")
    assert ok is False


def test_unpin_by_filename_only(tmp_path: Path):
    f = tmp_path / "deep" / "nested" / "contract.proto"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("syntax = 'proto3';", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    mgr.pin("deep/nested/contract.proto")
    assert len(mgr.load_pinned()) == 1

    # Unpin by base filename
    ok = mgr.unpin("contract.proto")
    assert ok is True
    assert mgr.load_pinned() == []


# ============================================================================
# 4. Clearing and Resetting
# ============================================================================

def test_clear_all_pinned_files(tmp_path: Path):
    for name in ["a.py", "b.py", "c.py"]:
        f = tmp_path / name
        f.write_text("x = 1", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    mgr.pin("a.py")
    mgr.pin("b.py")
    mgr.pin("c.py")
    assert len(mgr.load_pinned()) == 3

    mgr.clear()
    assert mgr.load_pinned() == []


# ============================================================================
# 5. Context Attachments for LLM Prompt Injection
# ============================================================================

def test_get_context_attachments_formats_code_fence(tmp_path: Path):
    f = tmp_path / "core.py"
    f.write_text("def run(): return 42", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    mgr.pin("core.py")

    attachments = mgr.get_context_attachments()
    assert len(attachments) == 1
    att = attachments[0]
    assert att["type"] == "pinned_file"
    assert "core.py" in att["label"]
    assert "def run(): return 42" in att["content"]
    assert "# [PINNED CONTEXT]" in att["content"]


def test_get_context_attachments_skips_deleted_files(tmp_path: Path):
    f = tmp_path / "transient.py"
    f.write_text("temp = 1", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    mgr.pin("transient.py")
    f.unlink()  # File removed from disk

    attachments = mgr.get_context_attachments()
    assert len(attachments) == 0


def test_render_list_runs_without_exceptions(tmp_path: Path):
    f = tmp_path / "lib.py"
    f.write_text("class Lib: pass", encoding="utf-8")

    mgr = PinnedContextManager(workspace_root=tmp_path)
    mgr.pin("lib.py")
    # Must execute cleanly
    mgr.render_list()
