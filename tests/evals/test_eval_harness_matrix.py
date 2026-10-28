"""PRUBETH EvalHarness Autonomous Behavioural Benchmark Matrix.

Runs deterministically against in-memory mock runtimes with zero API costs,
evaluating Pass@1, Tool Precision, AST Contract Compliance, and Stagnation Prevention.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest

from prubeth.evals.harness import EvalHarness, EvalTask, EvalResult
from prubeth.models.gateway import GenerationResponse


@pytest.fixture
def harness():
    return EvalHarness()


def test_eval_harness_simple_file_creation(harness):
    task = EvalTask(
        task_id="EVAL_001_FILE_CREATION",
        name="Create Configuration File",
        prompt="Create a config file at src/config.py with DEFAULT_PORT = 8080",
        expected_files=["src/config.py"],
        verification_checks=[
            lambda ws: "DEFAULT_PORT = 8080" in (ws / "src" / "config.py").read_text()
        ]
    )

    mock_resp_1 = GenerationResponse(
        text="""
I will create the configuration file:
```tool
{"tool": "write_file", "args": {"path": "src/config.py", "content": "DEFAULT_PORT = 8080\\n"}}
```
"""
    )
    mock_resp_2 = GenerationResponse(text="Configuration file created.")

    res = harness.run_task(task, model_responses=[mock_resp_1, mock_resp_2])
    assert res.passed is True
    assert res.turns_used == 1
    assert "write_file" in res.tools_called
    assert res.duration_s < 5.0


def test_eval_harness_surgical_bug_fix(harness):
    seed_content = "def calculate_discount(price: float) -> float:\n    return price * 0.5  # Bug: should be 0.1\n"
    task = EvalTask(
        task_id="EVAL_002_DISCOUNT_FIX",
        name="Fix Discount Calculation",
        prompt="Fix the discount calculation in src/pricing.py to 0.1 instead of 0.5",
        seed_files={"src/pricing.py": seed_content},
        expected_files=["src/pricing.py"],
        verification_checks=[
            lambda ws: "0.1" in (ws / "src" / "pricing.py").read_text(),
            lambda ws: "0.5" not in (ws / "src" / "pricing.py").read_text()
        ]
    )

    mock_edit = GenerationResponse(
        text="""
```tool
{"tool": "edit_file", "args": {"path": "src/pricing.py", "target": "return price * 0.5  # Bug: should be 0.1", "replacement": "return price * 0.1"}}
```
"""
    )
    mock_final = GenerationResponse(text="Bug resolved.")

    res = harness.run_task(task, model_responses=[mock_edit, mock_final])
    assert res.passed is True
    assert "edit_file" in res.tools_called


def test_eval_harness_missing_expected_file_fails(harness):
    task = EvalTask(
        task_id="EVAL_003_FAIL_MISSING_FILE",
        name="Expect Non-Existent File",
        prompt="Do nothing",
        expected_files=["src/never_created.txt"]
    )
    mock_idle = GenerationResponse(text="I have done nothing.")
    res = harness.run_task(task, model_responses=[mock_idle])
    assert res.passed is False


def test_eval_harness_stagnation_detection_flagged(harness):
    task = EvalTask(
        task_id="EVAL_004_STAGNATION",
        name="Cyclic Loop Stagnation Test",
        prompt="Trapped in loop",
        expected_files=[]
    )
    loop_call = GenerationResponse(
        text="```tool\n{\"tool\": \"list_dir\", \"args\": {\"path\": \".\"}}\n```"
    )
    res = harness.run_task(task, model_responses=[loop_call] * 5)
    assert res.stagnation_detected is True


def test_eval_harness_suite_aggregation(harness):
    task_a = EvalTask(
        task_id="SUITE_01",
        name="Task A",
        prompt="Create a",
        expected_files=["src/a.txt"]
    )
    task_b = EvalTask(
        task_id="SUITE_02",
        name="Task B",
        prompt="Create b",
        expected_files=["src/b.txt"]
    )

    resp_a = [
        GenerationResponse(text='```tool\n{"tool": "write_file", "args": {"path": "src/a.txt", "content": "A"}}\n```'),
        GenerationResponse(text="Done")
    ]
    resp_b = [
        GenerationResponse(text="No tools used")
    ]

    suite_summary = harness.run_suite(
        tasks=[task_a, task_b],
        scripted_responses_map={"SUITE_01": resp_a, "SUITE_02": resp_b}
    )

    assert suite_summary["total_tasks"] == 2
    assert suite_summary["passed_tasks"] == 1
    assert suite_summary["pass_rate_percentage"] == 50.0
    assert suite_summary["average_turns"] >= 0.5


@pytest.mark.parametrize("file_ext,decl", [
    (".py", "def service_func(): return True\n"),
    (".ts", "export function serviceFunc(): boolean { return true; }\n"),
    (".go", "package main\nfunc ServiceFunc() bool { return true }\n"),
    (".rs", "pub fn service_func() -> bool { true }\n"),
])
def test_eval_harness_polyglot_generation(harness, file_ext, decl):
    target_rel = f"src/generated{file_ext}"
    task = EvalTask(
        task_id=f"POLYGLOT_{file_ext}",
        name=f"Generate {file_ext}",
        prompt=f"Create {target_rel}",
        expected_files=[target_rel],
        verification_checks=[
            lambda ws: (ws / target_rel).is_file() and len((ws / target_rel).read_text()) > 10
        ]
    )

    resp_1 = GenerationResponse(
        text=f'```tool\n{{"tool": "write_file", "args": {{"path": "{target_rel}", "content": "{decl.replace(chr(10), "\\n")}"}}}}\n```'
    )
    resp_2 = GenerationResponse(text="Created polyglot artifact.")

    res = harness.run_task(task, model_responses=[resp_1, resp_2])
    assert res.passed is True
