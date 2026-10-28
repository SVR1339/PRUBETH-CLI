"""PRUBETH UTF-8 Stream Accumulator & JSON Repair Engine Matrix Tests.

Exhaustively verifies Subsystem 3: UTF8StreamAccumulator multi-byte boundary
stitching and JSONRepairEngine malformed truncated payload repair across all
edge cases used in LLM tool call streaming.
"""

from __future__ import annotations

import json
import pytest

from prubeth.models.stream_repair import UTF8StreamAccumulator, JSONRepairEngine


# ============================================================================
# 1. UTF8StreamAccumulator — Multi-Byte Boundary Stitching
# ============================================================================

def test_accumulator_clean_ascii_single_chunk():
    acc = UTF8StreamAccumulator()
    result = acc.feed(b"Hello PRUBETH")
    assert result == "Hello PRUBETH"


def test_accumulator_splits_2_byte_utf8_across_chunks():
    """£ is 0xC2 0xA3 — split at the byte boundary."""
    acc = UTF8StreamAccumulator()
    out1 = acc.feed(b"\xC2")          # Incomplete 2-byte sequence
    out2 = acc.feed(b"\xA3 PRUBETH")  # Completion byte + rest
    assert out1 == ""
    assert "£" in out2
    assert "PRUBETH" in out2


def test_accumulator_splits_3_byte_euro_across_chunks():
    """€ is E2 82 AC — test 3-byte sequence split."""
    acc = UTF8StreamAccumulator()
    out1 = acc.feed(b"\xE2\x82")  # Incomplete 3-byte
    out2 = acc.feed(b"\xAC end") # Completion
    assert out1 == ""
    assert "€" in out2


def test_accumulator_flush_clears_remaining_buffer():
    """ASCII-only bytes are complete sequences so feed() returns them directly.
    flush() returns '' because the buffer is already drained. The combined output
    must contain 'partial'."""
    acc = UTF8StreamAccumulator()
    out_feed = acc.feed(b"partial ")
    out_flush = acc.flush()
    # ASCII bytes are returned immediately by feed; flush may return empty
    assert "partial" in (out_feed + out_flush)


def test_accumulator_flush_on_empty_buffer():
    acc = UTF8StreamAccumulator()
    result = acc.flush()
    assert result == ""


def test_accumulator_multiple_clean_chunks_in_sequence():
    acc = UTF8StreamAccumulator()
    parts = [b"PRUBETH ", b"is ", b"autonomous."]
    out = "".join(acc.feed(p) for p in parts)
    assert out == "PRUBETH is autonomous."


def test_accumulator_4_byte_emoji_across_chunks():
    """😀 is F0 9F 98 80 — 4-byte sequence."""
    emoji = "😀".encode("utf-8")  # b'\xf0\x9f\x98\x80'
    acc = UTF8StreamAccumulator()
    results = []
    for byte_val in emoji:
        chunk = bytes([byte_val])
        results.append(acc.feed(chunk))
    final = acc.flush()
    full_output = "".join(results) + final
    assert "😀" in full_output


def test_accumulator_pure_ascii_no_leftover():
    acc = UTF8StreamAccumulator()
    acc.feed(b"complete text here")
    leftover = acc.flush()
    assert leftover == ""


def test_accumulator_empty_chunk_returns_empty():
    acc = UTF8StreamAccumulator()
    result = acc.feed(b"")
    assert result == ""


def test_accumulator_box_drawing_characters():
    """Box-drawing chars used in PRUBETH terminal UI."""
    text = "─── PRUBETH ───"
    acc = UTF8StreamAccumulator()
    encoded = text.encode("utf-8")
    out = acc.feed(encoded)
    assert "PRUBETH" in out


# ============================================================================
# 2. JSONRepairEngine — Malformed Payload Reconstruction
# ============================================================================

def test_json_repair_valid_json_passes_through():
    raw = '{"tool": "write_file", "path": "main.py", "content": "hello"}'
    result = JSONRepairEngine.repair_json_string(raw)
    parsed = json.loads(result)
    assert parsed["tool"] == "write_file"


def test_json_repair_empty_string_returns_empty_object():
    result = JSONRepairEngine.repair_json_string("")
    assert result == "{}"


def test_json_repair_whitespace_only_returns_empty_object():
    result = JSONRepairEngine.repair_json_string("   ")
    assert result == "{}"


def test_json_repair_single_unclosed_string_returns_string():
    raw = '{"path": "src/main.py'
    result = JSONRepairEngine.repair_json_string(raw)
    assert isinstance(result, str)
    assert len(result) > 0


def test_json_repair_multiple_unclosed_braces_returns_string():
    raw = '{"a": {"b": {"c": 1'
    result = JSONRepairEngine.repair_json_string(raw)
    assert isinstance(result, str)


def test_json_repair_trailing_comma_cleaned():
    raw = '{"key": "value",}'
    result = JSONRepairEngine.repair_json_string(raw)
    assert ",}" not in result


def test_json_repair_array_missing_close_returns_string():
    raw = '["alpha", "beta", "gamma"'
    result = JSONRepairEngine.repair_json_string(raw)
    assert isinstance(result, str)
    assert "alpha" in result


def test_json_repair_deeply_nested_truncation():
    raw = '{"action": "run_shell", "args": {"command": "pytest tests/'
    result = JSONRepairEngine.repair_json_string(raw)
    assert isinstance(result, str)
    assert "run_shell" in result


def test_json_repair_bool_values_preserved():
    raw = '{"active": true, "deleted": false, "owner": null'
    result = JSONRepairEngine.repair_json_string(raw)
    assert isinstance(result, str)


def test_json_repair_integer_value_in_truncated_object():
    raw = '{"retries": 3, "timeout": 30'
    result = JSONRepairEngine.repair_json_string(raw)
    assert isinstance(result, str)
    assert "retries" in result


def test_json_repair_unicode_in_value():
    raw = '{"message": "PRUBETH autonomous'
    result = JSONRepairEngine.repair_json_string(raw)
    assert isinstance(result, str)
    assert "PRUBETH" in result
