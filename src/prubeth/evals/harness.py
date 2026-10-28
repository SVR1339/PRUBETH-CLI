"""PRUBETH Autonomous Behavioural Evaluation & Mock Harness Rig.

Provides deterministic in-memory execution of the full agent runtime against
scripted or generative mock models, enabling cost-free verification of Task Success
Rate (TSR), Pass@1, Tool Precision, and Stagnation Prevention across SWE-bench style tasks.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from unittest.mock import patch

from prubeth.runtime.controller import AutonomousRuntimeController, RuntimeConfig
from prubeth.models.gateway import GenerationResponse


@dataclass
class EvalTask:
    """Specification of an autonomous coding benchmark challenge."""
    task_id: str
    name: str
    prompt: str
    seed_files: Dict[str, str] = field(default_factory=dict)
    expected_files: List[str] = field(default_factory=list)
    verification_checks: List[Callable[[Path], bool]] = field(default_factory=list)
    max_turns: int = 6
    timeout_s: float = 30.0


@dataclass
class EvalResult:
    """Comprehensive performance metrics from an evaluation task execution."""
    task_id: str
    passed: bool
    duration_s: float
    turns_used: int
    tools_called: List[str] = field(default_factory=list)
    stagnation_detected: bool = False
    contract_violations: int = 0
    error_message: Optional[str] = None
    prompt_tokens: int = 0
    candidate_tokens: int = 0


class EvalHarness:
    """Deterministic in-memory evaluation rig for PRUBETH Autonomous Runtime."""

    def __init__(self):
        self.results: List[EvalResult] = []

    def run_task(
        self,
        task: EvalTask,
        model_responses: Optional[List[GenerationResponse]] = None
    ) -> EvalResult:
        """Executes a single benchmark task in an isolated workspace."""
        start_time = time.time()
        tools_called = []
        stagnation_detected = False

        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir).resolve()
            (ws / ".prubeth" / "memory").mkdir(parents=True, exist_ok=True)
            (ws / "src").mkdir(parents=True, exist_ok=True)

            # 1. Seed workspace files
            for rel_path, content in task.seed_files.items():
                p = ws / rel_path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")

            # 2. Provision controller in temp workspace
            config = RuntimeConfig(
                auto_approve_actions=True,
                max_execution_turns=task.max_turns
            )
            controller = AutonomousRuntimeController(
                workspace_root=str(ws),
                config=config
            )

            # 3. Execute with scripted responses or mock generator
            try:
                if model_responses:
                    resp_iter = iter(model_responses)
                    def mock_generate(*args, **kwargs):
                        try:
                            return next(resp_iter)
                        except StopIteration:
                            return GenerationResponse(text="Task completed.")

                    with patch.object(controller.gateway, "generate", side_effect=mock_generate):
                        run_res = controller.run_fluid_turn(task.prompt, max_tool_turns=task.max_turns)
                else:
                    # Default mock response: returns simple completion
                    run_res = controller.run_fluid_turn(task.prompt, max_tool_turns=task.max_turns)

                tools_called = [t.get("tool", "") for t in run_res.get("tools_executed", [])]
                stagnation_detected = any("stagnation" in t.get("output", "").lower() for t in run_res.get("tools_executed", []))

                # 4. Verify outcomes
                passed = True
                for exp in task.expected_files:
                    if not (ws / exp).is_file():
                        passed = False
                        break

                if passed:
                    for check in task.verification_checks:
                        try:
                            if not check(ws):
                                passed = False
                                break
                        except Exception:
                            passed = False
                            break

                duration = time.time() - start_time
                eval_res = EvalResult(
                    task_id=task.task_id,
                    passed=passed,
                    duration_s=duration,
                    turns_used=len(run_res.get("tools_executed", [])),
                    tools_called=tools_called,
                    stagnation_detected=stagnation_detected,
                    prompt_tokens=run_res.get("prompt_tokens", 0),
                    candidate_tokens=run_res.get("candidate_tokens", 0)
                )
            except Exception as e:
                eval_res = EvalResult(
                    task_id=task.task_id,
                    passed=False,
                    duration_s=time.time() - start_time,
                    turns_used=0,
                    error_message=str(e)
                )
            finally:
                controller.close()

        self.results.append(eval_res)
        return eval_res

    def run_suite(
        self,
        tasks: List[EvalTask],
        scripted_responses_map: Optional[Dict[str, List[GenerationResponse]]] = None
    ) -> Dict[str, Any]:
        """Runs a complete suite of benchmark tasks and aggregates metrics."""
        task_results = []
        for t in tasks:
            responses = (scripted_responses_map or {}).get(t.task_id)
            res = self.run_task(t, model_responses=responses)
            task_results.append(res)

        total = len(task_results)
        passed = sum(1 for r in task_results if r.passed)
        pass_rate = (passed / total * 100.0) if total else 0.0
        avg_turns = (sum(r.turns_used for r in task_results) / total) if total else 0.0
        avg_duration = (sum(r.duration_s for r in task_results) / total) if total else 0.0

        return {
            "total_tasks": total,
            "passed_tasks": passed,
            "pass_rate_percentage": pass_rate,
            "average_turns": avg_turns,
            "average_duration_s": avg_duration,
            "stagnation_count": sum(1 for r in task_results if r.stagnation_detected),
            "results": [r.__dict__ for r in task_results]
        }
