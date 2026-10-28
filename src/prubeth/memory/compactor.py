"""PRUBETH Precision In-Memory Context Compaction & Token Folding Micro-Algorithm.

Folds multi-turn conversational history when approaching model context window boundaries,
distilling tool outputs and intermediate turns into structured memory state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple


@dataclass
class CompactionResult:
    compacted_messages: List[Dict[str, Any]]
    original_estimated_tokens: int
    compacted_estimated_tokens: int
    reduction_percentage: float
    files_preserved: List[str]


class ContextCompactor:
    """Manages conversational memory pruning, token folding, and invariant preservation."""

    def __init__(self, target_window_tokens: int = 32000, keep_recent_turns: int = 3):
        self.target_window_tokens = target_window_tokens
        self.keep_recent_turns = keep_recent_turns

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Fast heuristic token estimator (approx. 4 chars per token)."""
        return max(1, len(text) // 4)

    def total_estimated_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Sums estimated token counts across all turns in a conversation."""
        total = 0
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    total += self.estimate_tokens(str(part))
        return total

    def should_compact(self, messages: List[Dict[str, Any]], threshold_ratio: float = 0.75) -> bool:
        """Determines if conversation token consumption has crossed the compaction threshold."""
        current = self.total_estimated_tokens(messages)
        return current >= int(self.target_window_tokens * threshold_ratio)

    def compact(self, messages: List[Dict[str, Any]]) -> CompactionResult:
        """Executes surgical in-memory compaction over message list."""
        orig_tokens = self.total_estimated_tokens(messages)

        if len(messages) <= (self.keep_recent_turns * 2):
            return CompactionResult(
                compacted_messages=messages,
                original_estimated_tokens=orig_tokens,
                compacted_estimated_tokens=orig_tokens,
                reduction_percentage=0.0,
                files_preserved=[]
            )

        # Separate system message if first
        system_msg: Optional[Dict[str, Any]] = None
        working_msgs = list(messages)
        if working_msgs and working_msgs[0].get("role") == "system":
            system_msg = working_msgs.pop(0)

        # Recent turns to preserve verbatim
        recent_count = self.keep_recent_turns * 2
        history_to_fold = working_msgs[:-recent_count]
        recent_to_keep = working_msgs[-recent_count:]

        # Extract files mentioned, decisions made, and tool outcomes
        files_mentioned = set()
        user_objectives = []
        tool_results_summaries = []

        file_pattern = re.compile(r'[\w\-\./\\]+\.(?:py|js|ts|jsx|tsx|rs|go|json|md|toml|html|css)\b')

        for m in history_to_fold:
            role = m.get("role", "")
            content = m.get("content", "")
            if isinstance(content, str):
                # Discover files
                for f in file_pattern.findall(content):
                    if not any(ign in f for ign in ["http", ".git", "__pycache__"]):
                        files_mentioned.add(f)

                if role == "user" and len(content.strip()) > 5:
                    user_objectives.append(content.strip()[:100])
                elif role in ("tool", "function"):
                    tool_name = m.get("name", "tool")
                    tool_results_summaries.append(f"- Tool `{tool_name}` executed.")

        # Synthesize structured memory anchor
        summary_blocks = [
            "### [PRUBETH IN-MEMORY COMPACTED SESSION STATE]",
            f"**Historical Turns Folded**: {len(history_to_fold)} messages.",
            f"**Key Files Identified**: {', '.join(sorted(files_mentioned)[:12]) if files_mentioned else 'None'}",
            f"**Session Objectives**: {'; '.join(user_objectives[:4]) if user_objectives else 'Developer tasks'}"
        ]
        if tool_results_summaries:
            summary_blocks.append(f"**Completed Tool Actions**: {len(tool_results_summaries)} actions recorded.")

        compaction_anchor = {
            "role": "user",
            "content": "\n".join(summary_blocks)
        }
        ack_anchor = {
            "role": "model",
            "content": "Contextual history successfully compacted. Retaining operational focus and active files."
        }

        compacted = []
        if system_msg:
            compacted.append(system_msg)
        compacted.extend([compaction_anchor, ack_anchor])
        compacted.extend(recent_to_keep)

        new_tokens = self.total_estimated_tokens(compacted)
        reduction = round(max(0.0, (1.0 - (new_tokens / max(1, orig_tokens))) * 100.0), 1)

        return CompactionResult(
            compacted_messages=compacted,
            original_estimated_tokens=orig_tokens,
            compacted_estimated_tokens=new_tokens,
            reduction_percentage=reduction,
            files_preserved=sorted(files_mentioned)
        )
