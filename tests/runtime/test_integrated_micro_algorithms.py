"""Tests verifying end-to-end integration of Phase 1 micro-algorithms into runtime systems."""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from prubeth.runtime.stagnation import StagnationDetector, StagnationReport
from prubeth.models.circuit_breaker import GlobalCircuitRegistry, CircuitState, CircuitBreakerOpenError
from prubeth.models.stream_repair import UTF8StreamAccumulator, JSONRepairEngine
from prubeth.tools.file_ops import atomic_write_file, fuzzy_replace_text
from prubeth.memory.compactor import ContextCompactor
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase
from prubeth.models.gateway import UniversalModelGateway, GenerationResponse
from prubeth.runtime.controller import RuntimeController, RuntimeConfig


@pytest.fixture
def test_env(tmp_path: Path):
    db_path = tmp_path / "prubeth.db"
    db = TaskDatabase(str(db_path))
    sec = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=True)
    engine = ToolExecutionEngine(security=sec, db=db, current_task_id="test_task_1")
    return {"workspace": tmp_path, "db": db, "security": sec, "engine": engine}


# =========================================================================
# JSONRepairEngine & Atomic Write Integration in ToolExecutionEngine
# =========================================================================

def test_tool_execution_engine_accepts_and_repairs_json_string_args(test_env):
    engine = test_env["engine"]
    ws = test_env["workspace"]
    target = ws / "repaired.txt"

    # Pass args as raw JSON string with trailing comma / unquoted keys that JSONRepairEngine fixes
    raw_json_args = '{"path": "' + str(target).replace("\\", "\\\\") + '", "content": "hello world",}'
    success, output = engine.execute_tool("write_file", raw_json_args)
    assert success is True
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "hello world"


def test_tool_execution_engine_uses_atomic_write_file(test_env):
    engine = test_env["engine"]
    ws = test_env["workspace"]
    target = ws / "atomic.txt"

    success, output = engine.execute_tool("write_file", {"path": str(target), "content": "atomic test content"})
    assert success is True
    assert target.read_text(encoding="utf-8") == "atomic test content"


def test_tool_execution_engine_fuzzy_edit(test_env):
    engine = test_env["engine"]
    ws = test_env["workspace"]
    target = ws / "fuzzy.py"
    target.write_text("def run():\n    x = 10\n    return x\n", encoding="utf-8")

    # Shift indentation in target
    success, output = engine.execute_tool("edit_file", {
        "path": str(target),
        "target": "x = 10\nreturn x",
        "replacement": "x = 20\nreturn x * 2"
    })
    assert success is True
    content = target.read_text(encoding="utf-8")
    assert "x = 20" in content


def test_tool_execution_engine_dispatches_new_core_tools(test_env):
    engine = test_env["engine"]
    ws = test_env["workspace"]
    (ws / "file1.txt").write_text("one", encoding="utf-8")

    # Call list_dir via ToolExecutionEngine
    success, output = engine.execute_tool("list_dir", {"path": str(ws)})
    assert success is True
    assert "file1.txt" in output


# =========================================================================
# StagnationDetector in Autonomous ReAct Controller
# =========================================================================

def test_stagnation_detector_halts_repetitive_tool_calls(tmp_path: Path):
    ctrl = RuntimeController(
        workspace_root=str(tmp_path),
        config=RuntimeConfig(auto_approve_actions=True, max_execution_turns=10)
    )

    # Mock gateway returning the EXACT same tool call 4 times consecutively
    mock_tc = [{"name": "read_file", "args": {"path": "dummy.txt"}}]
    mock_resp = GenerationResponse(
        text="I am reading the file.",
        tool_calls=mock_tc,
        model="gemini-3.5-flash",
        provider="google"
    )

    with patch.object(ctrl.gateway, "generate", return_value=mock_resp):
        turn_res = ctrl.run_fluid_turn("Inspect the dummy file", max_tool_turns=5)
        # Should stop after hitting stagnation limit (3 repeats) instead of going all 5 turns
        executed_tools = turn_res["tools_executed"]
        # The 3rd repetitive call triggers stagnation interruption
        assert len(executed_tools) <= 3
        # Check that last result contains stagnation notice
        assert any("Stagnation detected" in t["output"] for t in executed_tools)


# =========================================================================
# GlobalCircuitRegistry in UniversalModelGateway
# =========================================================================

def test_gateway_circuit_breaker_trips_and_fails_fast():
    gateway = UniversalModelGateway()
    GlobalCircuitRegistry.reset_all()
    breaker = GlobalCircuitRegistry.get_breaker("google")
    assert breaker.state == CircuitState.CLOSED

    # Simulate 4 consecutive failures to trip circuit
    for _ in range(4):
        breaker.record_failure("HTTP Error 503: Service Unavailable")

    assert breaker.state == CircuitState.OPEN
    assert not breaker.can_execute()

    # When generate_chat is called with google provider while tripped open,
    # it must trigger CircuitBreakerOpenError, skip google, and pivot away from google
    with patch.object(gateway, "_generate_openai_compatible", side_effect=RuntimeError("All fallbacks down")):
        with pytest.raises(RuntimeError) as exc_info:
            gateway.generate_chat("test", model_name="gemini-3.5-flash")
        assert "Circuit breaker OPEN" in str(exc_info.value) or "exhausted" in str(exc_info.value)

    # Clean up breaker state
    GlobalCircuitRegistry.reset_all()


# =========================================================================
# UTF8StreamAccumulator Integration
# =========================================================================

def test_utf8_stream_accumulator_multi_byte_reassembly():
    acc = UTF8StreamAccumulator()
    # "£" is 0xC2 0xA3 in UTF-8
    pound_bytes = "£".encode("utf-8")
    assert len(pound_bytes) == 2

    chunk1 = acc.feed(pound_bytes[:1])
    assert chunk1 == ""  # Incomplete byte buffered

    chunk2 = acc.feed(pound_bytes[1:])
    assert chunk2 == "£"  # Complete character reassembled


# =========================================================================
# ContextCompactor in Controller History Compaction
# =========================================================================

def test_controller_compact_history_with_token_folding(tmp_path: Path):
    ctrl = RuntimeController(
        workspace_root=str(tmp_path),
        config=RuntimeConfig(auto_approve_actions=True)
    )

    # Seed fluid history with multiple turns
    for i in range(1, 6):
        ctrl.fluid_history.append({"role": "user", "content": f"Task step {i}: configure parameter {i}"})
        ctrl.fluid_history.append({"role": "assistant", "content": f"Configured parameter {i} successfully in config.py"})

    assert len(ctrl.fluid_history) == 10
    comp_res = ctrl.compact_history()
    assert comp_res["compacted_turns"] == 2
    assert comp_res["tokens_saved_approx"] >= 0
    assert "PRUBETH Compacted" in comp_res["summary"]
