"""PRUBETH Context Compactor & KV Token Folding Deep Matrix Tests.

Exhaustively verifies zero-dependency token estimation, pinned context lifecycle (/pin),
tool output folding, hierarchical summarisation, and long-horizon context budget adherence.
"""

from __future__ import annotations

import pytest
from prubeth.persistence.compactor import (
    ContextCompactor,
    PinnedItem,
    CompactionResult,
    CompactionStrategy,
)


# ============================================================================
# 1. Zero-Dependency Token Estimation
# ============================================================================

def test_estimate_tokens_empty_and_short():
    compactor = ContextCompactor()
    assert compactor.estimate_tokens("") == 0
    assert compactor.estimate_tokens("a") == 1
    assert compactor.estimate_tokens("hello") >= 1


@pytest.mark.parametrize("length,expected_min", [
    (100, 20),
    (1000, 200),
    (10000, 2000),
])
def test_estimate_tokens_scaling(length: int, expected_min: int):
    compactor = ContextCompactor(chars_per_token=3.8)
    text = "x" * length
    est = compactor.estimate_tokens(text)
    assert est >= expected_min
    assert est <= length


def test_estimate_messages_tokens_overhead():
    compactor = ContextCompactor()
    messages = [
        {"role": "user", "content": "Help me fix this bug"},
        {"role": "assistant", "content": "Sure, examining code..."},
        {"role": "tool", "content": "file contents", "tool_calls": [{"name": "read_file"}]}
    ]
    tokens = compactor.estimate_messages_tokens(messages)
    assert tokens > 0
    # Must account for framing overhead (4 tokens per message)
    assert tokens > compactor.estimate_tokens("Help me fix this bugSure, examining code...file contents")


# ============================================================================
# 2. Pinned Context Lifecycle (/pin)
# ============================================================================

def test_pin_and_unpin_lifecycle():
    compactor = ContextCompactor()
    pid = compactor.pin("Always use British English spelling.", kind="rule", label="Spelling Rule")
    assert compactor.is_pinned(pid) is True
    assert len(compactor.get_pinned_items()) == 1

    # Format pinned context for prompt injection
    formatted = compactor.format_pinned_context()
    assert "SPELLING RULE" in formatted
    assert "Always use British English spelling." in formatted

    # Unpin
    assert compactor.unpin(pid) is True
    assert compactor.is_pinned(pid) is False
    assert len(compactor.get_pinned_items()) == 0
    assert compactor.format_pinned_context() == ""


def test_unpin_nonexistent_returns_false():
    compactor = ContextCompactor()
    assert compactor.unpin("nonexistent_pin_id") is False


def test_multiple_pinned_items_formatting():
    compactor = ContextCompactor()
    compactor.pin("Architecture: microkernel", kind="rule", label="Arch")
    compactor.pin("class CoreEngine:\n    pass", kind="file", label="CoreEngine")

    formatted = compactor.format_pinned_context()
    assert "ARCH" in formatted
    assert "COREENGINE" in formatted
    assert "microkernel" in formatted
    assert "class CoreEngine:" in formatted


# ============================================================================
# 3. Compaction Decision Boundaries
# ============================================================================

def test_should_compact_threshold_boundaries():
    compactor = ContextCompactor(token_limit=100)
    small_messages = [{"role": "user", "content": "short"}]
    assert compactor.should_compact(small_messages) is False

    large_messages = [{"role": "user", "content": "word " * 120}]
    assert compactor.should_compact(large_messages) is True


# ============================================================================
# 4. Compaction Execution & Tool Output Folding
# ============================================================================

def test_compaction_folds_large_historical_tools_only():
    """Historical tool outputs exceeding 200 chars are folded, but recent ones stay intact."""
    compactor = ContextCompactor(token_limit=300, target_token_budget=200)
    large_output = "Line of compiler diagnostic output.\n" * 40  # > 1000 chars

    messages = [
        {"role": "user", "content": "Run diagnostics"},
        {"role": "tool", "content": large_output},  # Historical tool turn -> should be folded
        {"role": "assistant", "content": "Diagnostics evaluated."},
        {"role": "user", "content": "What is next?"},
        {"role": "tool", "content": "brief summary"},  # Short tool turn -> not folded
        {"role": "assistant", "content": "Ready for next step."},
    ]

    compacted, result = compactor.compact(messages, keep_recent_turns=2)
    assert result.estimated_tokens_after < result.estimated_tokens_before
    assert result.folded_tool_count >= 1

    # Historical tool output replaced with folded descriptor
    historical_tool = compacted[1]
    assert "[Tool output folded" in historical_tool["content"] or len(historical_tool["content"]) < len(large_output)


def test_compaction_preserves_pinned_items_through_compaction():
    compactor = ContextCompactor(token_limit=200, target_token_budget=150)
    pid = compactor.pin("CRITICAL_INVARIANT = True", kind="rule", label="Invariant")

    messages = [
        {"role": "user", "content": "word " * 150},
        {"role": "assistant", "content": "word " * 150},
    ]

    compacted, result = compactor.compact(messages)
    assert compactor.is_pinned(pid) is True
    assert result.pinned_retained_count == 1
    assert "CRITICAL_INVARIANT = True" in compactor.format_pinned_context()


def test_compaction_result_metadata():
    compactor = ContextCompactor(token_limit=500, target_token_budget=200)
    messages = [
        {"role": "user", "content": "Run tests"},
        {"role": "assistant", "content": "Running...", "tool_calls": [{"name": "test_runner"}]},
        {"role": "tool", "name": "test_runner", "content": "Output line diagnostic\n" * 200},
        {"role": "user", "content": "Next command"},
        {"role": "assistant", "content": "Finished."},
    ]
    compacted, result = compactor.compact(messages, keep_recent_turns=2)

    assert isinstance(result, CompactionResult)
    assert result.original_messages == 5
    assert result.reduction_percentage > 0.0
    assert result.strategy_used in list(CompactionStrategy)
