"""Comprehensive Unit and Stress Tests for StagnationInterceptor and Loop Breakers."""

import pytest
from prubeth.runtime.stagnation import (
    StagnationDetector,
    StagnationInterceptor,
    StagnationReport,
    ToolExecutionRecord,
)


@pytest.fixture
def detector():
    return StagnationDetector(max_consecutive_same=3, max_cycle_window=8)


@pytest.fixture
def interceptor():
    return StagnationInterceptor(
        max_consecutive_same=3,
        max_cycle_window=10,
        max_repeated_failures=3,
        similarity_threshold=0.65
    )


# =========================================================================
# Base StagnationDetector Invariants
# =========================================================================

def test_identical_consecutive_tool_calls_trigger_stall(detector):
    # Call 1: ok
    r1 = detector.record_tool_call("read_file", {"path": "src/main.py"})
    assert r1.is_stalled is False

    # Call 2: ok
    r2 = detector.record_tool_call("read_file", {"path": "src/main.py"})
    assert r2.is_stalled is False

    # Call 3: Stalled!
    r3 = detector.record_tool_call("read_file", {"path": "src/main.py"})
    assert r3.is_stalled is True
    assert "3 times with identical arguments" in r3.reason
    assert r3.suggested_action == "inject_feedback"


def test_interleaved_benign_calls_do_not_stall(detector):
    detector.record_tool_call("read_file", {"path": "src/a.py"})
    detector.record_tool_call("read_file", {"path": "src/b.py"})
    detector.record_tool_call("read_file", {"path": "src/c.py"})
    r = detector.record_tool_call("read_file", {"path": "src/d.py"})
    assert r.is_stalled is False


def test_2_step_cyclic_loop_detection(detector):
    # Pattern: list_dir -> grep_search -> list_dir -> grep_search
    detector.record_tool_call("list_dir", {"path": "."})
    detector.record_tool_call("grep_search", {"query": "TODO"})
    detector.record_tool_call("list_dir", {"path": "."})
    r = detector.record_tool_call("grep_search", {"query": "TODO"})
    assert r.is_stalled is True
    assert r.cycle_length == 2
    assert "Cyclic repetition detected" in r.reason


def test_3_step_cyclic_loop_detection(detector):
    # Pattern: A -> B -> C -> A -> B -> C
    for _ in range(2):
        detector.record_tool_call("tool_a", {"x": 1})
        detector.record_tool_call("tool_b", {"y": 2})
        r = detector.record_tool_call("tool_c", {"z": 3})

    assert r.is_stalled is True
    assert r.cycle_length == 3


def test_text_output_identical_repetition(detector):
    r1 = detector.record_text_output("I will now read the file to proceed.")
    assert r1.is_stalled is False
    r2 = detector.record_text_output("I will now read the file to proceed.")
    assert r2.is_stalled is False
    r3 = detector.record_text_output("I will now read the file to proceed.")
    assert r3.is_stalled is True
    assert r3.suggested_action == "abort"


# =========================================================================
# Advanced StagnationInterceptor Invariants
# =========================================================================

def test_repeated_failure_streak_triggers_stagnation(interceptor):
    for i in range(2):
        r = interceptor.intercept_execution(
            tool_name="run_command",
            args={"command": "npm test"},
            success=False,
            exit_code=1,
            output_snippet="Cannot find module 'foo'"
        )
        assert r.is_stalled is False

    # 3rd failure
    r3 = interceptor.intercept_execution(
        tool_name="run_command",
        args={"command": "npm test"},
        success=False,
        exit_code=1,
        output_snippet="Cannot find module 'foo'"
    )
    assert r3.is_stalled is True
    assert "failed 3 consecutive times" in r3.reason
    assert r3.corrective_prompt is not None
    assert "PRUBETH STAGNATION INTERCEPTOR" in r3.corrective_prompt


def test_no_op_edit_detection(interceptor):
    r = interceptor.intercept_execution(
        tool_name="edit_file",
        args={"path": "src/main.py", "target": "val = 1", "replacement": "val = 1"},
        success=True
    )
    assert r.is_stalled is True
    assert "No-op edit detected" in r.reason
    assert "target and replacement are identical" in r.reason


def test_ping_pong_file_oscillation(interceptor):
    # Model edits file back and forth between two implementations
    v1 = "def calc(): return 1"
    v2 = "def calc(): return 2"

    interceptor.intercept_execution("write_file", {"path": "src/calc.py", "replacement": v1})
    interceptor.intercept_execution("write_file", {"path": "src/calc.py", "replacement": v2})
    interceptor.intercept_execution("write_file", {"path": "src/calc.py", "replacement": v1})
    r4 = interceptor.intercept_execution("write_file", {"path": "src/calc.py", "replacement": v2})

    assert r4.is_stalled is True
    assert "Ping-pong oscillation detected" in r4.reason
    assert r4.cycle_length == 2


def test_jaccard_argument_similarity_stagnation(interceptor):
    # Model repeatedly micro-tweaks near-identical search queries
    args1 = {"path": "src", "query": "calculate_tax_rate_2025"}
    args2 = {"path": "src", "query": "calculate_tax_rate_2026"}
    args3 = {"path": "src", "query": "calculate_tax_rate_2027"}

    interceptor.intercept_execution("grep_search", args1, success=True, output_snippet="no match")
    interceptor.intercept_execution("grep_search", args2, success=True, output_snippet="no match")
    r3 = interceptor.intercept_execution("grep_search", args3, success=True, output_snippet="no match")

    # Arguments are 50%+ similar but let's check with identical key structures and identical paths
    sim_args1 = {"path": "src", "k1": "v1", "k2": "v2", "k3": "v3", "pattern": "item_1"}
    sim_args2 = {"path": "src", "k1": "v1", "k2": "v2", "k3": "v3", "pattern": "item_2"}
    sim_args3 = {"path": "src", "k1": "v1", "k2": "v2", "k3": "v3", "pattern": "item_3"}

    interceptor.reset()
    interceptor.intercept_execution("find_files", sim_args1, success=True)
    interceptor.intercept_execution("find_files", sim_args2, success=True)
    res = interceptor.intercept_execution("find_files", sim_args3, success=True)

    assert res.is_stalled is True
    assert "near-identical arguments" in res.reason


def test_interceptor_reset_clears_all_buffers(interceptor):
    interceptor.intercept_execution("tool_a", {"x": 1})
    interceptor.intercept_execution("tool_a", {"x": 1})
    interceptor.reset()
    assert len(interceptor.records) == 0
    assert len(interceptor._call_history) == 0
    # Next call is counted as 1st call, not 3rd
    r = interceptor.intercept_execution("tool_a", {"x": 1})
    assert r.is_stalled is False
