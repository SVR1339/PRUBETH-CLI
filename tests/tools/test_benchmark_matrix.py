"""Deep Matrix Tests for BenchmarkTool across diverse workloads and percentile invariants."""

import pytest
from prubeth.tools.domain.benchmark import BenchmarkTool


@pytest.fixture
def bench():
    return BenchmarkTool()


# =========================================================================
# Matrix: 10 Mathematical and Algorithmic Workloads
# =========================================================================

BENCHMARK_WORKLOADS = [
    ("list_comprehension", "res = [i ** 2 for i in range(500)]"),
    ("string_concatenation", "s = ''.join([str(i) for i in range(200)])"),
    ("dict_creation", "d = {f'k_{i}': i for i in range(200)}"),
    ("set_intersection", "s1 = set(range(100)); s2 = set(range(50, 150)); res = s1 & s2"),
    ("sorting", "arr = list(reversed(range(300))); arr.sort()"),
    ("math_operations", "import math; res = sum(math.sin(i) for i in range(200))"),
    ("json_roundtrip", "import json; s = json.dumps({'a': list(range(100))}); d = json.loads(s)"),
    ("hashlib_sha256", "import hashlib; h = hashlib.sha256(b'test data' * 50).hexdigest()"),
    ("regex_matching", "import re; m = re.findall(r'\\d+', 'abc 123 def 456 ghi 789' * 10)"),
    ("recursion_fibonacci", "def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2); fib(10)"),
]

@pytest.mark.parametrize("name, code", BENCHMARK_WORKLOADS)
def test_matrix_benchmark_workloads(bench, name, code):
    res = bench.execute({
        "code": code,
        "iterations": 10,
        "warmup": 2
    })
    assert res.success is True
    meta = res.metadata
    assert meta["iterations"] == 10
    assert meta["warmup"] == 2
    # Invariant: min <= median <= p95 <= max
    assert meta["min_ms"] <= meta["median_ms"]
    assert meta["median_ms"] <= meta["p95_ms"]
    assert meta["p95_ms"] <= meta["max_ms"]


# =========================================================================
# Matrix: Iteration Counts and Warmup Variations
# =========================================================================

@pytest.mark.parametrize("iters, warmup", [
    (1, 0),
    (5, 1),
    (10, 2),
    (20, 5),
    (50, 10),
])
def test_matrix_iteration_and_warmup_scalings(bench, iters, warmup):
    res = bench.execute({
        "code": "x = 42 * 42",
        "iterations": iters,
        "warmup": warmup
    })
    assert res.success is True
    assert res.metadata["iterations"] == iters
    assert res.metadata["warmup"] == warmup
    assert res.metadata["mean_ms"] >= 0.0


# =========================================================================
# Matrix: Error Handling and Syntax Invariants
# =========================================================================

@pytest.mark.parametrize("bad_code", [
    "def broken_syntax(:",
    "raise RuntimeError('Intentional crash')",
    "undefined_variable_lookup + 1",
])
def test_matrix_benchmark_handles_errors_gracefully(bench, bad_code):
    res = bench.execute({"code": bad_code, "iterations": 5, "warmup": 1})
    assert res.success is False
    assert res.exit_code == 1
