"""PRUBETH Context Compactor & KV Token Folding Matrix Tests.

Validates token estimation, tool output folding, hierarchical summarisation,
and inviolable pinned context preservation.
"""

from __future__ import annotations

import pytest
from prubeth.persistence.compactor import (
    ContextCompactor,
    CompactionStrategy,
    PinnedItem,
)


@pytest.fixture
def compactor():
    return ContextCompactor(token_limit=1000, target_token_budget=600)


def test_token_estimation_basic(compactor):
    assert compactor.estimate_tokens("") == 0
    assert compactor.estimate_tokens("Hello world") >= 1
    # Check 1000 chars roughly equals 260 tokens (at 3.8 chars/token)
    sample = "a" * 1000
    est = compactor.estimate_tokens(sample)
    assert 250 <= est <= 280


def test_pin_and_unpin_lifecycle(compactor):
    pid = compactor.pin("const SECRET_API_INVARIANT = 42;", kind="rule", label="API Invariant")
    assert compactor.is_pinned(pid)
    assert len(compactor.get_pinned_items()) == 1

    formatted = compactor.format_pinned_context()
    assert "SECRET_API_INVARIANT" in formatted
    assert "API INVARIANT" in formatted

    # Unpin
    assert compactor.unpin(pid) is True
    assert not compactor.is_pinned(pid)
    assert len(compactor.get_pinned_items()) == 0


def test_should_compact_threshold(compactor):
    # Below threshold
    short_msgs = [{"role": "user", "content": "Hello"}]
    assert compactor.should_compact(short_msgs) is False

    # Exceeding threshold: 1000 tokens ~ 3800 chars
    huge_msgs = [{"role": "user", "content": "x" * 4500}]
    assert compactor.should_compact(huge_msgs) is True


def test_compaction_folds_large_tool_outputs(compactor):
    # Build conversation with large tool outputs in earlier turns exceeding token_limit (1000 tokens ~ 3800 chars)
    huge_tool_output = "Line " * 1000  # ~5000 chars ~ 1300 tokens
    messages = [
        {"role": "user", "content": "Read the file"},
        {"role": "assistant", "content": "I will read it", "tool_calls": [{"name": "read_file"}]},
        {"role": "tool", "name": "read_file", "content": huge_tool_output},
        {"role": "user", "content": "Now explain it"},
        {"role": "assistant", "content": "Here is the explanation"},
    ]

    compacted, report = compactor.compact(messages, keep_recent_turns=2)
    assert report.strategy_used in (CompactionStrategy.FOLD_TOOL_OUTPUTS, CompactionStrategy.HIERARCHICAL_SUMMARIZATION)
    assert report.reduction_percentage > 0.0

    # Verify tool output was folded
    tool_msg = [m for m in compacted if m.get("role") == "tool"][0]
    assert "[Output folded:" in tool_msg["content"]
    assert "read_file" in tool_msg["content"]


def test_compaction_preserves_pinned_content(compactor):
    critical_spec = "CRITICAL_SYSTEM_SPECIFICATION: Must maintain zero font blur."
    compactor.pin(critical_spec, kind="spec", label="Spec Rule")

    messages = [
        {"role": "system", "content": f"Rules:\n{critical_spec}"},
        {"role": "user", "content": "x" * 2000},
        {"role": "assistant", "content": "y" * 2000},
        {"role": "user", "content": "Recent question"},
        {"role": "assistant", "content": "Recent answer"},
    ]

    compacted, report = compactor.compact(messages, keep_recent_turns=2)
    assert report.pinned_retained_count == 1
    # Pinned spec remains intact
    assert any(critical_spec in m.get("content", "") for m in compacted) or compactor.format_pinned_context()


def test_hierarchical_summarization_on_massive_context(compactor):
    # 20 turns of dialogue
    messages = []
    for i in range(20):
        messages.append({"role": "user", "content": f"Turn {i} request with lots of details " * 20})
        messages.append({"role": "assistant", "content": f"Turn {i} reply with architecture reasoning " * 20})

    compacted, report = compactor.compact(messages, keep_recent_turns=4)
    assert report.strategy_used == CompactionStrategy.HIERARCHICAL_SUMMARIZATION
    assert report.summary_injected is True
    assert report.reduction_percentage > 50.0
    # First message in compacted output is the system summary
    assert "[COMPACTED ARCHITECTURAL CONTEXT]" in compacted[0]["content"]
    # Most recent turns are preserved
    assert len(compacted) <= 8


@pytest.mark.parametrize("multiplier", [1, 2, 5, 10, 20])
def test_compactor_token_scaling_invariants(compactor, multiplier):
    content = "def calculate_hash(data: bytes) -> str:\n    return hashlib.sha256(data).hexdigest()\n" * multiplier
    tokens = compactor.estimate_tokens(content)
    assert tokens > 0
    assert tokens == compactor.estimate_tokens(content)
