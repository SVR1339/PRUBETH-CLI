"""Comprehensive unit tests for CircuitBreaker, UTF8StreamAccumulator, JSONRepairEngine, and MultilineInputParser."""

import time
import pytest
from prubeth.models.circuit_breaker import ProviderCircuitBreaker, CircuitState, GlobalCircuitRegistry
from prubeth.models.stream_repair import UTF8StreamAccumulator, JSONRepairEngine
from prubeth.cli.multiline import MultilineInputParser


# =========================================================================
# ProviderCircuitBreaker Detailed State Machine Tests
# =========================================================================

def test_circuit_breaker_initial_state():
    cb = ProviderCircuitBreaker(failure_threshold=3, cooldown_s=1.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_trips_to_open_after_threshold():
    cb = ProviderCircuitBreaker(failure_threshold=3, cooldown_s=1.0)
    cb.record_failure("err1")
    assert cb.state == CircuitState.CLOSED
    cb.record_failure("err2")
    assert cb.state == CircuitState.CLOSED
    cb.record_failure("err3")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_circuit_breaker_transitions_to_half_open_after_cooldown():
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=0.05)
    cb.record_failure("e1")
    cb.record_failure("e2")
    assert cb.state == CircuitState.OPEN

    time.sleep(0.08)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.can_execute() is True


def test_circuit_breaker_half_open_recovers_to_closed_on_successes():
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=0.05, recovery_successes=2)
    cb.record_failure("e1")
    cb.record_failure("e2")
    time.sleep(0.08)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN  # needs 2 successes
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_half_open_trips_back_to_open_on_canary_failure():
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=0.05)
    cb.record_failure("e1")
    cb.record_failure("e2")
    time.sleep(0.08)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure("canary failed")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_circuit_breaker_manual_reset():
    cb = ProviderCircuitBreaker(failure_threshold=2)
    cb.record_failure("e1")
    cb.record_failure("e2")
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_global_circuit_registry_isolation():
    GlobalCircuitRegistry.reset_all()
    b_google = GlobalCircuitRegistry.get_breaker("google")
    b_anthropic = GlobalCircuitRegistry.get_breaker("anthropic")

    for _ in range(4):
        b_google.record_failure("outage")

    assert b_google.state == CircuitState.OPEN
    # Anthropic breaker must remain independent and CLOSED
    assert b_anthropic.state == CircuitState.CLOSED
    assert b_anthropic.can_execute() is True

    GlobalCircuitRegistry.reset_all()
    assert b_google.state == CircuitState.CLOSED


# =========================================================================
# UTF8StreamAccumulator Tests
# =========================================================================

def test_utf8_accumulator_ascii():
    acc = UTF8StreamAccumulator()
    res = acc.feed(b"Hello world!")
    assert res == "Hello world!"


def test_utf8_accumulator_split_euro_symbol():
    acc = UTF8StreamAccumulator()
    # '€' is 3 bytes: 0xE2 0x82 0xAC
    euro = "€".encode("utf-8")
    assert len(euro) == 3

    assert acc.feed(euro[:1]) == ""
    assert acc.feed(euro[1:2]) == ""
    assert acc.feed(euro[2:]) == "€"


def test_utf8_accumulator_split_emoji():
    acc = UTF8StreamAccumulator()
    # '🚀' is 4 bytes: 0xF0 0x9F 0x99 0x80
    rocket = "🚀".encode("utf-8")
    assert len(rocket) == 4

    assert acc.feed(rocket[:2]) == ""
    assert acc.feed(rocket[2:]) == "🚀"


def test_utf8_accumulator_flush():
    acc = UTF8StreamAccumulator()
    acc.feed(b"\xc2")  # 1 byte of 2-byte char
    flushed = acc.flush()
    assert flushed != ""  # Replaced with replacement char on force flush


# =========================================================================
# JSONRepairEngine Tests
# =========================================================================

def test_json_repair_valid_json():
    data = JSONRepairEngine.parse_safely('{"key": "value", "num": 42}')
    assert data["key"] == "value"
    assert data["num"] == 42


def test_json_repair_unclosed_braces():
    data = JSONRepairEngine.parse_safely('{"path": "test.txt", "content": "hello"')
    assert data["path"] == "test.txt"
    assert data["content"] == "hello"


def test_json_repair_trailing_commas():
    data = JSONRepairEngine.parse_safely('{"items": [1, 2, 3,], "flag": true,}')
    assert data["items"] == [1, 2, 3]
    assert data["flag"] is True


def test_json_repair_markdown_codeblock():
    text = "```json\n{\n  \"command\": \"pytest\",\n  \"timeout\": 30\n}\n```"
    data = JSONRepairEngine.parse_safely(text)
    assert data["command"] == "pytest"
    assert data["timeout"] == 30


def test_json_repair_conversational_wrapping():
    text = "Here is the tool call you requested:\n{\"tool\": \"read_file\", \"args\": {\"path\": \"a.py\"}}\nHope this helps!"
    data = JSONRepairEngine.parse_safely(text)
    assert data["tool"] == "read_file"
    assert data["args"]["path"] == "a.py"


def test_json_repair_unrepairable_returns_empty_dict():
    data = JSONRepairEngine.parse_safely("Total gibberish that has zero JSON")
    assert data == {}


# =========================================================================
# MultilineInputParser Tests
# =========================================================================

def test_multiline_parser_single_complete_line():
    parser = MultilineInputParser()
    is_cont, text = parser.feed_line("print('hello')")
    assert is_cont is False
    assert text == "print('hello')"


def test_multiline_parser_trailing_backslash():
    parser = MultilineInputParser()
    is_cont1, _ = parser.feed_line("result = a + \\")
    assert is_cont1 is True
    is_cont2, text = parser.feed_line("    b")
    assert is_cont2 is False
    assert "result = a +" in text
    assert "b" in text


def test_multiline_parser_unclosed_parentheses():
    parser = MultilineInputParser()
    is_cont1, _ = parser.feed_line("def compute(x,")
    assert is_cont1 is True
    is_cont2, text = parser.feed_line("            y):")
    assert is_cont2 is False
    assert "def compute(x,\n            y):" == text


def test_multiline_parser_unclosed_triple_quotes():
    parser = MultilineInputParser()
    is_cont1, _ = parser.feed_line('docstring = """First line')
    assert is_cont1 is True
    is_cont2, _ = parser.feed_line('Second line')
    assert is_cont2 is True
    is_cont3, text = parser.feed_line('Third line"""')
    assert is_cont3 is False
    assert 'docstring = """First line\nSecond line\nThird line"""' == text


def test_multiline_parser_reset():
    parser = MultilineInputParser()
    parser.feed_line("open paren (")
    assert parser.is_continuation is True
    parser.reset()
    assert parser.is_continuation is False
    assert parser.get_buffer() == ""
