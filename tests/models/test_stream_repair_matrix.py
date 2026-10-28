"""PRUBETH UTF-8 Stream Stitching & Streaming JSON Repair Permutation Matrix.

Exhaustively verifies multi-byte UTF-8 packet boundary reconstruction,
incomplete sequence buffering, and resilient JSON repair for truncated LLM tool calls.
"""

from __future__ import annotations

import json
import pytest

from prubeth.models.stream_repair import UTF8StreamAccumulator, JSONRepairEngine


# ============================================================================
# 1. UTF8StreamAccumulator — Single Byte & Multi-Byte Split Stitching
# ============================================================================

def test_utf8_accumulator_ascii_stream():
    acc = UTF8StreamAccumulator()
    chunk1 = acc.feed(b"Hello, ")
    chunk2 = acc.feed(b"world!")
    assert chunk1 == "Hello, "
    assert chunk2 == "world!"
    assert acc.flush() == ""


@pytest.mark.parametrize("char,byte_seq", [
    ("é", "é".encode("utf-8")),           # 2-byte: 0xC3, 0xA9
    ("ñ", "ñ".encode("utf-8")),           # 2-byte: 0xC3, 0xB1
    ("€", "€".encode("utf-8")),           # 3-byte: 0xE2, 0x82, 0xAC
    ("漢", "漢".encode("utf-8")),         # 3-byte: 0xE6, 0xBC, 0xA2
    ("🚀", "🚀".encode("utf-8")),         # 4-byte: 0xF0, 0x9F, 0x99, 0x80
    ("🐝", "🐝".encode("utf-8")),         # 4-byte: 0xF0, 0x9F, 0x90, 0x9D
    ("🎉", "🎉".encode("utf-8")),         # 4-byte: 0xF0, 0x9F, 0x8E, 0x89
])
def test_utf8_accumulator_splits_by_single_bytes(char: str, byte_seq: bytes):
    """Feeds multi-byte characters byte-by-byte and verifies accurate reconstruction."""
    acc = UTF8StreamAccumulator()
    accumulated = ""
    for b in byte_seq:
        accumulated += acc.feed(bytes([b]))
    accumulated += acc.flush()
    assert accumulated == char


def test_utf8_accumulator_boundary_split_across_text():
    """Text where a 4-byte emoji is split exactly in the middle between two network packets."""
    text_before = "Building PRUBETH AI "
    emoji = "🚀"
    text_after = " in British English."

    full_bytes = (text_before + emoji + text_after).encode("utf-8")
    split_index = len(text_before.encode("utf-8")) + 2  # Split 4-byte emoji right in half

    packet_1 = full_bytes[:split_index]
    packet_2 = full_bytes[split_index:]

    acc = UTF8StreamAccumulator()
    decoded_1 = acc.feed(packet_1)
    decoded_2 = acc.feed(packet_2)
    decoded_flush = acc.flush()

    assert decoded_1 == text_before
    assert (decoded_2 + decoded_flush) == (emoji + text_after)
    assert (decoded_1 + decoded_2 + decoded_flush) == (text_before + emoji + text_after)


def test_utf8_accumulator_empty_feed():
    acc = UTF8StreamAccumulator()
    assert acc.feed(b"") == ""
    assert acc.flush() == ""


def test_utf8_accumulator_flush_incomplete():
    """Residual invalid byte sequence flushed uses replacement character."""
    acc = UTF8StreamAccumulator()
    acc.feed(b"\xf0\x9f")  # Incomplete 4-byte lead
    flushed = acc.flush()
    assert len(flushed) > 0  # Replaced gracefully without raising exception


# ============================================================================
# 2. JSONRepairEngine — Surgical Incomplete JSON Repair
# ============================================================================

def test_json_repair_clean_passthrough():
    clean = '{"tool": "read_file", "args": {"path": "src/main.py"}}'
    assert JSONRepairEngine.repair_json_string(clean) == clean


