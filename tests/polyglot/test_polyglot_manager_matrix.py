"""PRUBETH Polyglot Language Manager Matrix Tests.

Exhaustively verifies PolyglotLanguageManager workspace marker detection,
user configuration overrides, dynamic fallback to auto, list_all_stacks metadata,
and unknown language handling.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.config.manager import ConfigManager
from prubeth.polyglot.manager import PolyglotLanguageManager
from prubeth.polyglot.stacks import SUPPORTED_STACKS, detect_stack_from_workspace


# ============================================================================
# 1. Dynamic Workspace Stack Detection Matrix
# ============================================================================

def test_detect_python_workspace(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "python"


def test_detect_rust_workspace(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname="app"\n', encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "rust"


def test_detect_go_workspace(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module example.com/app\ngo 1.22\n", encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "go"


def test_detect_typescript_workspace(tmp_path: Path):
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "typescript"


def test_detect_javascript_workspace(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name": "app"}', encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "javascript"


def test_detect_java_workspace(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "java"


def test_detect_dart_workspace(tmp_path: Path):
    (tmp_path / "pubspec.yaml").write_text("name: flutter_app\n", encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "dart"


def test_detect_ruby_workspace(tmp_path: Path):
    (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "ruby"


def test_detect_php_workspace(tmp_path: Path):
    (tmp_path / "composer.json").write_text("{}", encoding="utf-8")
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "php"


def test_detect_empty_workspace_defaults_to_python(tmp_path: Path):
    stack = detect_stack_from_workspace(tmp_path)
    assert stack.id == "python"


# ============================================================================
# 2. Configured Language Overrides
# ============================================================================

def test_configured_override_takes_precedence_over_markers(tmp_path: Path):
    # Workspace has Cargo.toml (Rust)
    (tmp_path / "Cargo.toml").write_text('[package]\nname="app"\n', encoding="utf-8")

    cfg_dir = tmp_path / "cfg"
    cfg_mgr = ConfigManager(config_dir=cfg_dir)
    mgr = PolyglotLanguageManager(workspace_root=tmp_path, config_manager=cfg_mgr)

    # Set override to Go
    ok, msg = mgr.set_default_language("go")
    assert ok is True

    resolved = mgr.resolve_active_stack()
    assert resolved.id == "go"


def test_set_default_language_auto_reverts_to_markers(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname="app"\n', encoding="utf-8")

    cfg_dir = tmp_path / "cfg"
    cfg_mgr = ConfigManager(config_dir=cfg_dir)
    mgr = PolyglotLanguageManager(workspace_root=tmp_path, config_manager=cfg_mgr)

    mgr.set_default_language("go")
    assert mgr.resolve_active_stack().id == "go"

    # Revert to auto
    ok, msg = mgr.set_default_language("auto")
    assert ok is True
    assert mgr.resolve_active_stack().id == "rust"


def test_set_default_language_unknown_rejected(tmp_path: Path):
    cfg_dir = tmp_path / "cfg"
    cfg_mgr = ConfigManager(config_dir=cfg_dir)
    mgr = PolyglotLanguageManager(workspace_root=tmp_path, config_manager=cfg_mgr)

    ok, msg = mgr.set_default_language("cobol_ancient")
    assert ok is False
    assert "Unknown language stack" in msg


# ============================================================================
# 3. Metadata Listing
# ============================================================================

def test_list_all_stacks_contains_all_13(tmp_path: Path):
    cfg_mgr = ConfigManager(config_dir=tmp_path / "cfg")
    mgr = PolyglotLanguageManager(workspace_root=tmp_path, config_manager=cfg_mgr)
    stacks = mgr.list_all_stacks()
    assert len(stacks) == 13

    ids = [s["id"] for s in stacks]
    assert "python" in ids
    assert "rust" in ids
    assert "typescript" in ids


def test_list_all_stacks_flags_active_stack(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname="app"\n', encoding="utf-8")
    cfg_mgr = ConfigManager(config_dir=tmp_path / "cfg")
    mgr = PolyglotLanguageManager(workspace_root=tmp_path, config_manager=cfg_mgr)
    stacks = mgr.list_all_stacks()

    rust_stack = next(s for s in stacks if s["id"] == "rust")
    assert rust_stack["is_active"] is True

    python_stack = next(s for s in stacks if s["id"] == "python")
    assert python_stack["is_active"] is False
