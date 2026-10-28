"""PRUBETH Auto-TDD Closed-Loop Self-Healing Execution Scenarios.

Verifies end-to-end autonomous healing: test failure detection, traceback parsing,
patch synthesis, verification passes, and snapshot auto-rollback on regression.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from prubeth.runtime.auto_heal import AutoHealer
from prubeth.models.gateway import GenerationResponse


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / ".prubeth" / "memory").mkdir(parents=True, exist_ok=True)
        (ws / "src").mkdir(parents=True, exist_ok=True)
        (ws / "tests").mkdir(parents=True, exist_ok=True)
        yield ws


def test_auto_healer_extract_failing_files_python(temp_workspace):
    console = Console(quiet=True)
    healer = AutoHealer(workspace_root=temp_workspace, console=console)

    # Create dummy source files
    (temp_workspace / "src" / "math_ops.py").write_text("def add(a, b): return a - b\n")
    (temp_workspace / "tests" / "test_math.py").write_text("def test_add(): assert add(1, 2) == 3\n")

    traceback_sample = """
Traceback (most recent call last):
  File "tests/test_math.py", line 1, in test_add
    assert add(1, 2) == 3
AssertionError: assert -1 == 3
  File "src/math_ops.py", line 1, in add
    return a - b
"""
    files = healer.extract_failing_files(traceback_sample)
    assert len(files) >= 1
    assert any("math_ops.py" in f or "test_math.py" in f for f in files)


def test_auto_healer_extract_failing_files_polyglot_line_patterns(temp_workspace):
    console = Console(quiet=True)
    healer = AutoHealer(workspace_root=temp_workspace, console=console)

    (temp_workspace / "src" / "service.ts").write_text("export function run() {}\n")
    (temp_workspace / "src" / "handler.go").write_text("package main\n")

    compiler_out = """
src/service.ts:14:2 - error TS2304: Cannot find name 'foo'.
src/handler.go:28:5: undefined: bar
"""
    files = healer.extract_failing_files(compiler_out)
    assert any("service.ts" in f for f in files)
    assert any("handler.go" in f for f in files)


def test_auto_healer_zero_failures_baseline_success(temp_workspace):
    console = Console(quiet=True)
    healer = AutoHealer(workspace_root=temp_workspace, console=console)

    with patch.object(healer, "run_command", return_value=(0, "All 42 tests passed!", "")):
        result = healer.heal("pytest")
        assert result["success"] is True
        assert result["healed"] is False
        assert result["attempts"] == 0
        assert "Baseline command succeeded" in result["message"]


def test_auto_healer_successful_repair_on_first_attempt(temp_workspace):
    console = Console(quiet=True)
    healer = AutoHealer(workspace_root=temp_workspace, console=console)

    # Initial buggy code
    target_file = temp_workspace / "src" / "calculator.py"
    target_file.write_text("def multiply(a, b): return a + b\n")

    # Command mock: first call fails (code=1), second call succeeds (code=0)
    command_outputs = [
        (1, "FAILED tests/test_calc.py::test_mult - AssertionError", 'File "src/calculator.py", line 1, in multiply'),
        (0, "1 passed in 0.05s", "")
    ]
    call_idx = 0

    def mock_run_cmd(cmd, timeout_s=60):
        nonlocal call_idx
        res = command_outputs[min(call_idx, len(command_outputs) - 1)]
        call_idx += 1
        return res

    mock_patch_response = GenerationResponse(
        text="""
```json
{
  "root_cause": "Operator was addition instead of multiplication",
  "file_path": "src/calculator.py",
  "action": "edit",
  "find_str": "return a + b",
  "replace_str": "return a * b"
}
```
"""
    )

    with patch.object(healer, "run_command", side_effect=mock_run_cmd), \
         patch.object(healer.gateway, "generate", return_value=mock_patch_response):

        result = healer.heal("pytest", max_attempts=2)
        assert result["healed"] is True
        assert result["attempts"] == 1
        assert "def multiply(a, b): return a * b" in target_file.read_text()


def test_auto_healer_regression_triggers_rollback(temp_workspace):
    console = Console(quiet=True)
    healer = AutoHealer(workspace_root=temp_workspace, console=console)

    target_file = temp_workspace / "src" / "core.py"
    original_code = "def stable_func(): return 'original'\n"
    target_file.write_text(original_code)

    # Command mock: test consistently fails
    always_failing = (1, "FAILED tests/test_core.py", 'File "src/core.py", line 1')

    mock_bad_patch = GenerationResponse(
        text="""
```diff
--- a/src/core.py
+++ b/src/core.py
@@ -1,1 +1,1 @@
-def stable_func(): return 'original'
+def stable_func(): return 'broken_patch'
```
"""
    )

    with patch.object(healer, "run_command", return_value=always_failing), \
         patch.object(healer.gateway, "generate", return_value=mock_bad_patch):

        result = healer.heal("pytest", max_attempts=2)
        assert result["healed"] is False
        assert result["attempts"] == 2
        # Verify rollback restored original code
        assert target_file.read_text() == original_code


def test_auto_healer_timeout_handling(temp_workspace):
    console = Console(quiet=True)
    healer = AutoHealer(workspace_root=temp_workspace, console=console)

    with patch("subprocess.run", side_effect=TimeoutError("timed out")):
        code, out, err = healer.run_command("sleep 100", timeout_s=1)
        assert code != 0
        assert "timed out" in err.lower() or code == 124


@pytest.mark.parametrize("lang_ext,sample_trace", [
    (".js", 'at Object.<anonymous> (src/app.js:12:15)'),
    (".ts", 'src/controller.ts:45:9 - error TS2339: Property does not exist'),
    (".go", 'src/main.go:23:12: undefined: Config'),
    (".rs", 'src/lib.rs:18:5: error[E0425]: cannot find value `x` in this scope'),
    (".py", '  File "src/server.py", line 99, in start'),
])
def test_auto_healer_polyglot_trace_recognition(temp_workspace, lang_ext, sample_trace):
    console = Console(quiet=True)
    healer = AutoHealer(workspace_root=temp_workspace, console=console)

    test_file = temp_workspace / "src" / f"testfile{lang_ext}"
    test_file.write_text("// dummy source code\n")

    # Replace filename in trace to match
    custom_trace = sample_trace.replace("app.js", f"testfile{lang_ext}")
    custom_trace = custom_trace.replace("controller.ts", f"testfile{lang_ext}")
    custom_trace = custom_trace.replace("main.go", f"testfile{lang_ext}")
    custom_trace = custom_trace.replace("lib.rs", f"testfile{lang_ext}")
    custom_trace = custom_trace.replace("server.py", f"testfile{lang_ext}")

    detected = healer.extract_failing_files(custom_trace)
    assert any(f"testfile{lang_ext}" in f for f in detected)
