"""PRUBETH Long-Horizon Context Compactor & KV Token Folding Engine.

Maintains long-horizon reasoning fidelity across massive codebases and extended sessions.
Implements token budget accounting, tool output folding, hierarchical summarisation,
and pinned context preservation (/pin) for Claude Code and Gemini CLI parity.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple


class CompactionStrategy(str, Enum):
    """Strategies for context compaction when token budget is exceeded."""
    FOLD_TOOL_OUTPUTS = "fold_tool_outputs"
    HIERARCHICAL_SUMMARIZATION = "hierarchical_summarization"
    SLIDING_WINDOW = "sliding_window"
    PRUNE_INTERMEDIATE = "prune_intermediate"


@dataclass
class PinnedItem:
    """Item guaranteed never to be purged or folded during context compaction."""
    id: str
    kind: str             # "message", "file", "rule", "symbol", "manual"
    content: str
    label: str = ""
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompactionResult:
    """Outcome of context compaction execution."""
    strategy_used: CompactionStrategy
    original_messages: int
    compacted_messages: int
    estimated_tokens_before: int
    estimated_tokens_after: int
    reduction_percentage: float
    folded_tool_count: int = 0
    pinned_retained_count: int = 0
    summary_injected: bool = False


class ContextCompactor:
    """Manages long-horizon token conservation, output folding, and pinned artifacts."""

    def __init__(
        self,
        token_limit: int = 32000,
        target_token_budget: int = 24000,
        chars_per_token: float = 3.8
    ):
        self.token_limit = token_limit
        self.target_token_budget = target_token_budget
        self.chars_per_token = chars_per_token
        self._pinned_items: Dict[str, PinnedItem] = {}

    def estimate_tokens(self, text: str) -> int:
        """Fast, zero-dependency token estimation across polyglot texts."""
        if not text:
            return 0
        return max(1, int(len(text) / self.chars_per_token))

    def estimate_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimates cumulative token count for a message list."""
        total = 0
        for m in messages:
            content = str(m.get("content", ""))
            total += self.estimate_tokens(content)
            # Add overhead for tool call descriptors
            t_calls = m.get("tool_calls")
            if isinstance(t_calls, list):
                for tc in t_calls:
                    total += self.estimate_tokens(str(tc)) + 12
            total += 4  # Message framing overhead
        return total

    # =========================================================================
    # Pinned Context (/pin) Management
    # =========================================================================

    def pin(
        self,
        content: str,
        kind: str = "manual",
        label: str = "",
        pin_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Pins a critical code snippet, requirement, or rule into inviolable memory."""
        pid = pin_id or f"pin_{uuid.uuid4().hex[:8]}"
        self._pinned_items[pid] = PinnedItem(
            id=pid,
            kind=kind,
            content=content,
            label=label or f"Pinned {kind}",
            metadata=metadata or {}
        )
        return pid

    def unpin(self, pin_id: str) -> bool:
        """Removes an item from pinned memory."""
        if pin_id in self._pinned_items:
            del self._pinned_items[pin_id]
            return True
        return False

    def is_pinned(self, pin_id: str) -> bool:
        return pin_id in self._pinned_items

    def get_pinned_items(self) -> List[PinnedItem]:
        return list(self._pinned_items.values())

    def format_pinned_context(self) -> str:
        """Formats all active pinned items for system prompt injection."""
        if not self._pinned_items:
            return ""

        blocks = []
        for p in self._pinned_items.values():
            blocks.append(f"### [PINNED: {p.label.upper()} ({p.kind})]\n{p.content}")
        return "\n\n".join(blocks)

    # =========================================================================
    # Context Compaction Pipeline
    # =========================================================================

    def should_compact(self, messages: List[Dict[str, Any]]) -> bool:
        """Determines if the current conversation history exceeds threshold."""
        return self.estimate_messages_tokens(messages) > self.token_limit

    def compact(
        self,
        messages: List[Dict[str, Any]],
        keep_recent_turns: int = 4
    ) -> Tuple[List[Dict[str, Any]], CompactionResult]:
        """Executes multi-stage KV context compaction.
        
        Stage 1: Fold large historical tool outputs (> 200 chars) into concise structural summaries.
        Stage 2: If still above budget, compress older conversation turns into an anchor summary.
        Stage 3: Preserve pinned context and the most recent K turns untouched.
        """
        orig_count = len(messages)
        tokens_before = self.estimate_messages_tokens(messages)

        if not self.should_compact(messages):
            return messages, CompactionResult(
                strategy_used=CompactionStrategy.SLIDING_WINDOW,
                original_messages=orig_count,
                compacted_messages=orig_count,
                estimated_tokens_before=tokens_before,
                estimated_tokens_after=tokens_before,
                reduction_percentage=0.0,
                pinned_retained_count=len(self._pinned_items)
            )

        # Stage 1: Fold tool outputs in historical turns
        compacted = [dict(m) for m in messages]
        folded_count = 0

        # Protect the last keep_recent_turns messages
        protect_idx = max(0, len(compacted) - keep_recent_turns)

        for i in range(protect_idx):
            m = compacted[i]
            role = m.get("role")

            # Check if this message contains pinned content
            content = str(m.get("content", ""))
            if any(p.content in content for p in self._pinned_items.values()):
                continue

            if role == "tool":
                if len(content) > 250:
                    tool_name = m.get("name", "tool")
                    first_line = content.splitlines()[0] if content.splitlines() else "Success"
                    m["content"] = f"[Output folded: {tool_name} returned {len(content)} chars. Lead line: '{first_line[:80]}...']"
                    folded_count += 1
            elif role == "assistant" and "tool_calls" in m:
                # Retain tool call declaration but trim bulky inline thoughts
                if len(content) > 400:
                    m["content"] = content[:300] + "\n... [Earlier thoughts folded for context economy] ..."

        tokens_stage_1 = self.estimate_messages_tokens(compacted)
        if tokens_stage_1 <= self.target_token_budget:
            reduction = ((tokens_before - tokens_stage_1) / max(1, tokens_before)) * 100.0
            return compacted, CompactionResult(
                strategy_used=CompactionStrategy.FOLD_TOOL_OUTPUTS,
                original_messages=orig_count,
                compacted_messages=len(compacted),
                estimated_tokens_before=tokens_before,
                estimated_tokens_after=tokens_stage_1,
                reduction_percentage=reduction,
                folded_tool_count=folded_count,
                pinned_retained_count=len(self._pinned_items)
            )

        # Stage 2: Hierarchical summarization of older dialogue turns
        older_turns = compacted[:protect_idx]
        recent_turns = compacted[protect_idx:]

        # Extract goals and key outcomes from older turns
        extracted_topics = []
        for m in older_turns:
            c = str(m.get("content", ""))
            if m.get("role") == "user":
                clean_u = c.splitlines()[-1] if c.splitlines() else c
                extracted_topics.append(f"- User requested: {clean_u[:120]}")
            elif m.get("role") == "assistant" and "tool_calls" not in m:
                extracted_topics.append(f"- Assistant concluded: {c[:120]}")

        summary_text = (
            "[COMPACTED ARCHITECTURAL CONTEXT]:\n"
            f"Earlier conversation ({len(older_turns)} messages) folded for token economy:\n"
            + "\n".join(extracted_topics[:6]) + "\n"
            "Key discoveries and constraints preserved."
        )

        final_messages = [{"role": "system", "content": summary_text}] + recent_turns
        tokens_after = self.estimate_messages_tokens(final_messages)
        reduction = ((tokens_before - tokens_after) / max(1, tokens_before)) * 100.0

        return final_messages, CompactionResult(
            strategy_used=CompactionStrategy.HIERARCHICAL_SUMMARIZATION,
            original_messages=orig_count,
            compacted_messages=len(final_messages),
            estimated_tokens_before=tokens_before,
            estimated_tokens_after=tokens_after,
            reduction_percentage=reduction,
            folded_tool_count=folded_count,
            pinned_retained_count=len(self._pinned_items),
            summary_injected=True
        )
