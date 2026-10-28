"""Extended SWE-bench Suite & Advanced Resilience Evaluation Matrix for PRUBETH."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from prubeth.evals.harness import EvalHarness, EvalTask, EvalResult
from prubeth.evals.benchmarks import get_default_benchmark_suite, get_benchmark_by_id
from prubeth.models.gateway import GenerationResponse


def _make_tool_response(tool_name: str, args: dict, explanation: str = "Applying fix") -> GenerationResponse:
    tool_payload = json.dumps({"tool": tool_name, "args": args})
    return GenerationResponse(text=f"{explanation}\n```tool\n{tool_payload}\n```\n")


@pytest.mark.parametrize("benchmark_id", [
    "swe-09-concurrency-race-mutex",
    "swe-10-async-timeout-handler",
    "swe-11-schema-migration-v2",
    "swe-12-regex-redos-mitigation",
    "swe-13-dockerfile-security-nonroot",
    "swe-14-rate-limiter-token-bucket",
    "swe-15-jwt-signature-algorithm-guard",
    "swe-16-circuit-breaker-fallback-handler",
])
def test_extended_benchmarks_registered_and_resolvable(benchmark_id: str):
    """Verifies that extended benchmark tasks 09 through 16 resolve cleanly."""
    task = get_benchmark_by_id(benchmark_id)
    assert task is not None
    assert task.task_id == benchmark_id
    assert len(task.expected_files) >= 1
    assert len(task.verification_checks) >= 1
    assert task.name.strip() != ""


def test_swe_09_concurrency_race_mutex_e2e():
    """Validates repair of concurrency race condition via thread lock."""
    task = get_benchmark_by_id("swe-09-concurrency-race-mutex")
    assert task is not None

    harness = EvalHarness()
    fixed_code = (
        "import threading\n\n"
        "class ThreadSafeCounter:\n"
        "    def __init__(self):\n"
        "        self.count = 0\n"
        "        self.lock = threading.Lock()\n\n"
        "    def increment(self):\n"
        "        with self.lock:\n"
        "            self.count += 1\n"
    )
    mock_responses = [
        _make_tool_response("write_file", {"path": "src/counter.py", "content": fixed_code}),
        GenerationResponse(text="Counter protected with threading.Lock.")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is True
    assert "write_file" in res.tools_called
    assert res.turns_used >= 1


def test_swe_10_async_timeout_handler_e2e():
    """Validates addition of asyncio.wait_for timeout protection."""
    task = get_benchmark_by_id("swe-10-async-timeout-handler")
    assert task is not None

    harness = EvalHarness()
    fixed_code = (
        "import asyncio\n\n"
        "async def fetch_resource(client, url: str) -> str:\n"
        "    return await asyncio.wait_for(client.get(url), timeout=5.0)\n"
    )
    mock_responses = [
        _make_tool_response("write_file", {"path": "src/client.py", "content": fixed_code}),
        GenerationResponse(text="Wrapped client call in asyncio.wait_for.")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is True
    assert "write_file" in res.tools_called


def test_swe_11_schema_migration_e2e():
    """Validates SQL schema migration script with default backfill."""
    task = get_benchmark_by_id("swe-11-schema-migration-v2")
    assert task is not None

    harness = EvalHarness()
    sql_content = "ALTER TABLE users ADD COLUMN status VARCHAR(32) DEFAULT 'active';\n"
    mock_responses = [
        _make_tool_response("write_file", {"path": "src/migrations/v2_add_status.sql", "content": sql_content}),
        GenerationResponse(text="Added ALTER TABLE migration.")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is True


def test_swe_12_regex_redos_mitigation_e2e():
    """Validates remediation of exponential ReDoS regex."""
    task = get_benchmark_by_id("swe-12-regex-redos-mitigation")
    assert task is not None

    harness = EvalHarness()
    safe_code = (
        "import re\n\n"
        "def validate_username(s: str) -> bool:\n"
        "    if len(s) > 64:\n"
        "        return False\n"
        "    return bool(re.match(r'^[a-zA-Z0-9_-]{1,64}$', s))\n"
    )
    mock_responses = [
        _make_tool_response("write_file", {"path": "src/validators.py", "content": safe_code}),
        GenerationResponse(text="Replaced vulnerable regex with safe bounded pattern.")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is True


def test_swe_13_dockerfile_security_nonroot_e2e():
    """Validates container hardening with non-root USER directive."""
    task = get_benchmark_by_id("swe-13-dockerfile-security-nonroot")
    assert task is not None

    harness = EvalHarness()
    hardened_dockerfile = (
        "FROM python:3.11-slim\n"
        "RUN useradd -m -u 1000 appuser\n"
        "WORKDIR /app\n"
        "COPY . /app\n"
        "USER appuser\n"
        "CMD [\"python\", \"-m\", \"prubeth.cli.main\"]\n"
    )
    mock_responses = [
        _make_tool_response("write_file", {"path": "Dockerfile", "content": hardened_dockerfile}),
        GenerationResponse(text="Hardened Dockerfile with non-root appuser.")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is True


def test_swe_14_rate_limiter_token_bucket_e2e():
    """Validates token bucket rate limiter implementation."""
    task = get_benchmark_by_id("swe-14-rate-limiter-token-bucket")
    assert task is not None

    harness = EvalHarness()
    impl = (
        "import time\n\n"
        "class TokenBucketLimiter:\n"
        "    def __init__(self, capacity: int, refill_rate_per_s: float):\n"
        "        self.capacity = capacity\n"
        "        self.refill_rate = refill_rate_per_s\n"
        "        self.tokens = float(capacity)\n"
        "        self.last_update = time.time()\n\n"
        "    def allow_request(self) -> bool:\n"
        "        now = time.time()\n"
        "        elapsed = now - self.last_update\n"
        "        self.tokens = min(float(self.capacity), self.tokens + elapsed * self.refill_rate)\n"
        "        self.last_update = now\n"
        "        if self.tokens >= 1.0:\n"
        "            self.tokens -= 1.0\n"
        "            return True\n"
        "        return False\n"
    )
    mock_responses = [
        _make_tool_response("write_file", {"path": "src/limiter.py", "content": impl}),
        GenerationResponse(text="Implemented token bucket replenishment and consumption.")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is True


def test_swe_15_jwt_algorithm_guard_e2e():
    """Validates JWT algorithm confusion prevention."""
    task = get_benchmark_by_id("swe-15-jwt-signature-algorithm-guard")
    assert task is not None

    harness = EvalHarness()
    safe_jwt = (
        "import jwt\n\n"
        "def decode_token(token: str, secret: str):\n"
        "    return jwt.decode(token, secret, algorithms=['HS256'])\n"
    )
    mock_responses = [
        _make_tool_response("write_file", {"path": "src/auth.py", "content": safe_jwt}),
        GenerationResponse(text="Hardened JWT decode with explicit algorithms=['HS256'].")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is True


def test_swe_16_circuit_breaker_fallback_e2e():
    """Validates resilient circuit breaker exception catch and fallback."""
    task = get_benchmark_by_id("swe-16-circuit-breaker-fallback-handler")
    assert task is not None

    harness = EvalHarness()
    resilient_code = (
        "class CircuitOpenError(Exception):\n"
        "    pass\n\n"
        "def call_service_with_fallback(service_fn, fallback_val):\n"
        "    try:\n"
        "        return service_fn()\n"
        "    except CircuitOpenError:\n"
        "        return fallback_val\n"
    )
    mock_responses = [
        _make_tool_response("write_file", {"path": "src/service.py", "content": resilient_code}),
        GenerationResponse(text="Wrapped call in try/except CircuitOpenError with fallback.")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is True


def test_swe_bench_extended_failure_detection():
    """Verifies that if the agent fails to implement the required guard, task is marked failed."""
    task = get_benchmark_by_id("swe-09-concurrency-race-mutex")
    assert task is not None

    harness = EvalHarness()
    # Agent just says done without writing lock
    mock_responses = [
        GenerationResponse(text="I have reviewed the code and everything looks fine!")
    ]

    res = harness.run_task(task, model_responses=mock_responses)
    assert res.passed is False
    assert len(res.tools_called) == 0


def test_extended_suite_overall_count():
    """Ensures suite has at least 16 canonical benchmark challenges."""
    suite = get_default_benchmark_suite()
    assert len(suite) >= 16
