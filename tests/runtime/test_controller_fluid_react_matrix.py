"""PRUBETH Controller Fluid ReAct & Stagnation Steering Matrix.

Validates multi-turn fluid agent cycles, stagnation interception,
steering prompt injection, and seamless tool execution loops.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prubeth.runtime.controller import AutonomousRuntimeController, RuntimeConfig
from prubeth.models.gateway import GenerationResponse


@pytest.fixture
def controller_fixture():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / ".prubeth" / "memory").mkdir(parents=True, exist_ok=True)
        (ws / "src").mkdir(parents=True, exist_ok=True)
        ctrl = AutonomousRuntimeController(
            workspace_root=str(ws),
            config=RuntimeConfig(auto_approve_actions=True, max_execution_turns=5)
        )
        yield ctrl
        ctrl.close()


def test_controller_fluid_turn_direct_text_response(controller_fixture):
    mock_resp = GenerationResponse(
        text="The requested function can be implemented using modular arithmetic."
    )
    with patch.object(controller_fixture.gateway, "generate", return_value=mock_resp):
        res = controller_fixture.run_fluid_turn("Explain modular arithmetic in cryptography.")
        assert res["success"] is True
        assert "modular arithmetic" in res["text"]
        assert len(res["tools_executed"]) == 0
        assert len(controller_fixture.fluid_history) == 2


def test_controller_fluid_turn_single_tool_execution(controller_fixture):
    ws = controller_fixture.workspace_root
    (ws / "src" / "version.py").write_text("__version__ = '2.0.0'\n")

    # Step 1: Model requests read_file
    mock_step_1 = GenerationResponse(
        text="I will read the version file.\n```tool\n{\"tool\": \"read_file\", \"args\": {\"path\": \"src/version.py\"}}\n```"
    )
    # Step 2: Model outputs final answer
    mock_step_2 = GenerationResponse(
        text="The current version is 2.0.0."
    )

    with patch.object(controller_fixture.gateway, "generate", side_effect=[mock_step_1, mock_step_2]):
        res = controller_fixture.run_fluid_turn("Check the current project version.")
        assert res["success"] is True
        assert len(res["tools_executed"]) == 1
        assert res["tools_executed"][0]["tool"] == "read_file"
        assert res["tools_executed"][0]["success"] is True
        assert "2.0.0" in res["text"]


def test_controller_fluid_turn_stagnation_interceptor_aborts_infinite_loop(controller_fixture):
    # Model endlessly attempts identical tool call
    infinite_tool = GenerationResponse(
        text="```tool\n{\"tool\": \"list_dir\", \"args\": {\"path\": \".\"}}\n```"
    )

    with patch.object(controller_fixture.gateway, "generate", return_value=infinite_tool):
        res = controller_fixture.run_fluid_turn("Loop test", max_tool_turns=6)
        # Should be stopped by stagnation detector before max_tool_turns
        assert 2 <= len(res["tools_executed"]) <= 3
        # The last execution reports stagnation
        assert res["tools_executed"][-1]["success"] is False
        assert "stagnation detected" in res["tools_executed"][-1]["output"].lower()


def test_controller_fluid_turn_repeated_tool_failure_steering(controller_fixture):
    # Model keeps trying to read a non-existent file
    failing_tool = GenerationResponse(
        text="```tool\n{\"tool\": \"read_file\", \"args\": {\"path\": \"nonexistent_xyz.txt\"}}\n```"
    )

    with patch.object(controller_fixture.gateway, "generate", return_value=failing_tool):
        res = controller_fixture.run_fluid_turn("Read missing file", max_tool_turns=5)
        assert len(res["tools_executed"]) <= 3
        # At least one failure recorded
        assert any(not t["success"] for t in res["tools_executed"])


def test_controller_fluid_history_retention_across_turns(controller_fixture):
    mock_1 = GenerationResponse(text="Greeting recorded.")
    mock_2 = GenerationResponse(text="Previous context understood.")

    with patch.object(controller_fixture.gateway, "generate", side_effect=[mock_1, mock_2]):
        controller_fixture.run_fluid_turn("Hello PRUBETH")
        assert len(controller_fixture.fluid_history) == 2
        controller_fixture.run_fluid_turn("How are you?")
        assert len(controller_fixture.fluid_history) == 4
        assert controller_fixture.fluid_history[0]["content"] == "Hello PRUBETH"
        assert controller_fixture.fluid_history[2]["content"] == "How are you?"
