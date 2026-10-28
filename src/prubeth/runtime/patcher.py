"""PRUBETH Fuzzy Whitespace-Insensitive Surgical Patch Engine.

Applies file modifications reliably even when indentation varies (2-space vs 4-space,
tabs vs spaces), line endings differ (CRLF vs LF), or minor whitespace fluctuations
occur between model generation and workspace file contents.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class PatchResult:
    success: bool
    patched_content: str
    match_kind: str  # "exact", "normalised_whitespace", "fuzzy_line_match", "failed"
    confidence: float
    error_message: str = ""
    matches_found: int = 0


class FuzzyPatcher:
    """Surgical code patcher with whitespace resilience and indentation transfer."""

    def __init__(self, fuzzy_threshold: float = 0.88):
        self.fuzzy_threshold = fuzzy_threshold

    def apply_patch(
        self,
        original_text: str,
        target: str,
        replacement: str
    ) -> PatchResult:
        """Applies replacement to original_text, resolving target with progressive resilience."""
        if not target:
            return PatchResult(
                success=False,
                patched_content=original_text,
                match_kind="failed",
                confidence=0.0,
                error_message="Target string cannot be empty."
            )

        # 1. Exact Match Fast-Path
        count = original_text.count(target)
        if count == 1:
            patched = original_text.replace(target, replacement, 1)
            return PatchResult(
                success=True,
                patched_content=patched,
                match_kind="exact",
                confidence=1.0,
                matches_found=1
            )
        elif count > 1:
            # Multiple exact occurrences; require more context to disambiguate
            return PatchResult(
                success=False,
                patched_content=original_text,
                match_kind="failed",
                confidence=1.0,
                error_message=f"Ambiguous target: found {count} exact occurrences. Provide more surrounding context lines.",
                matches_found=count
            )

        # 2. Line Ending Normalisation (\r\n vs \n)
        is_crlf = "\r\n" in original_text
        target_norm = target.replace("\r\n", "\n")
        orig_norm = original_text.replace("\r\n", "\n")
        repl_norm = replacement.replace("\r\n", "\n")

        norm_count = orig_norm.count(target_norm)
        if norm_count == 1:
            patched = orig_norm.replace(target_norm, repl_norm, 1)
            if is_crlf:
                patched = patched.replace("\n", "\r\n")
            return PatchResult(
                success=True,
                patched_content=patched,
                match_kind="normalised_whitespace",
                confidence=0.99,
                matches_found=1
            )
        elif norm_count > 1:
            return PatchResult(
                success=False,
                patched_content=original_text,
                match_kind="failed",
                confidence=0.99,
                error_message=f"Ambiguous target: found {norm_count} occurrences after newline normalisation.",
                matches_found=norm_count
            )

        # 3. Block-Level Trimmed Line Sequence Matching
        block_result = self._match_block_by_trimmed_lines(orig_norm, target_norm, repl_norm, is_crlf)
        if block_result.success:
            return block_result

        # 4. Fuzzy Similarity Sequence Match
        fuzzy_result = self._match_fuzzy_sliding_window(orig_norm, target_norm, repl_norm, is_crlf)
        if fuzzy_result.success:
            return fuzzy_result

        return PatchResult(
            success=False,
            patched_content=original_text,
            match_kind="failed",
            confidence=0.0,
            error_message="Target block could not be located in source file. Verify context lines."
        )

    def _match_block_by_trimmed_lines(
        self,
        orig: str,
        target: str,
        repl: str,
        is_crlf: bool
    ) -> PatchResult:
        orig_lines = orig.split("\n")
        target_lines = target.split("\n")

        # Strip trailing empty line from split if target ends in \n
        if target_lines and not target_lines[-1]:
            target_lines = target_lines[:-1]

        t_trimmed = [l.strip() for l in target_lines if l.strip()]
        if not t_trimmed:
            return PatchResult(success=False, patched_content=orig, match_kind="failed", confidence=0.0)

        matches: List[Tuple[int, int]] = []
        n_target = len(t_trimmed)

        for i in range(len(orig_lines) - n_target + 1):
            sub_trimmed = [orig_lines[i + k].strip() for k in range(n_target)]
            if sub_trimmed == t_trimmed:
                matches.append((i, i + n_target))

        if len(matches) == 1:
            start, end = matches[0]
            # Transfer existing indentation: detect indentation of first original line
            orig_first_line = orig_lines[start]
            match_indent = re.match(r"^(\s*)", orig_first_line)
            indent_prefix = match_indent.group(1) if match_indent else ""

            # Check if replacement needs indentation adjustment
            repl_lines = repl.split("\n")
            target_first_indent = re.match(r"^(\s*)", target_lines[0]).group(1) if target_lines else ""

            len_orig = len(indent_prefix)
            len_tgt = len(target_first_indent)
            scale = (len_orig / len_tgt) if len_tgt > 0 and len_orig >= len_tgt else 1.0

            adjusted_repl_lines = []
            for r_line in repl_lines:
                if not r_line.strip():
                    adjusted_repl_lines.append("")
                else:
                    r_indent = len(r_line) - len(r_line.lstrip())
                    rel_indent = max(0, r_indent - len_tgt)
                    scaled_indent = int(rel_indent * scale)
                    adjusted_repl_lines.append(" " * (len_orig + scaled_indent) + r_line.lstrip())

            new_lines = orig_lines[:start] + adjusted_repl_lines + orig_lines[end:]
            res = "\n".join(new_lines)
            if is_crlf:
                res = res.replace("\n", "\r\n")

            return PatchResult(
                success=True,
                patched_content=res,
                match_kind="normalised_whitespace",
                confidence=0.95,
                matches_found=1
            )
        elif len(matches) > 1:
            return PatchResult(
                success=False,
                patched_content=orig,
                match_kind="failed",
                confidence=0.95,
                error_message=f"Ambiguous target: found {len(matches)} whitespace-normalised matches.",
                matches_found=len(matches)
            )

        return PatchResult(success=False, patched_content=orig, match_kind="failed", confidence=0.0)

    def _match_fuzzy_sliding_window(
        self,
        orig: str,
        target: str,
        repl: str,
        is_crlf: bool
    ) -> PatchResult:
        orig_lines = orig.split("\n")
        target_lines = target.split("\n")
        k = len(target_lines)

        if k == 0 or len(orig_lines) < k:
            return PatchResult(success=False, patched_content=orig, match_kind="failed", confidence=0.0)

        best_ratio = 0.0
        best_window: Optional[Tuple[int, int]] = None
        target_str = "\n".join(target_lines)

        for i in range(len(orig_lines) - k + 1):
            window_str = "\n".join(orig_lines[i : i + k])
            ratio = difflib.SequenceMatcher(None, target_str, window_str).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_window = (i, i + k)

        if best_ratio >= self.fuzzy_threshold and best_window:
            start, end = best_window
            new_lines = orig_lines[:start] + repl.split("\n") + orig_lines[end:]
            res = "\n".join(new_lines)
            if is_crlf:
                res = res.replace("\n", "\r\n")
            return PatchResult(
                success=True,
                patched_content=res,
                match_kind="fuzzy_line_match",
                confidence=round(best_ratio, 3),
                matches_found=1
            )

        return PatchResult(
            success=False,
            patched_content=orig,
            match_kind="failed",
            confidence=round(best_ratio, 3),
            error_message=f"Best fuzzy match confidence {best_ratio:.2f} was below required threshold {self.fuzzy_threshold:.2f}."
        )
