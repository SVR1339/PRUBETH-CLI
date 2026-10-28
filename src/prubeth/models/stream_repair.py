"""PRUBETH Precision Stream & JSON Repair Micro-Algorithms.

Handles multi-byte UTF-8 packet boundary stitching and streaming JSON repair
for malformed or truncated LLM tool invocation arguments.
"""

from __future__ import annotations

import json
import re
from typing import Tuple, Any, Dict, List


class UTF8StreamAccumulator:
    """Reconstructs clean UTF-8 text from fragmented byte streams.
    
    Prevents UnicodeDecodeError and character corruption when TCP/SSE chunks
    split multi-byte UTF-8 sequences (e.g. emojis, box-drawing characters, CJK).
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> str:
        """Appends raw bytes and returns all complete UTF-8 characters."""
        self._buffer.extend(chunk)
        if not self._buffer:
            return ""

        # Determine how many trailing bytes might be part of an incomplete UTF-8 sequence
        valid_length = len(self._buffer)
        for i in range(1, min(5, len(self._buffer) + 1)):
            lead_byte = self._buffer[-i]
            # ASCII byte (0xxxxxxx) -> sequence complete
            if lead_byte & 0x80 == 0:
                break
            # Continuation byte (10xxxxxx) -> keep looking backwards for lead byte
            if (lead_byte & 0xC0) == 0x80:
                continue
            # 2-byte lead (110xxxxx)
            if (lead_byte & 0xE0) == 0xC0:
                if i < 2:
                    valid_length = len(self._buffer) - i
                break
            # 3-byte lead (1110xxxx)
            if (lead_byte & 0xF0) == 0xE0:
                if i < 3:
                    valid_length = len(self._buffer) - i
                break
            # 4-byte lead (11110xxx)
            if (lead_byte & 0xF8) == 0xF0:
                if i < 4:
                    valid_length = len(self._buffer) - i
                break

        if valid_length == 0:
            return ""

        to_decode = self._buffer[:valid_length]
        self._buffer = self._buffer[valid_length:]
        return to_decode.decode("utf-8", errors="replace")

    def flush(self) -> str:
        """Decodes any remaining bytes at stream termination."""
        if not self._buffer:
            return ""
        res = self._buffer.decode("utf-8", errors="replace")
        self._buffer.clear()
        return res


class JSONRepairEngine:
    """Repairs truncated, partial, or malformed JSON payloads from LLM tool arguments."""

    @staticmethod
    def repair_json_string(raw: str) -> str:
        """Surgically balances quotes, brackets, and braces in incomplete JSON."""
        s = raw.strip()
        if not s:
            return "{}"

        # If it already parses cleanly, return as-is
        try:
            json.loads(s)
            return s
        except Exception:
            pass

        # Strip markdown code block wrappers if present
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s)
            s = re.sub(r"\s*```$", "", s)

        # 1. Strip trailing commas before closing braces/brackets
        s = re.sub(r",\s*([\}\]])", r"\1", s)

        # 2. Check if string ends mid-literal or mid-quote
        in_string = False
        escape = False
        delimiter_stack: List[str] = []

        for char in s:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char in ("{", "["):
                    delimiter_stack.append(char)
                elif char == "}" and delimiter_stack and delimiter_stack[-1] == "{":
                    delimiter_stack.pop()
                elif char == "]" and delimiter_stack and delimiter_stack[-1] == "[":
                    delimiter_stack.pop()

        # If ended while inside a string literal, close the quote
        if in_string:
            s += '"'

        # Auto-close remaining open delimiters in reverse order
        while delimiter_stack:
            opener = delimiter_stack.pop()
            if opener == "{":
                # Check if last item has an open key with colon
                trimmed = s.rstrip()
                if trimmed.endswith(":"):
                    s += ' null}'
                elif trimmed.endswith(","):
                    s = trimmed[:-1] + "}"
                else:
                    s += "}"
            elif opener == "[":
                trimmed = s.rstrip()
                if trimmed.endswith(","):
                    s = trimmed[:-1] + "]"
                else:
                    s += "]"

        # Strip any trailing commas once more
        s = re.sub(r",\s*([\}\]])", r"\1", s)
        return s

    @classmethod
    def parse_safely(cls, raw: str, default: Any = None) -> Any:
        """Attempts standard parse, falls back to surgical repair, or returns default."""
        if not raw or not raw.strip():
            return default if default is not None else {}
        try:
            return json.loads(raw)
        except Exception:
            pass

        try:
            repaired = cls.repair_json_string(raw)
            return json.loads(repaired)
        except Exception:
            pass

        # Conversational / embedded JSON extraction
        s = raw.strip()
        first_brace = s.find("{")
        last_brace = s.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = s[first_brace:last_brace+1]
            try:
                return json.loads(candidate)
            except Exception:
                try:
                    repaired = cls.repair_json_string(candidate)
                    return json.loads(repaired)
                except Exception:
                    pass

        first_bracket = s.find("[")
        last_bracket = s.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            candidate = s[first_bracket:last_bracket+1]
            try:
                return json.loads(candidate)
            except Exception:
                try:
                    repaired = cls.repair_json_string(candidate)
                    return json.loads(repaired)
                except Exception:
                    pass

        return default if default is not None else {}
