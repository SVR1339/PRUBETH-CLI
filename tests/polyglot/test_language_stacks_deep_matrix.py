"""PRUBETH Language Stacks & Directive Synthesis Matrix Tests.

Exhaustively verifies all 13 LanguageStack ecosystem definitions, extensions,
marker files, default commands, framework detection mappings, and PRUBETH.md
context directive generation.
"""

from __future__ import annotations

import pytest

from prubeth.polyglot.stacks import (
    LanguageStack,
    SUPPORTED_STACKS,
    get_stack_by_id,
)


# ============================================================================
# 1. Supported Stacks Invariants
# ============================================================================

def test_supported_stacks_count_exactly_13():
    assert len(SUPPORTED_STACKS) == 13


@pytest.mark.parametrize("stack_id", [
    "python",
    "typescript",
    "javascript",
    "rust",
    "go",
    "java",
    "csharp",
    "cpp",
    "dart",
    "php",
    "ruby",
    "kotlin",
    "swift",
])
def test_all_13_stacks_exist_and_retrievable(stack_id: str):
    stack = get_stack_by_id(stack_id)
    assert stack is not None
    assert stack.id == stack_id
    assert len(stack.name) > 0
    assert len(stack.extensions) > 0
    assert len(stack.markers) > 0
    assert len(stack.default_test_cmd) > 0
    assert len(stack.default_build_cmd) > 0
    assert len(stack.default_lint_cmd) > 0
    assert len(stack.default_run_cmd) > 0


def test_get_stack_case_insensitive():
    s1 = get_stack_by_id("RUST")
    s2 = get_stack_by_id("rust")
    assert s1 is s2
    assert s1.id == "rust"


def test_get_stack_unknown_returns_none():
    assert get_stack_by_id("non_existent_lang_xyz") is None


# ============================================================================
# 2. Ecosystem Specific Markers & Commands
# ============================================================================

def test_python_stack_invariants():
    stack = get_stack_by_id("python")
    assert ".py" in stack.extensions
    assert "pyproject.toml" in stack.markers
    assert "pytest" in stack.default_test_cmd


def test_typescript_stack_invariants():
    stack = get_stack_by_id("typescript")
    assert ".ts" in stack.extensions
    assert ".tsx" in stack.extensions
    assert "tsconfig.json" in stack.markers
    assert "npm test" in stack.default_test_cmd or "jest" in stack.default_test_cmd


def test_rust_stack_invariants():
    stack = get_stack_by_id("rust")
    assert ".rs" in stack.extensions
    assert "Cargo.toml" in stack.markers
    assert "cargo test" in stack.default_test_cmd
    assert "cargo clippy" in stack.default_lint_cmd


def test_go_stack_invariants():
    stack = get_stack_by_id("go")
    assert ".go" in stack.extensions
    assert "go.mod" in stack.markers
    assert "go test" in stack.default_test_cmd


def test_dart_stack_invariants():
    stack = get_stack_by_id("dart")
    assert ".dart" in stack.extensions
    assert "pubspec.yaml" in stack.markers
    assert "dart test" in stack.default_test_cmd or "flutter test" in stack.default_test_cmd


def test_ruby_stack_invariants():
    stack = get_stack_by_id("ruby")
    assert ".rb" in stack.extensions
    assert "Gemfile" in stack.markers
    assert "rspec" in stack.default_test_cmd or "bundle" in stack.default_test_cmd


def test_php_stack_invariants():
    stack = get_stack_by_id("php")
    assert ".php" in stack.extensions
    assert "composer.json" in stack.markers


def test_csharp_stack_invariants():
    stack = get_stack_by_id("csharp")
    assert ".cs" in stack.extensions
    assert any(".csproj" in m or ".sln" in m for m in stack.markers)
    assert "dotnet test" in stack.default_test_cmd


# ============================================================================
# 3. PRUBETH.md Directive Synthesis
# ============================================================================

@pytest.mark.parametrize("stack_id", list(SUPPORTED_STACKS.keys()))
def test_generate_prubeth_md_contains_key_sections(stack_id: str):
    stack = get_stack_by_id(stack_id)
    doc = stack.generate_prubeth_md("my_cool_project")

    assert "# Project Instructions (PRUBETH.md)" in doc
    assert stack.name in doc
    assert "my_cool_project" in doc
    assert stack.default_test_cmd in doc
    assert stack.default_build_cmd in doc
    assert stack.default_lint_cmd in doc
    assert "British English" in doc or "Verification Gate" in doc
