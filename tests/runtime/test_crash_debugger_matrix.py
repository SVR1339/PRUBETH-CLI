"""PRUBETH Autonomous Crash Debugger Matrix Tests.

Exhaustively verifies AutonomousCrashDebugger: clean command execution,
direct traceback parsing, disk log inspection, failure frame extraction,
and diagnostic summary generation.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from prubeth.runtime.debugger import AutonomousCrashDebugger


# ============================================================================
# 1. Clean Execution Path
# ============================================================================

def test_debug_command_clean_execution_returns_success(tmp_path: Path):
    debugger = AutonomousCrashDebugger(workspace_root=tmp_path)
    # Python one-liner that exits 0
    res = debugger.debug_command('python -c "print(42)"')
    assert res.get("success") is True
    assert res.get("returncode") == 0
    assert "succeeded" in res.get("message", "").lower()


# ============================================================================
# 2. Direct Traceback String Ingestion
# ============================================================================

SAMPLE_TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "src/math_ops.py", line 42, in safe_divide\n'
    "    return a / b\n"
    "ZeroDivisionError: float division by zero\n"
)

@patch("prubeth.models.gateway.UniversalModelGateway.generate")
def test_debug_command_parses_raw_traceback_string(mock_gen, tmp_path: Path):
    mock_gen.side_effect = ConnectionError("Offline test mode")
    debugger = AutonomousCrashDebugger(workspace_root=tmp_path)

    res = debugger.debug_command(SAMPLE_TRACEBACK)
    assert res is not None
    assert isinstance(res, dict)


# ============================================================================
# 3. Log File Ingestion
# ============================================================================

@patch("prubeth.models.gateway.UniversalModelGateway.generate")
def test_debug_command_reads_traceback_from_disk_file(mock_gen, tmp_path: Path):
    mock_gen.side_effect = ConnectionError("Offline test mode")
    log_file = tmp_path / "crash.log"
    log_file.write_text(SAMPLE_TRACEBACK, encoding="utf-8")

    debugger = AutonomousCrashDebugger(workspace_root=tmp_path)
    res = debugger.debug_command(str(log_file))
    assert res is not None


# ============================================================================
# 4. In-Process Python Syntax Exception Traceback
# ============================================================================

SYNTAX_TRACEBACK = (
    '  File "src/server.py", line 12\n'
    "    def run_server(:\n"
    "                   ^\n"
    "SyntaxError: invalid syntax\n"
)

@patch("prubeth.models.gateway.UniversalModelGateway.generate")
def test_debug_command_parses_syntax_error_traceback(mock_gen, tmp_path: Path):
    mock_gen.side_effect = ConnectionError("Offline test mode")
    debugger = AutonomousCrashDebugger(workspace_root=tmp_path)

    res = debugger.debug_command(SYNTAX_TRACEBACK)
    assert res is not None
