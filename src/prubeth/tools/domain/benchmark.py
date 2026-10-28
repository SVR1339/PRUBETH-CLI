"""PRUBETH Automated Micro-Benchmarking & Performance Profiler Tool."""

from __future__ import annotations

import statistics
import time
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class BenchmarkTool(BaseTool):
    """Executes micro-benchmarks on Python code or shell snippets and calculates latency percentiles."""

    name = "benchmark"
    description = "Benchmarks code execution latency across iterations, computing min, max, mean, p50, and p95."
    clearance_level = ToolClearanceLevel.SYSTEM_EXECUTION

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="Python statement or expression to benchmark.",
                required=True
            ),
            ToolParameter(
                name="iterations",
                type="integer",
                description="Number of benchmark iterations (default 10, max 1000).",
                required=False,
                default=10
            ),
            ToolParameter(
                name="warmup",
                type="integer",
                description="Warmup iterations to execute prior to timing (default 2).",
                required=False,
                default=2
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        code_str = arguments.get("code", "").strip()
        iterations = min(max(1, int(arguments.get("iterations", 10))), 1000)
        warmup = max(0, int(arguments.get("warmup", 2)))

        if not code_str:
            return ToolResult.fail("No code snippet provided to benchmark.", exit_code=1)

        try:
            compiled = compile(code_str, "<benchmark>", "exec")
        except SyntaxError as e:
            return ToolResult.fail(f"Benchmark code has syntax error: {e}", exit_code=1)

        scope: Dict[str, Any] = {}

        # Warmup
        for _ in range(warmup):
            try:
                exec(compiled, scope)
            except Exception as e:
                return ToolResult.fail(f"Warmup execution failed: {e}", exit_code=1)

        timings_ms: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            exec(compiled, scope)
            duration_ms = (time.perf_counter() - start) * 1000.0
            timings_ms.append(duration_ms)

        timings_sorted = sorted(timings_ms)
        min_ms = timings_sorted[0]
        max_ms = timings_sorted[-1]
        mean_ms = statistics.mean(timings_sorted)
        median_ms = statistics.median(timings_sorted)
        p95_idx = int(0.95 * len(timings_sorted))
        p95_ms = timings_sorted[min(p95_idx, len(timings_sorted) - 1)]

        summary = (
            f"Benchmark Results ({iterations} iterations, {warmup} warmup):\n"
            f"  Mean:   {mean_ms:.3f} ms\n"
            f"  Median: {median_ms:.3f} ms (p50)\n"
            f"  p95:    {p95_ms:.3f} ms\n"
            f"  Min:    {min_ms:.3f} ms\n"
            f"  Max:    {max_ms:.3f} ms\n"
        )

        return ToolResult.ok(
            summary,
            metadata={
                "iterations": iterations,
                "warmup": warmup,
                "mean_ms": round(mean_ms, 4),
                "median_ms": round(median_ms, 4),
                "p95_ms": round(p95_ms, 4),
                "min_ms": round(min_ms, 4),
                "max_ms": round(max_ms, 4),
            }
        )
