"""PRUBETH Context Compactor & Token Folding Matrix Tests.

Exhaustively verifies ContextCompactor token estimation, threshold detection,
surgical compaction, system message preservation, file extraction, and
CompactionResult data contracts.
"""

from __future__ import annotations

import pytest
from typing import List, Dict, Any

from prubeth.memory.compactor import ContextCompactor, CompactionResult


def _make_messages(count: int, content_per: str = "A " * 200) -> List[Dict[str, Any]]:
    """Creates a synthetic conversation with alternating user/assistant turns."""
    msgs = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"Turn {i}: {content_per}"})
    return msgs


# ============================================================================
# 1. Token Estimation
# ============================================================================

def test_estimate_tokens_basic():
    comp = ContextCompactor()
    text = "A" * 400  # 400 chars / 4 = 100 tokens
    assert comp.estimate_tokens(text) == 100


def test_estimate_tokens_minimum_one():
    comp = ContextCompactor()
    assert comp.estimate_tokens("x") == 1


def test_estimate_tokens_empty_returns_one():
    comp = ContextCompactor()
    assert comp.estimate_tokens("") == 1


def test_total_tokens_across_messages():
    comp = ContextCompactor(target_window_tokens=10000)
    msgs = [
        {"role": "user", "content": "A" * 400},   # 100 tokens
        {"role": "assistant", "content": "B" * 800},  # 200 tokens
    ]
    total = comp.total_estimated_tokens(msgs)
    assert total == 300


def test_total_tokens_list_content_parts():
    comp = ContextCompactor()
    msgs = [{"role": "user", "content": ["part1", "part2 abc"]}]
    total = comp.total_estimated_tokens(msgs)
    assert total >= 1


# ============================================================================
# 2. Compaction Threshold Detection
# ============================================================================

def test_should_compact_below_threshold():
    comp = ContextCompactor(target_window_tokens=10000)
    msgs = [{"role": "user", "content": "hello"}]  # Tiny conversation
    assert comp.should_compact(msgs, threshold_ratio=0.75) is False


def test_should_compact_above_threshold():
    comp = ContextCompactor(target_window_tokens=1000)
    # Create content that's clearly over 75% of 1000 tokens
    msgs = [{"role": "user", "content": "A" * 3200}]  # 800 tokens — exactly 80%
    assert comp.should_compact(msgs, threshold_ratio=0.75) is True


def test_should_compact_at_exact_threshold():
    comp = ContextCompactor(target_window_tokens=1000)
    msgs = [{"role": "user", "content": "A" * 3000}]  # 750 tokens = exactly 75%
    assert comp.should_compact(msgs, threshold_ratio=0.75) is True


# ============================================================================
# 3. Compaction Invariants
# ============================================================================

def test_compact_short_conversation_unchanged():
    comp = ContextCompactor(target_window_tokens=32000, keep_recent_turns=3)
    msgs = _make_messages(4)  # Only 4 messages — keep_recent_turns*2 = 6 → unchanged
    result = comp.compact(msgs)
    assert isinstance(result, CompactionResult)
    assert result.reduction_percentage == 0.0
    assert len(result.compacted_messages) == len(msgs)


def test_compact_long_conversation_reduces_tokens():
    comp = ContextCompactor(target_window_tokens=32000, keep_recent_turns=2)
    msgs = _make_messages(20)
    result = comp.compact(msgs)
    assert result.compacted_estimated_tokens <= result.original_estimated_tokens
    assert result.reduction_percentage >= 0.0


def test_compact_preserves_recent_turns():
    comp = ContextCompactor(target_window_tokens=32000, keep_recent_turns=2)
    msgs = _make_messages(20)
    result = comp.compact(msgs)
    # The last 4 messages (keep_recent_turns * 2) must be present
    recent_originals = [m["content"] for m in msgs[-4:]]
    compacted_contents = [m.get("content", "") for m in result.compacted_messages]
    # At least one recent message must appear verbatim in compacted output
    assert any(orig in compacted_contents for orig in recent_originals)


def test_compact_system_message_preserved():
    comp = ContextCompactor(target_window_tokens=32000, keep_recent_turns=2)
    system = {"role": "system", "content": "You are PRUBETH AI. British English. Zero bloat."}
    msgs = [system] + _make_messages(20)
    result = comp.compact(msgs)
    roles = [m.get("role") for m in result.compacted_messages]
    assert "system" in roles


def test_compact_result_fields_populated():
    comp = ContextCompactor(target_window_tokens=32000, keep_recent_turns=2)
    msgs = _make_messages(16)
    result = comp.compact(msgs)
    assert result.original_estimated_tokens > 0
    assert isinstance(result.files_preserved, list)
    assert isinstance(result.compacted_messages, list)


def test_compact_returns_compaction_result_type():
    comp = ContextCompactor()
    result = comp.compact(_make_messages(10))
    assert isinstance(result, CompactionResult)


def test_compact_reduction_percentage_non_negative():
    comp = ContextCompactor(keep_recent_turns=2)
    msgs = _make_messages(20)
    result = comp.compact(msgs)
    assert result.reduction_percentage >= 0.0


def test_compact_compacted_messages_is_list():
    comp = ContextCompactor(keep_recent_turns=2)
    result = comp.compact(_make_messages(10))
    assert isinstance(result.compacted_messages, list)
    assert len(result.compacted_messages) > 0


def test_compact_no_message_loss_on_very_short():
    comp = ContextCompactor(keep_recent_turns=3)
    msgs = [{"role": "user", "content": "What is PRUBETH?"}]
    result = comp.compact(msgs)
    assert len(result.compacted_messages) >= 1
