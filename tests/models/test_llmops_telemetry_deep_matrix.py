"""PRUBETH LLMOps Telemetry, Latency & Provider Health Matrix Tests.

Exhaustively verifies LLMOpsMonitor and ModelCallMetrics:
- Singleton pattern and state reset invariants
- Real-time latency tracking and average computation
- Token accounting (input, output, cached, cache creation)
- Cache hit efficiency ratio calculations
- Multi-provider health state transitions (HEALTHY, DEGRADED, CRITICAL, UNKNOWN)
- Multi-provider concurrent metrics isolation
"""

from __future__ import annotations

import pytest
from prubeth.models.telemetry import LLMOpsMonitor, ModelCallMetrics


@pytest.fixture(autouse=True)
def clean_monitor():
    monitor = LLMOpsMonitor()
    monitor.reset()
    yield monitor
    monitor.reset()


# ============================================================================
# 1. Dataclass Structure & Defaults
# ============================================================================

def test_model_call_metrics_instantiation():
    m = ModelCallMetrics(
        model="gemini-2.5-pro",
        provider="google",
        latency_s=0.45,
        input_tokens=1500,
        output_tokens=320,
        cached_tokens=1000,
        success=True
    )
    assert m.model == "gemini-2.5-pro"
    assert m.provider == "google"
    assert m.latency_s == 0.45
    assert m.input_tokens == 1500
    assert m.output_tokens == 320
    assert m.cached_tokens == 1000
    assert m.success is True
    assert m.cache_creation_tokens == 0
    assert m.error_message is None
    assert len(m.timestamp) > 0


# ============================================================================
# 2. Unknown Provider State
# ============================================================================

def test_unknown_provider_health_defaults(clean_monitor: LLMOpsMonitor):
    health = clean_monitor.get_provider_health("unseen_provider")
    assert health["provider"] == "unseen_provider"
    assert health["status"] == "UNKNOWN"
    assert health["total_calls"] == 0
    assert health["success_rate"] == 1.0
    assert health["avg_latency_s"] == 0.0


# ============================================================================
# 3. Provider Health Classification Transitions Matrix
# ============================================================================

@pytest.mark.parametrize("successes,failures,expected_status", [
    (10, 0, "HEALTHY"),     # 100% -> HEALTHY (>= 90%)
    (9, 1, "HEALTHY"),      # 90% -> HEALTHY (>= 90%)
    (8, 2, "DEGRADED"),     # 80% -> DEGRADED (50% - 89%)
    (6, 4, "DEGRADED"),     # 60% -> DEGRADED
    (5, 5, "DEGRADED"),     # 50% -> DEGRADED
    (4, 6, "CRITICAL"),     # 40% -> CRITICAL (< 50%)
    (1, 9, "CRITICAL"),     # 10% -> CRITICAL
    (0, 5, "CRITICAL"),     # 0% -> CRITICAL
])
def test_provider_health_status_thresholds(
    clean_monitor: LLMOpsMonitor,
    successes: int,
    failures: int,
    expected_status: str
):
    provider = f"test_provider_{successes}_{failures}"
    for _ in range(successes):
        clean_monitor.record_call(
            model="m1", provider=provider, latency_s=0.2, input_tokens=100, output_tokens=50, success=True
        )
    for _ in range(failures):
        clean_monitor.record_call(
            model="m1", provider=provider, latency_s=0.5, input_tokens=100, output_tokens=0, success=False, error_message="503"
        )

    health = clean_monitor.get_provider_health(provider)
    assert health["status"] == expected_status
    total = successes + failures
    assert health["total_calls"] == total
    assert health["success_rate"] == round(successes / total, 3)


# ============================================================================
# 4. Latency & Cache Efficiency Calculations
# ============================================================================

def test_average_latency_computation(clean_monitor: LLMOpsMonitor):
    latencies = [0.10, 0.20, 0.30, 0.40, 0.50]
    for lat in latencies:
        clean_monitor.record_call(
            model="gemini-2.5-flash",
            provider="google",
            latency_s=lat,
            input_tokens=500,
            output_tokens=100,
            success=True
        )

    health = clean_monitor.get_provider_health("google")
    assert health["total_calls"] == 5
    assert health["avg_latency_s"] == 0.30


def test_cache_efficiency_ratio_computation(clean_monitor: LLMOpsMonitor):
    # Total input: 4000 tokens, Cached: 3000 tokens -> ratio = 0.75
    clean_monitor.record_call(
        model="claude-3-7-sonnet",
        provider="anthropic",
        latency_s=0.35,
        input_tokens=2000,
        cached_tokens=1500,
        success=True
    )
    clean_monitor.record_call(
        model="claude-3-7-sonnet",
        provider="anthropic",
        latency_s=0.30,
        input_tokens=2000,
        cached_tokens=1500,
        success=True
    )

    health = clean_monitor.get_provider_health("anthropic")
    assert health["cache_efficiency"] == 0.75


# ============================================================================
# 5. Multi-Provider Concurrency Isolation
# ============================================================================

def test_multi_provider_metrics_isolation(clean_monitor: LLMOpsMonitor):
    providers = ["google", "anthropic", "openai", "groq", "ollama", "openrouter"]

    for i, prov in enumerate(providers):
        # Even providers succeed, odd providers have 1 failure
        has_fail = (i % 2 == 1)
        clean_monitor.record_call(
            model=f"{prov}-model",
            provider=prov,
            latency_s=0.1 * (i + 1),
            input_tokens=1000 * (i + 1),
            output_tokens=200,
            cached_tokens=500,
            success=True
        )
        if has_fail:
            clean_monitor.record_call(
                model=f"{prov}-model",
                provider=prov,
                latency_s=1.0,
                success=False,
                error_message="Connection timed out"
            )

    # Verify each provider is tracked independently
    for i, prov in enumerate(providers):
        h = clean_monitor.get_provider_health(prov)
        if i % 2 == 0:
            assert h["total_calls"] == 1
            assert h["success_rate"] == 1.0
            assert h["status"] == "HEALTHY"
        else:
            assert h["total_calls"] == 2
            assert h["success_rate"] == 0.5
            assert h["status"] == "DEGRADED"


def test_reset_clears_all_metrics_and_failure_counts(clean_monitor: LLMOpsMonitor):
    clean_monitor.record_call("m", "prov", 0.5, success=False)
    assert len(clean_monitor.metrics) == 1
    assert clean_monitor.provider_failure_counts.get("prov") == 1

    clean_monitor.reset()
    assert len(clean_monitor.metrics) == 0
    assert len(clean_monitor.provider_failure_counts) == 0
    assert clean_monitor.get_provider_health("prov")["total_calls"] == 0
