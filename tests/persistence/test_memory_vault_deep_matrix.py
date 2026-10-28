"""PRUBETH Memory Vault & Continuous Learning Ledger Matrix Tests.

Exhaustively verifies MemoryVault (Subsystem 12): markdown file initialisation,
anti-pattern recording, architectural decision recording, get_memory_context distillation,
structured anti-pattern listing, truncation limits, and persistence invariants.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.persistence.memory import MemoryVault


# ============================================================================
# 1. Directory and Ledger Initialisation
# ============================================================================

def test_memory_vault_initialises_files(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    assert (tmp_path / "anti-patterns.md").exists()
    assert (tmp_path / "decisions.md").exists()


def test_memory_vault_headers_present(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    anti_text = (tmp_path / "anti-patterns.md").read_text(encoding="utf-8")
    assert "Learned Anti-Patterns Ledger" in anti_text

    dec_text = (tmp_path / "decisions.md").read_text(encoding="utf-8")
    assert "Architectural Decisions Ledger" in dec_text


# ============================================================================
# 2. Recording Anti-Patterns
# ============================================================================

def test_record_anti_pattern_appends_entry(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    vault.record_anti_pattern(
        failing_component="SQLite Connection Pool",
        error_symptom="OperationalError: database is locked",
        root_cause="Concurrent write operations without WAL journal mode.",
        prevention_rule="Always configure PRAGMA journal_mode=WAL and acquire threading.RLock."
    )

    content = (tmp_path / "anti-patterns.md").read_text(encoding="utf-8")
    assert "SQLite Connection Pool" in content
    assert "OperationalError: database is locked" in content
    assert "Always configure PRAGMA journal_mode=WAL" in content


def test_record_multiple_anti_patterns(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    vault.record_anti_pattern("Comp1", "Symp1", "Cause1", "Rule1")
    vault.record_anti_pattern("Comp2", "Symp2", "Cause2", "Rule2")

    patterns = vault.list_anti_patterns()
    assert len(patterns) >= 2


# ============================================================================
# 3. Recording Architectural Decisions
# ============================================================================

def test_record_decision_appends_entry(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    vault.record_decision(
        decision_title="Adopt Rich Boxed Terminal UI Standard",
        rationale="Guarantees 0% font blur on Windows CP65001 and consistent ANSI borders.",
        affected_modules=["prubeth.cli.hud", "prubeth.cli.dashboard"]
    )

    content = (tmp_path / "decisions.md").read_text(encoding="utf-8")
    assert "Adopt Rich Boxed Terminal UI Standard" in content
    assert "prubeth.cli.hud" in content
    assert "0% font blur" in content


# ============================================================================
# 4. Context Distillation for LLM System Prompt
# ============================================================================

def test_get_memory_context_empty_ledger_clean(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    ctx = vault.get_memory_context()
    # Empty ledger returns empty or minimal header
    assert isinstance(ctx, str)


def test_get_memory_context_includes_both_ledgers(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    vault.record_anti_pattern("MemoryGate", "OOM", "No compaction", "Use ContextCompactor")
    vault.record_decision("Offline First", "Zero external network dependency for local models", ["prubeth.models"])

    ctx = vault.get_memory_context()
    assert "Learned Project Anti-Patterns" in ctx
    assert "MemoryGate" in ctx
    assert "Architectural Invariants & Decisions" in ctx
    assert "Offline First" in ctx


def test_get_memory_context_respects_max_chars(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    for i in range(10):
        vault.record_anti_pattern(f"Component_{i}", f"Error_{i}", f"Cause_{i}", f"Rule_{i}")

    ctx = vault.get_memory_context(max_chars=500)
    assert len(ctx) <= 500


# ============================================================================
# 5. Parsing Structured Anti-Patterns
# ============================================================================

def test_list_anti_patterns_structured_fields(tmp_path: Path):
    vault = MemoryVault(memory_dir=tmp_path)
    vault.record_anti_pattern(
        failing_component="HTTP Retry Layer",
        error_symptom="Thundering herd 429",
        root_cause="Fixed retry delay without jitter.",
        prevention_rule="Use full jitter exponential backoff."
    )

    items = vault.list_anti_patterns()
    assert len(items) == 1
    item = items[0]
    assert item["component"] == "HTTP Retry Layer"
    assert "Thundering herd 429" in item["symptom"]
    assert "Fixed retry delay" in item["root_cause"]
    assert "exponential backoff" in item["prevention_rule"]
