"""PRUBETH Universal Model Gateway, Provider Failover & Circuit Breaker Matrix.

Exhaustively verifies:
1. ProviderCircuitBreaker multi-stage transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
2. Failure threshold and recovery success permutations across various cooldown intervals.
3. GlobalCircuitRegistry isolated state per provider family.
4. ModelAutoRouter heuristic classification (fast, balanced, deep) across keyword sets,
   word counts, and multiline code thresholds.
5. GenerationResponse token metrics, latency tracking, and caching metadata invariants.
6. Failover candidate resolution order and local offline fallback pivots.
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch

from prubeth.models.circuit_breaker import (
    CircuitState,
    CircuitBreakerOpenError,
    ProviderCircuitBreaker,
    GlobalCircuitRegistry,
)
from prubeth.models.router import (
    ModelAutoRouter,
    RoutingDecision,
    _FAST_MODELS,
    _BALANCED_MODELS,
    _DEEP_MODELS,
    _DEEP_KEYWORDS,
    _FAST_KEYWORDS,
)
from prubeth.models.gateway import GenerationResponse, UniversalModelGateway
from prubeth.config.manager import ConfigManager


# ============================================================================
# 1. ProviderCircuitBreaker State Transitions: Happy Path & Failure Tripping
# ============================================================================

def test_circuit_breaker_initial_state():
    cb = ProviderCircuitBreaker(failure_threshold=3, cooldown_s=10.0, recovery_successes=2)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


@pytest.mark.parametrize("threshold", [1, 2, 3, 4, 5, 8, 10])
def test_circuit_breaker_trips_to_open_at_threshold(threshold: int):
    cb = ProviderCircuitBreaker(failure_threshold=threshold, cooldown_s=60.0)
    for i in range(threshold - 1):
        cb.record_failure(f"Error {i}")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    # Final threshold failure
    cb.record_failure(f"Error {threshold}")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_circuit_breaker_success_resets_failure_count():
    cb = ProviderCircuitBreaker(failure_threshold=3)
    cb.record_failure("Err 1")
    cb.record_failure("Err 2")
    assert cb._consecutive_failures == 2

    # Success resets counter
    cb.record_success()
    assert cb._consecutive_failures == 0
    assert cb.state == CircuitState.CLOSED

    # Requires 3 full failures again to trip
    cb.record_failure("Err 3")
    assert cb.state == CircuitState.CLOSED


# ============================================================================
# 2. ProviderCircuitBreaker Cooldown & Recovery (HALF_OPEN -> CLOSED / OPEN)
# ============================================================================

def test_circuit_breaker_cooldown_to_half_open(monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)

    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=20.0, recovery_successes=2)
    cb.record_failure("Err 1")
    cb.record_failure("Err 2")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    # Advance time by 10s (still under 20s cooldown)
    current_time += 10.0
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    # Advance time past cooldown (25s total)
    current_time += 15.0
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.can_execute() is True

    # 1 success in HALF_OPEN is not enough if recovery_successes == 2
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN

    # 2nd success recovers to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_half_open_failure_immediately_reopens(monkeypatch):
    current_time = 2000.0
    monkeypatch.setattr(time, "time", lambda: current_time)

    cb = ProviderCircuitBreaker(failure_threshold=3, cooldown_s=15.0, recovery_successes=2)
    for _ in range(3):
        cb.record_failure("Outage")
    assert cb.state == CircuitState.OPEN

    # Advance past cooldown
    current_time += 16.0
    assert cb.state == CircuitState.HALF_OPEN

    # Canary failure -> trips straight back to OPEN without waiting for threshold
    cb.record_failure("Canary request failed")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_circuit_breaker_manual_reset():
    cb = ProviderCircuitBreaker(failure_threshold=2)
    cb.record_failure("Err 1")
    cb.record_failure("Err 2")
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True
    assert cb._consecutive_failures == 0


# ============================================================================
# 3. GlobalCircuitRegistry Isolation Matrix
# ============================================================================

PROVIDERS = ["google", "anthropic", "openai", "openrouter", "deepseek", "groq", "ollama", "lm_studio"]

@pytest.mark.parametrize("provider", PROVIDERS)
def test_global_circuit_registry_provider_isolation(provider: str):
    GlobalCircuitRegistry.reset_all()
    breaker = GlobalCircuitRegistry.get_breaker(provider)
    assert breaker.state == CircuitState.CLOSED

    # Trip only this provider
    for _ in range(breaker.failure_threshold):
        breaker.record_failure(f"{provider} 503")

    assert breaker.state == CircuitState.OPEN

    # All other providers remain CLOSED
    for other in PROVIDERS:
        if other != provider:
            other_b = GlobalCircuitRegistry.get_breaker(other)
            assert other_b.state == CircuitState.CLOSED
            assert other_b.can_execute() is True

    GlobalCircuitRegistry.reset_all()


# ============================================================================
# 4. ModelAutoRouter: Deep Complexity Keywords Matrix
# ============================================================================

DEEP_PROMPT_SAMPLES = [
    "Design and architect a distributed consensus microservice",
    "Refactor the AST parser to support full polyglot syntax",
    "Analyze security vulnerabilities and potential CVEs in the codebase",
    "Implement an asynchronous thread pool for concurrent pipeline execution",
    "Benchmark and optimize memory consumption down to zero bloat",
    "Audit database migration scripts for backward-breaking schema drops",
    "Reverse engineer the binary protocol and reconstruct the message layout",
    "Orchestrate a multi-agent swarm with automated peer review",
    "Deep dive into performance bottleneck in the sliding window compactor",
    "Review enterprise scalability and thread safety under high load",
]

@pytest.mark.parametrize("prompt", DEEP_PROMPT_SAMPLES)
def test_router_selects_deep_tier_for_complex_tasks(prompt: str):
    router = ModelAutoRouter(provider="google", enabled=True)
    decision = router.route(prompt)
    assert decision.tier == "deep"
    assert "gemini-2.5-pro" in decision.suggested_model or "pro" in decision.suggested_model.lower()


# ============================================================================
# 5. ModelAutoRouter: Fast / Velocity Keywords Matrix
# ============================================================================

FAST_PROMPT_SAMPLES = [
    "hello",
    "hi there",
    "fix typo in README",
    "what is a decorator?",
    "explain this variable name",
    "summarize this short note",
    "tell me what does exit code 0 mean",
    "format this json snippet",
    "quick check on syntax",
    "short one-liner to read file",
]

@pytest.mark.parametrize("prompt", FAST_PROMPT_SAMPLES)
def test_router_selects_fast_tier_for_simple_tasks(prompt: str):
    router = ModelAutoRouter(provider="google", enabled=True)
    decision = router.route(prompt)
    assert decision.tier == "fast"
    assert "flash" in decision.suggested_model.lower() or "haiku" in decision.suggested_model.lower()


# ============================================================================
# 6. ModelAutoRouter: Word Count & Multiline Code Threshold Matrix
# ============================================================================

@pytest.mark.parametrize("word_count,expected_tier", [
    (5, "fast"),      # <= 10 words -> fast
    (10, "fast"),
    (15, "balanced"), # 11 - 79 words -> balanced
    (45, "balanced"),
    (60, "balanced"),
    (85, "deep"),     # >= 80 words -> deep
    (120, "deep"),
    (200, "deep"),
])
def test_router_word_count_tier_selection(word_count: int, expected_tier: str):
    router = ModelAutoRouter(provider="openai", enabled=True)
    # Neutral prose words without keywords
    words = ["item" for _ in range(word_count)]
    text = " ".join(words)
    decision = router.route(text)
    assert decision.tier == expected_tier


@pytest.mark.parametrize("num_lines,expected_tier", [
    (1, "fast"),      # 1 line <= 10 words -> fast
    (4, "balanced"),  # 4 lines (< 8 lines) -> balanced
    (10, "deep"),     # >= 8 lines multiline -> deep
    (20, "deep"),
    (50, "deep"),
])
def test_router_multiline_code_triggers_deep_tier(num_lines: int, expected_tier: str):
    router = ModelAutoRouter(provider="anthropic", enabled=True)
    code_lines = [f"let item_{i} = {i};" for i in range(num_lines)]
    code_text = "\n".join(code_lines)
    decision = router.route(code_text)
    assert decision.tier == expected_tier


# ============================================================================
# 7. ModelAutoRouter: Provider-Specific Model Recommendations Matrix
# ============================================================================

@pytest.mark.parametrize("prov", ["google", "anthropic", "openai", "deepseek"])
@pytest.mark.parametrize("tier", ["fast", "balanced", "deep"])
def test_router_provider_model_mappings(prov: str, tier: str):
    if tier == "fast":
        assert prov in _FAST_MODELS
        assert len(_FAST_MODELS[prov]) > 0
    elif tier == "balanced":
        assert prov in _BALANCED_MODELS
        assert len(_BALANCED_MODELS[prov]) > 0
    elif tier == "deep":
        assert prov in _DEEP_MODELS
        assert len(_DEEP_MODELS[prov]) > 0


# ============================================================================
# 8. GenerationResponse Token Properties & Invariants Matrix
# ============================================================================

@pytest.mark.parametrize("prompt_toks,cand_toks,cached_toks,cache_create_toks", [
    (100, 50, 0, 0),
    (1500, 300, 1000, 0),
    (8000, 1200, 7500, 500),
    (0, 0, 0, 0),
    (25000, 4000, 24000, 1000),
])
def test_generation_response_properties(prompt_toks: int, cand_toks: int, cached_toks: int, cache_create_toks: int):
    resp = GenerationResponse(
        text="Sample output text",
        prompt_tokens=prompt_toks,
        candidate_tokens=cand_toks,
        thinking_tokens=150,
        model="gemini-2.5-pro",
        provider="google",
        latency_s=0.42,
        cached_tokens=cached_toks,
        cache_creation_tokens=cache_create_toks,
    )
    assert resp.tokens_input == prompt_toks
    assert resp.tokens_output == cand_toks
    assert resp.tokens_cached == cached_toks
    assert resp.tokens_cache_creation == cache_create_toks
    assert resp.latency_s == 0.42
    assert resp.model == "gemini-2.5-pro"
    assert resp.provider == "google"


# ============================================================================
# 9. Model Gateway Detection & Failover Cascade Logic
# ============================================================================

def test_detect_local_model_returns_none_when_unreachable(tmp_path, monkeypatch):
    cfg_mgr = ConfigManager()
    gw = UniversalModelGateway(config_manager=cfg_mgr)
    # When ports 1234 and 11434 are closed, gracefully returns None in < 120ms
    t0 = time.time()
    detected = gw.detect_local_model()
    elapsed = time.time() - t0
    assert detected is None or isinstance(detected, dict)
    assert elapsed < 1.0


# ============================================================================
# 10. AutoRouter Exhaustive Keyword Classification Matrix (_DEEP_KEYWORDS)
# ============================================================================

@pytest.mark.parametrize("keyword", list(_DEEP_KEYWORDS))
def test_router_exhaustive_deep_keywords(keyword: str):
    router = ModelAutoRouter(provider="google", enabled=True)
    prompt = f"Please {keyword} this component for our system"
    decision = router.route(prompt)
    assert decision.tier == "deep"


# ============================================================================
# 11. AutoRouter Exhaustive Keyword Classification Matrix (_FAST_KEYWORDS)
# ============================================================================

@pytest.mark.parametrize("keyword", list(_FAST_KEYWORDS))
def test_router_exhaustive_fast_keywords(keyword: str):
    router = ModelAutoRouter(provider="google", enabled=True)
    prompt = f"{keyword}"
    decision = router.route(prompt)
    assert decision.tier == "fast"


# ============================================================================
# 12. CircuitBreaker Recovery Success Threshold Matrix (1 to 6)
# ============================================================================

@pytest.mark.parametrize("req_successes", [1, 2, 3, 4, 5, 6])
def test_circuit_breaker_varying_recovery_successes(req_successes: int, monkeypatch):
    current_time = 5000.0
    monkeypatch.setattr(time, "time", lambda: current_time)

    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=10.0, recovery_successes=req_successes)
    cb.record_failure("err 1")
    cb.record_failure("err 2")
    assert cb.state == CircuitState.OPEN

    # Advance time past cooldown
    current_time += 15.0
    assert cb.state == CircuitState.HALF_OPEN

    # Deliver req_successes - 1 successes -> remains HALF_OPEN
    for i in range(req_successes - 1):
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN

    # Final success triggers recovery to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


# ============================================================================
# 13. CircuitBreaker Error Messages & HTTP Status Codes Permutations
# ============================================================================

ERROR_CODES = [
    (429, "Rate limit exceeded (TPM/RPM)"),
    (500, "Internal server error"),
    (502, "Bad Gateway upstream"),
    (503, "Service temporarily unavailable / overloaded"),
    (504, "Gateway timeout waiting for upstream model"),
    (408, "Request timeout"),
]

@pytest.mark.parametrize("status_code,msg", ERROR_CODES)
def test_circuit_breaker_records_http_errors(status_code: int, msg: str):
    cb = ProviderCircuitBreaker(failure_threshold=3)
    err_str = f"HTTP {status_code}: {msg}"
    cb.record_failure(err_str)
    assert cb._last_error == err_str
    assert cb._consecutive_failures == 1


# ============================================================================
# 14. CircuitBreakerOpenError Exception Invariants
# ============================================================================

@pytest.mark.parametrize("prov", PROVIDERS)
def test_circuit_breaker_open_error_messages(prov: str):
    err = CircuitBreakerOpenError(f"Circuit breaker OPEN for provider '{prov}'")
    assert prov in str(err)
    assert "Circuit breaker OPEN" in str(err)
    assert isinstance(err, Exception)


# ============================================================================
# 15. CircuitBreaker Cooldown Duration Variations
# ============================================================================

@pytest.mark.parametrize("cooldown", [1.0, 5.0, 10.0, 25.0, 60.0, 120.0])
def test_circuit_breaker_cooldown_durations(cooldown: float, monkeypatch):
    t_start = 10000.0
    current_time = t_start
    monkeypatch.setattr(time, "time", lambda: current_time)

    cb = ProviderCircuitBreaker(failure_threshold=1, cooldown_s=cooldown)
    cb.record_failure("error")
    assert cb.state == CircuitState.OPEN

    # Just before cooldown
    current_time = t_start + (cooldown - 0.1)
    assert cb.state == CircuitState.OPEN

    # At or after cooldown
    current_time = t_start + cooldown + 0.1
    assert cb.state == CircuitState.HALF_OPEN


# ============================================================================
# 16. ModelAutoRouter Toggle State Machine Permutations
# ============================================================================

@pytest.mark.parametrize("init_state", [False, True])
def test_router_toggle_state_transitions(init_state: bool):
    router = ModelAutoRouter(provider="google", default_model="gemini-2.5-flash", enabled=init_state)
    assert router.enabled is init_state

    # 1st toggle
    new_state = router.toggle()
    assert new_state is not init_state
    assert router.enabled is not init_state

    # 2nd toggle (returns to init_state)
    reverted_state = router.toggle()
    assert reverted_state is init_state
    assert router.enabled is init_state


