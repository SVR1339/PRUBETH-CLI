"""PRUBETH Precision Multiline Terminal Input & Delimiter Parser.

Tracks unclosed brackets, braces, parentheses, and quotes to determine whether
an interactive terminal input line requires continuation or is ready for execution.
"""

from __future__ import annotations

from typing import Tuple, List


class MultilineInputParser:
    """Lexical balance tracker for interactive terminal input."""

    def __init__(self) -> None:
        self._lines: List[str] = []
        self._is_continuation = False

    @property
    def is_continuation(self) -> bool:
        return self._is_continuation

    def reset(self) -> None:
        self._lines.clear()
        self._is_continuation = False

    def get_buffer(self) -> str:
        return "\n".join(self._lines)

    def feed_line(self, line: str) -> Tuple[bool, str]:
        """Feeds a line into the accumulator.
        
        Returns:
            (is_continuation: bool, full_accumulated_text: str)
        """
        self._lines.append(line)
        full_text = "\n".join(self._lines)
        is_complete, _ = self.is_input_complete(full_text)
        self._is_continuation = not is_complete
        if is_complete:
            buffered = full_text
            self.reset()
            return False, buffered
        return True, full_text

    @staticmethod
    def is_input_complete(text: str) -> Tuple[bool, str]:
        """Evaluates whether the accumulated input text is lexically complete.
        
        Returns:
            (is_complete: bool, continuation_prompt: str)
            where continuation_prompt is "... " or "quote> "
        """
        trimmed = text.rstrip()
        if not trimmed:
            return True, ""

        # 1. Explicit line continuation with trailing backslash '\'
        # Count consecutive trailing backslashes: odd number means unescaped continuation
        trailing_slashes = len(trimmed) - len(trimmed.rstrip("\\"))
        if trailing_slashes % 2 != 0:
            return False, "... "

        # 2. Check triple quotes first
        # Count non-escaped triple quotes
        double_triple = text.count('"""')
        single_triple = text.count("'''")
        if (double_triple % 2) != 0:
            return False, '"""... '
        if (single_triple % 2) != 0:
            return False, "'''... "

        # 3. Stack-based delimiter tracking
        stack: List[str] = []
        in_single_quote = False
        in_double_quote = False
        in_triple_double = False
        in_triple_single = False
        escape = False

        i = 0
        while i < len(text):
            char = text[i]

            if escape:
                escape = False
                i += 1
                continue

            if char == "\\":
                escape = True
                i += 1
                continue

            # Handle triple quotes
            if char == '"' and not in_single_quote and not in_triple_single:
                if text[i:i+3] == '"""':
                    in_triple_double = not in_triple_double
                    i += 3
                    continue
                if not in_triple_double:
                    in_double_quote = not in_double_quote
                    i += 1
                    continue
                i += 1
                continue

            if char == "'" and not in_double_quote and not in_triple_double:
                if text[i:i+3] == "'''":
                    in_triple_single = not in_triple_single
                    i += 3
                    continue
                if not in_triple_single:
                    in_single_quote = not in_single_quote
                    i += 1
                    continue
                i += 1
                continue

            # If inside any quote, ignore brackets
            if in_single_quote or in_double_quote or in_triple_double or in_triple_single:
                i += 1
                continue

            # Delimiters
            if char in ("(", "[", "{"):
                stack.append(char)
            elif char == ")" and stack and stack[-1] == "(":
                stack.pop()
            elif char == "]" and stack and stack[-1] == "[":
                stack.pop()
            elif char == "}" and stack and stack[-1] == "{":
                stack.pop()

            i += 1

        if in_single_quote or in_double_quote:
            return False, "quote> "

        if stack:
            # Open brackets remain unclosed
            return False, "... "

        return True, ""
