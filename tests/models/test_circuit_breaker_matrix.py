"""PRUBETH Circuit Breaker & Global Registry State Machine Matrix Tests.

Exhaustively verifies Subsystem 12: ProviderCircuitBreaker state transitions
(CLOSED -> OPEN -> HALF_OPEN -> CLOSED), failure accumulation thresholds,
cooldown time auto-transitions, canary recovery, GlobalCircuitRegistry singleton
isolation, and multi-endpoint independence.
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import patch

from prubeth.models.circuit_breaker import (
    CircuitState,
    CircuitBreakerOpenError,
    ProviderCircuitBreaker,
    GlobalCircuitRegistry,
)


# ============================================================================
# 1. Initial State Invariants
# ============================================================================

def test_circuit_breaker_initial_state_is_closed():
    cb = ProviderCircuitBreaker()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_initial_failure_count_zero():
    cb = ProviderCircuitBreaker()
    assert cb._consecutive_failures == 0
    assert cb._consecutive_successes == 0
    assert cb._last_error == ""


def test_circuit_breaker_custom_thresholds():
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=10.0, recovery_successes=1)
    assert cb.failure_threshold == 2
    assert cb.cooldown_s == 10.0
    assert cb.recovery_successes == 1


# ============================================================================
# 2. CLOSED -> OPEN Transition (Failure Accumulation)
# ============================================================================

def test_single_failure_stays_closed():
    cb = ProviderCircuitBreaker(failure_threshold=4)
    cb.record_failure("timeout")
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_three_failures_below_threshold_stay_closed():
    cb = ProviderCircuitBreaker(failure_threshold=4)
    for _ in range(3):
        cb.record_failure("503 Service Unavailable")
    assert cb.state == CircuitState.CLOSED


def test_four_failures_trip_to_open():
    cb = ProviderCircuitBreaker(failure_threshold=4)
    for i in range(4):
        cb.record_failure(f"error_{i}")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_open_circuit_blocks_execution():
    cb = ProviderCircuitBreaker(failure_threshold=2)
    cb.record_failure("err")
    cb.record_failure("err")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_error_message_stored_on_failure():
    cb = ProviderCircuitBreaker(failure_threshold=3)
    cb.record_failure("HTTP 429 Rate Limited")
    assert "429" in cb._last_error


# ============================================================================
# 3. OPEN -> HALF_OPEN Transition (Cooldown Elapsed)
# ============================================================================

def test_open_transitions_to_half_open_after_cooldown():
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=0.05)
    cb.record_failure("err1")
    cb.record_failure("err2")
    assert cb.state == CircuitState.OPEN

    time.sleep(0.07)
    # Accessing .state triggers the auto-transition
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.can_execute() is True


def test_open_stays_open_before_cooldown():
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=60.0)
    cb.record_failure("err1")
    cb.record_failure("err2")
    assert cb.state == CircuitState.OPEN
    # No sleep — cooldown not elapsed
    assert cb.state == CircuitState.OPEN


# ============================================================================
# 4. HALF_OPEN Canary Recovery (HALF_OPEN -> CLOSED)
# ============================================================================

def test_half_open_successful_canary_recovers_to_closed():
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=0.05, recovery_successes=2)
    cb.record_failure("err")
    cb.record_failure("err")
    time.sleep(0.07)
    assert cb.state == CircuitState.HALF_OPEN

    # Two successes needed to fully recover
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN  # Not yet
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_half_open_failed_canary_re_trips_to_open():
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_s=0.05, recovery_successes=2)
    cb.record_failure("err")
    cb.record_failure("err")
    time.sleep(0.07)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure("canary failed")
    assert cb.state == CircuitState.OPEN


# ============================================================================
# 5. Manual Reset
# ============================================================================

def test_manual_reset_from_open_to_closed():
    cb = ProviderCircuitBreaker(failure_threshold=2)
    cb.record_failure("err")
    cb.record_failure("err")
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb._consecutive_failures == 0
    assert cb._last_error == ""
    assert cb.can_execute() is True


def test_manual_reset_clears_error_message():
    cb = ProviderCircuitBreaker(failure_threshold=1)
    cb.record_failure("FATAL_CONNECTION_RESET")
    cb.reset()
    assert cb._last_error == ""


# ============================================================================
# 6. Success Resets Failure Counter in CLOSED State
# ============================================================================

def test_success_in_closed_resets_failure_counter():
    cb = ProviderCircuitBreaker(failure_threshold=4)
    cb.record_failure("err1")
    cb.record_failure("err2")
    assert cb._consecutive_failures == 2

    cb.record_success()
    assert cb._consecutive_failures == 0
    assert cb.state == CircuitState.CLOSED


# ============================================================================
# 7. GlobalCircuitRegistry — Singleton & Multi-Endpoint Isolation
# ============================================================================

def test_registry_singleton_returns_same_instance():
    GlobalCircuitRegistry.reset_all()
    inst1 = GlobalCircuitRegistry.get_instance()
    inst2 = GlobalCircuitRegistry.get_instance()
    assert inst1 is inst2


def test_registry_creates_breaker_for_new_provider():
    GlobalCircuitRegistry.reset_all()
    breaker = GlobalCircuitRegistry.get_breaker("ollama")
    assert isinstance(breaker, ProviderCircuitBreaker)
    assert breaker.state == CircuitState.CLOSED


def test_registry_returns_same_breaker_for_same_provider():
    GlobalCircuitRegistry.reset_all()
    b1 = GlobalCircuitRegistry.get_breaker("gemini")
    b2 = GlobalCircuitRegistry.get_breaker("gemini")
    assert b1 is b2


def test_registry_isolates_different_providers():
    GlobalCircuitRegistry.reset_all()
    b_ollama = GlobalCircuitRegistry.get_breaker("ollama")
    b_openai = GlobalCircuitRegistry.get_breaker("openai")

    # Trip ollama only
    for _ in range(4):
        b_ollama.record_failure("err")
    assert b_ollama.state == CircuitState.OPEN
    assert b_openai.state == CircuitState.CLOSED


def test_registry_reset_all_recovers_all_endpoints():
    GlobalCircuitRegistry.reset_all()
    b1 = GlobalCircuitRegistry.get_breaker("groq")
    b2 = GlobalCircuitRegistry.get_breaker("lm_studio")

    for _ in range(4):
        b1.record_failure("err")
        b2.record_failure("err")

    GlobalCircuitRegistry.reset_all()
    assert b1.state == CircuitState.CLOSED
    assert b2.state == CircuitState.CLOSED


def test_registry_provider_key_normalised_lowercase():
    GlobalCircuitRegistry.reset_all()
    b1 = GlobalCircuitRegistry.get_breaker("ANTHROPIC")
    b2 = GlobalCircuitRegistry.get_breaker("anthropic")
    assert b1 is b2


def test_registry_five_providers_independently_managed():
    GlobalCircuitRegistry.reset_all()
    providers = ["ollama", "openai", "anthropic", "groq", "deepseek"]
    breakers = [GlobalCircuitRegistry.get_breaker(p) for p in providers]
    # Trip only ollama
    for _ in range(4):
        breakers[0].record_failure("err")

    assert breakers[0].state == CircuitState.OPEN
    for b in breakers[1:]:
        assert b.state == CircuitState.CLOSED
