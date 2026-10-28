"""Comprehensive SWE-bench & Behavioural Scenario Matrix for PRUBETH EvalHarness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List
import pytest

from prubeth.evals.harness import EvalHarness, EvalTask, EvalResult
from prubeth.evals.benchmarks import get_default_benchmark_suite, get_benchmark_by_id
from prubeth.models.gateway import GenerationResponse


def _make_tool_response(tool_name: str, args: dict, explanation: str = "Applying patch") -> GenerationResponse:
    tool_payload = json.dumps({"tool": tool_name, "args": args})
    return GenerationResponse(text=f"{explanation}\n```tool\n{tool_payload}\n```\n")


def test_eval_benchmark_suite_registry():
    """Verifies that all standard SWE-bench evaluation tasks are registered and valid."""
    suite = get_default_benchmark_suite()
    assert len(suite) >= 8
    task_ids = [t.task_id for t in suite]
    assert len(task_ids) == len(set(task_ids)), "Task IDs must be strictly unique"
    for t in suite:
        assert t.task_id.startswith("swe-")
        assert len(t.name) > 5
        assert len(t.prompt) > 10
        assert len(t.expected_files) > 0


def test_eval_benchmark_lookup_by_id():
    """Verifies retrieval of specific benchmark scenarios."""
    task = get_benchmark_by_id("swe-01-python-division-guard")
    assert task is not None
    assert "safe_divide" in task.prompt

    missing = get_benchmark_by_id("non-existent-benchmark-id")
    assert missing is None


@pytest.mark.parametrize("benchmark_id", [
    "swe-01-python-division-guard",
    "swe-02-ts-optional-chaining",
    "swe-03-cve-sql-parameterization",
    "swe-04-go-nil-slice-guard",
    "swe-05-rust-option-unwrap-safe",
    "swe-06-memory-leak-clearance",
    "swe-08-polyglot-json-serializer"
])
def test_swe_bench_scenarios_execution(benchmark_id: str):
    """Executes each SWE-bench scenario with mock tool execution to verify verification check pass."""
    task = get_benchmark_by_id(benchmark_id)
    assert task is not None

    harness = EvalHarness()

    # Create scripted responses that apply the required patch
    if benchmark_id == "swe-01-python-division-guard":
        responses = [
            _make_tool_response(
                "edit_file",
                {
                    "path": "src/math_utils.py",
                    "target": "    # BUG: raises ZeroDivisionError when b == 0\n    return a / b\n",
                    "replacement": "    if b == 0:\n        return default\n    return a / b\n"
                },
                "Adding division by zero guard"
            ),
            GenerationResponse(text="Fix completed successfully.")
        ]
    elif benchmark_id == "swe-02-ts-optional-chaining":
        responses = [
            _make_tool_response(
                "edit_file",
                {
                    "path": "src/user_service.ts",
                    "target": "  return user.profile.avatar;\n",
                    "replacement": "  return user?.profile?.avatar ?? '/default.png';\n"
                },
                "Adding optional chaining to TS user avatar"
            ),
            GenerationResponse(text="TS optional chaining completed.")
        ]
    elif benchmark_id == "swe-03-cve-sql-parameterization":
        responses = [
            _make_tool_response(
                "edit_file",
                {
                    "path": "src/db/users.py",
                    "target": "    query = f\"SELECT id, name FROM users WHERE username = '{username}'\"\n    return cursor.execute(query).fetchall()\n",
                    "replacement": "    query = \"SELECT id, name FROM users WHERE username = %s\"\n    return cursor.execute(query, (username,)).fetchall()\n"
                },
                "Remediating SQL injection vulnerability with parameterized query"
            ),
            GenerationResponse(text="CVE fix applied.")
        ]
    elif benchmark_id == "swe-04-go-nil-slice-guard":
        responses = [
            _make_tool_response(
                "edit_file",
                {
                    "path": "src/pkg/handler.go",
                    "target": "    return items[0]\n",
                    "replacement": "    if len(items) == 0 {\n        return \"\"\n    }\n    return items[0]\n"
                },
                "Adding nil slice guard to Go handler"
            ),
            GenerationResponse(text="Go nil check added.")
        ]
    elif benchmark_id == "swe-05-rust-option-unwrap-safe":
        responses = [
            _make_tool_response(
                "edit_file",
                {
                    "path": "src/lookup.rs",
                    "target": "    // BUG: unwrap() causes panic on missing key\n    map.get(key).unwrap().clone()\n",
                    "replacement": "    map.get(key).cloned().unwrap_or_default()\n"
                },
                "Replacing unwrap with safe Option handling in Rust function"
            ),
            GenerationResponse(text="Rust panic eliminated.")
        ]
    elif benchmark_id == "swe-06-memory-leak-clearance":
        responses = [
            _make_tool_response(
                "edit_file",
                {
                    "path": "src/cache.py",
                    "target": "    def set(self, k, v):\n        self._store[k] = v\n",
                    "replacement": "    def set(self, k, v):\n        self._store[k] = v\n\n    def clear(self):\n        self._store.clear()\n"
                },
                "Adding clear cache method"
            ),
            GenerationResponse(text="Cache clear added.")
        ]
    elif benchmark_id == "swe-08-polyglot-json-serializer":
        responses = [
            _make_tool_response(
                "edit_file",
                {
                    "path": "src/serializer.py",
                    "target": "    return json.dumps(data)\n",
                    "replacement": "    return json.dumps(data, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o))\n"
                },
                "Adding datetime isoformat handler"
            ),
            GenerationResponse(text="Serializer updated.")
        ]

    res = harness.run_task(task, model_responses=responses)
    assert res.passed is True
    assert res.turns_used >= 1
    assert "edit_file" in res.tools_called
    assert res.duration_s >= 0.0


def test_swe_bench_multimodule_refactor():
    """Verifies multi-module refactor scenario where files are extracted and imports updated."""
    task = get_benchmark_by_id("swe-07-multimodule-refactor")
    assert task is not None

    harness = EvalHarness()
    responses = [
        # Turn 1: Write new module src/formatters.py
        _make_tool_response(
            "write_file",
            {
                "path": "src/formatters.py",
                "content": "def format_currency(amount: float) -> str:\n    return f'${amount:.2f}'\n"
            },
            "Extracting format_currency to src/formatters.py"
        ),
        # Turn 2: Edit src/billing.py to import format_currency
        _make_tool_response(
            "edit_file",
            {
                "path": "src/billing.py",
                "target": "def format_currency(amount: float) -> str:\n    return f'${amount:.2f}'\n\n",
                "replacement": "from src.formatters import format_currency\n\n"
            },
            "Updating src/billing.py imports"
        ),
        GenerationResponse(text="Refactoring complete.")
    ]

    res = harness.run_task(task, model_responses=responses)
    assert res.passed is True
    assert "write_file" in res.tools_called
    assert "edit_file" in res.tools_called