def test_json_repair_empty_string():
    assert JSONRepairEngine.repair_json_string("") == "{}"
    assert JSONRepairEngine.repair_json_string("   ") == "{}"


def test_json_repair_strips_markdown_codeblocks():
    wrapped = "```json\n{\"key\": \"value\"}\n```"
    repaired = JSONRepairEngine.repair_json_string(wrapped)
    parsed = json.loads(repaired)
    assert parsed == {"key": "value"}


def test_json_repair_trailing_commas():
    malformed = '{"a": 1, "b": [2, 3, ], }'
    repaired = JSONRepairEngine.repair_json_string(malformed)
    parsed = json.loads(repaired)
    assert parsed == {"a": 1, "b": [2, 3]}


@pytest.mark.parametrize("truncated_json,expected_key,expected_val", [
    ('{"tool": "edit_file", "args": {"path": "src/app.py', "path", "src/app.py"),
    ('{"action": "test", "files": ["a.py", "b.py"', "files", ["a.py", "b.py"]),
    ('{"config": {"port": 8080, "host": "127.0.0.1"', "host", "127.0.0.1"),
])
def test_json_repair_unclosed_quotes_and_delimiters(truncated_json: str, expected_key: str, expected_val: any):
    """Truncated JSON with unclosed string literals and unclosed brackets is auto-balanced."""
    repaired = JSONRepairEngine.repair_json_string(truncated_json)
    parsed = json.loads(repaired)
    if expected_key == "path":
        assert parsed["args"][expected_key] == expected_val
    elif expected_key == "files":
        assert parsed[expected_key] == expected_val
    elif expected_key == "host":
        assert parsed["config"][expected_key] == expected_val


def test_json_repair_trailing_colon_with_null_fill():
    truncated = '{"tool": "read_file", "path":'
    repaired = JSONRepairEngine.repair_json_string(truncated)
    parsed = json.loads(repaired)
    assert parsed["tool"] == "read_file"
    assert parsed["path"] is None


def test_json_repair_deeply_nested_delimiters():
    truncated = '{"a": [{"b": {"c": [{"d": 42'
    repaired = JSONRepairEngine.repair_json_string(truncated)
    parsed = json.loads(repaired)
    assert parsed["a"][0]["b"]["c"][0]["d"] == 42


# ============================================================================
# 3. JSONRepairEngine.parse_safely()
# ============================================================================

def test_parse_safely_valid_json():
    data = JSONRepairEngine.parse_safely('{"status": "ok"}')
    assert data == {"status": "ok"}


def test_parse_safely_empty_falls_back_to_default():
    assert JSONRepairEngine.parse_safely("", default={"def": True}) == {"def": True}
    assert JSONRepairEngine.parse_safely(None, default=[]) == []


def test_parse_safely_conversational_wrapped_json():
    """Extracts JSON embedded inside natural language dialogue."""
    raw = (
        "Here is the tool invocation you requested:\n\n"
        "```json\n"
        '{"tool": "run_shell", "args": {"command": "pytest"}}\n'
        "```\n\n"
        "Let me know if you want me to execute this."
    )
    parsed = JSONRepairEngine.parse_safely(raw)
    assert parsed["tool"] == "run_shell"
    assert parsed["args"]["command"] == "pytest"


def test_parse_safely_embedded_list():
    raw = "The updated file list is: ['src/a.py', 'src/b.py'] as requested."
    # With valid quotes:
    raw_valid = 'The files are: ["src/a.py", "src/b.py"] in the repository.'
    parsed = JSONRepairEngine.parse_safely(raw_valid)
    assert parsed == ["src/a.py", "src/b.py"]


def test_parse_safely_unrecoverable_returns_default():
    raw = "There is no json whatsoever in this response string."
    assert JSONRepairEngine.parse_safely(raw, default={"fallback": 1}) == {"fallback": 1}
