"""Tests for PRUBETH Precision Micro-Algorithms:
1. UTF-8 Multi-byte Stream Reconstructor (UTF8StreamAccumulator)
2. Streaming JSON Repair State Machine (JSONRepairEngine)
3. Crash-Safe Atomic File Replacement (atomic_write_file)
4. Fuzzy Indentation-Tolerant Patch Replacer (fuzzy_replace_text)
5. Agent Stagnation & Infinite Loop Detector (StagnationDetector)
6. Multiline Delimiter Balance Tracker (MultilineInputParser)
7. Endpoint Health Circuit Breaker (ProviderCircuitBreaker)
8. In-Memory Context Compactor (ContextCompactor)
"""

import sys
import json
import time
from pathlib import Path
import tempfile
import shutil

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prubeth.models.stream_repair import UTF8StreamAccumulator, JSONRepairEngine
from prubeth.tools.file_ops import atomic_write_file, fuzzy_replace_text, detect_line_ending
from prubeth.runtime.stagnation import StagnationDetector
from prubeth.cli.multiline import MultilineInputParser
from prubeth.models.circuit_breaker import ProviderCircuitBreaker, CircuitState
from prubeth.memory.compactor import ContextCompactor


class TestUTF8StreamAccumulator:
    def test_ascii_passthrough(self):
        acc = UTF8StreamAccumulator()
        assert acc.feed(b"Hello PRUBETH") == "Hello PRUBETH"
        assert acc.flush() == ""

    def test_split_multibyte_emoji(self):
        # 4-byte rocket emoji 🚀 is bytes: b'\xf0\x9f\x9a\x80'
        acc = UTF8StreamAccumulator()
        part1 = b"Launching \xf0\x9f"  # cut mid-emoji
        part2 = b"\x9a\x80 into space"

        out1 = acc.feed(part1)
        assert out1 == "Launching "  # held the incomplete byte sequence

        out2 = acc.feed(part2)
        assert out2 == "🚀 into space"


class TestJSONRepairEngine:
    def test_valid_json_untouched(self):
        raw = '{"path": "src/main.py", "lines": 42}'
        assert json.loads(JSONRepairEngine.repair_json_string(raw)) == json.loads(raw)

    def test_unclosed_string_and_array(self):
        truncated = '{"action": "edit", "files": ["app.py", "test.py'
        repaired = JSONRepairEngine.repair_json_string(truncated)
        parsed = json.loads(repaired)
        assert parsed["action"] == "edit"
        assert "app.py" in parsed["files"]

    def test_trailing_comma_repair(self):
        bad_json = '{"key1": "val1", "key2": [1, 2, 3,],}'
        repaired = JSONRepairEngine.repair_json_string(bad_json)
        parsed = json.loads(repaired)
        assert parsed["key2"] == [1, 2, 3]

    def test_parse_safely_fallback(self):
        assert JSONRepairEngine.parse_safely("", default={"empty": True}) == {"empty": True}
        assert JSONRepairEngine.parse_safely('{"valid": 1}') == {"valid": 1}


class TestAtomicFileOps:
    def test_atomic_write_creates_file(self, tmp_path):
        target = tmp_path / "subdir" / "test.txt"
        atomic_write_file(target, "Hello Atomic World\n")
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "Hello Atomic World\n"

    def test_detect_line_ending(self):
        assert detect_line_ending("line1\r\nline2\r\n") == "\r\n"
        assert detect_line_ending("line1\nline2\n") == "\n"

    def test_fuzzy_replace_text_exact(self):
        source = "def run():\n    print('old')\n"
        ok, res, _ = fuzzy_replace_text(source, "print('old')", "print('new')")
        assert ok
        assert "print('new')" in res

    def test_fuzzy_replace_text_indentation_tolerant(self):
        source = "    class Runner:\n        def execute(self):\n            return 1\n"
        target = "def execute(self):\n    return 1\n"
        replacement = "def execute(self):\n    return 2\n"

        ok, res, _ = fuzzy_replace_text(source, target, replacement)
        assert ok
        assert "return 2" in res
        # Preserved surrounding 8-space indentation
        assert "        def execute(self):" in res


class TestStagnationDetector:
    def test_consecutive_same_tool_calls(self):
        det = StagnationDetector(max_consecutive_same=3)
        assert not det.record_tool_call("read_file", {"path": "a.py"}).is_stalled
        assert not det.record_tool_call("read_file", {"path": "a.py"}).is_stalled
        rep = det.record_tool_call("read_file", {"path": "a.py"})
        assert rep.is_stalled
        assert rep.suggested_action == "inject_feedback"

    def test_cyclic_tool_calls(self):
        det = StagnationDetector()
        # Pattern: read -> edit -> read -> edit
        det.record_tool_call("read", {"p": 1})
        det.record_tool_call("edit", {"p": 1})
        det.record_tool_call("read", {"p": 1})
        rep = det.record_tool_call("edit", {"p": 1})
        assert rep.is_stalled
        assert rep.cycle_length == 2


class TestMultilineInputParser:
    def test_single_complete_line(self):
        ok, _ = MultilineInputParser.is_input_complete("print('hello')")
        assert ok

    def test_trailing_backslash_incomplete(self):
        ok, prompt = MultilineInputParser.is_input_complete("SELECT * FROM users \\")
        assert not ok
        assert prompt == "... "

    def test_unclosed_bracket(self):
        ok, _ = MultilineInputParser.is_input_complete("data = [1, 2, 3,")
        assert not ok

    def test_unclosed_triple_quote(self):
        ok, prompt = MultilineInputParser.is_input_complete('"""This is a docstring')
        assert not ok
        assert '"""' in prompt


class TestProviderCircuitBreaker:
    def test_initial_state_closed(self):
        cb = ProviderCircuitBreaker(failure_threshold=3)
        assert cb.can_execute()
        assert cb.state == CircuitState.CLOSED

    def test_trips_to_open_after_threshold(self):
        cb = ProviderCircuitBreaker(failure_threshold=3, cooldown_s=0.2)
        cb.record_failure("503 Overloaded")
        cb.record_failure("503 Overloaded")
        assert cb.can_execute()
        cb.record_failure("503 Overloaded")
        assert not cb.can_execute()
        assert cb.state == CircuitState.OPEN

    def test_recovers_to_half_open_after_cooldown(self):
        cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=0.05, recovery_successes=1)
        cb.record_failure("err")
        cb.record_failure("err")
        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestContextCompactor:
    def test_token_estimation(self):
        assert ContextCompactor.estimate_tokens("word " * 10) >= 10

    def test_compaction_folds_old_turns(self):
        compactor = ContextCompactor(target_window_tokens=500, keep_recent_turns=2)
        messages = [
            {"role": "system", "content": "You are PRUBETH."},
            {"role": "user", "content": "Inspect file src/main.py and fix database.py."},
            {"role": "model", "content": "I am looking at src/main.py."},
            {"role": "tool", "content": "File content of src/main.py...", "name": "read_file"},
            {"role": "model", "content": "Now editing src/main.py."},
            {"role": "user", "content": "Please verify tests."},
            {"role": "model", "content": "Running pytest now."},
            {"role": "user", "content": "What is next?"},
            {"role": "model", "content": "Ready to commit."}
        ]
        res = compactor.compact(messages)
        assert len(res.compacted_messages) < len(messages)
        assert "src/main.py" in res.files_preserved or "database.py" in res.files_preserved
        assert res.compacted_messages[0]["role"] == "system"
        # Last turn preserved
        assert res.compacted_messages[-1]["content"] == "Ready to commit."
