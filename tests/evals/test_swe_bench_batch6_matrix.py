"""PRUBETH SWE-bench Benchmark Suite Batch 6 Matrix (Tasks 51 to 60).

Verifies workspace initialization, seed code generation, challenge description,
and solution verification checks across:
- swe-51: Token Bucket Rate Limiter with burst allowance
- swe-52: LRU Cache with per-key TTL expiration
- swe-53: Semantic Version Range Matcher (^, ~, >=, <=)
- swe-54: Diff3 Three-Way Merge Conflict Resolution
- swe-55: Levenshtein Distance with minimal edit operations
- swe-56: Probabilistic Bloom Filter with BitArray
- swe-57: Transitive Import Dependency Ordering with Topological Sort
- swe-58: O(1) Real-Time Moving Average & Variance Aggregator
- swe-59: Standard 5-Field Cron Expression Matcher
- swe-60: Minimal Feedback Arc Set Graph Cycle Breaker
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.evals.benchmarks import get_default_benchmark_suite, get_benchmark_by_id
from prubeth.evals.harness import EvalTask


def _setup_task_workspace(task: EvalTask, ws: Path):
    for rel_path, content in task.seed_files.items():
        p = ws / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


BATCH_6_IDS = [
    "swe-51-token-bucket-rate-limiter",
    "swe-52-lru-ttl-cache",
    "swe-53-semver-range-matcher",
    "swe-54-diff3-three-way-merge",
    "swe-55-levenshtein-distance",
    "swe-56-bloom-filter-probabilistic",
    "swe-57-ast-dependency-resolver",
    "swe-58-sliding-window-moving-average",
    "swe-59-cron-expression-parser",
    "swe-60-dag-cycle-breaker",
]

@pytest.mark.parametrize("task_id", BATCH_6_IDS)
def test_batch6_task_registered_and_retrievable(task_id: str):
    task = get_benchmark_by_id(task_id)
    assert task is not None
    assert task.task_id == task_id
    assert len(task.name) > 5
    assert len(task.prompt) > 10
    assert len(task.seed_files) >= 1
    assert len(task.expected_files) >= 1
    assert len(task.verification_checks) >= 1


@pytest.mark.parametrize("task_id", BATCH_6_IDS)
def test_batch6_workspace_seed_setup(task_id: str, tmp_path):
    task = get_benchmark_by_id(task_id)
    _setup_task_workspace(task, tmp_path)

    for exp_file in task.expected_files:
        p = tmp_path / exp_file
        assert p.exists()
        assert len(p.read_text(encoding="utf-8")) > 0


@pytest.mark.parametrize("task_id", BATCH_6_IDS)
def test_batch6_suite_membership(task_id: str):
    suite = get_default_benchmark_suite()
    ids = {t.task_id for t in suite}
    assert task_id in ids
