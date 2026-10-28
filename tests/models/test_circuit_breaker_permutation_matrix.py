"""PRUBETH Circuit Breaker State Machine — Exhaustive Permutation Matrix Tests.

Verifies the ProviderCircuitBreaker and GlobalCircuitRegistry across all state
transitions: CLOSED → OPEN → HALF_OPEN → CLOSED recovery cycles, canary failure
re-tripping, threshold boundaries, and independent per-provider isolation.
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import patch

from prubeth.models.circuit_breaker import (
    ProviderCircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    GlobalCircuitRegistry,
)

PROVIDERS = ["google", "anthropic", "openai", "openrouter", "deepseek", "groq", "ollama", "lm_studio"]


# ============================================================================
# 1. Initial State
# ============================================================================

def test_circuit_breaker_initial_state_is_closed():
    cb = ProviderCircuitBreaker()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


# ============================================================================
# 2. CLOSED → OPEN: failure threshold trip
# ============================================================================

@pytest.mark.parametrize("threshold", [1, 2, 3, 4, 5, 10])
def test_circuit_trips_open_at_threshold(threshold: int):
    cb = ProviderCircuitBreaker(failure_threshold=threshold)
    for i in range(threshold - 1):
        cb.record_failure(f"error_{i}")
        assert cb.state == CircuitState.CLOSED, f"Should still be CLOSED after {i+1} failures"
    cb.record_failure("final_error")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


# ============================================================================
# 3. OPEN → HALF_OPEN: cooldown elapsed
# ============================================================================

def test_circuit_transitions_to_half_open_after_cooldown():
    cb = ProviderCircuitBreaker(failure_threshold=1, cooldown_s=0.05)
    cb.record_failure("trigger")
    assert cb.state == CircuitState.OPEN

    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.can_execute() is True


# ============================================================================
# 4. HALF_OPEN → CLOSED: successful recovery
# ============================================================================

def test_circuit_recovers_from_half_open_after_required_successes():
    cb = ProviderCircuitBreaker(failure_threshold=1, cooldown_s=0.01, recovery_successes=2)
    cb.record_failure("trigger")
    time.sleep(0.02)
    # Now in HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN  # One success, need 2

    cb.record_success()
    assert cb.state == CircuitState.CLOSED


# ============================================================================
# 5. HALF_OPEN → OPEN: canary request fails
# ============================================================================

def test_canary_failure_re_trips_circuit_to_open():
    cb = ProviderCircuitBreaker(failure_threshold=1, cooldown_s=0.01, recovery_successes=2)
    cb.record_failure("initial_trigger")
    time.sleep(0.02)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure("canary_failed")
    assert cb.state == CircuitState.OPEN


# ============================================================================
# 6. Manual reset
# ============================================================================

def test_manual_reset_returns_to_closed():
    cb = ProviderCircuitBreaker(failure_threshold=1)
    cb.record_failure("trigger")
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


# ============================================================================
# 7. Success in CLOSED resets failure counter
# ============================================================================

def test_success_in_closed_resets_failure_streak():
    cb = ProviderCircuitBreaker(failure_threshold=4)
    cb.record_failure("e1")
    cb.record_failure("e2")
    cb.record_failure("e3")
    assert cb.state == CircuitState.CLOSED  # 3 < 4

    cb.record_success()  # Should reset counter
    cb.record_failure("e_after_reset")
    assert cb.state == CircuitState.CLOSED  # Only 1 failure after reset


# ============================================================================
# 8. GlobalCircuitRegistry per-provider isolation
# ============================================================================

@pytest.mark.parametrize("provider_a,provider_b", [
    ("google", "anthropic"),
    ("openai", "ollama"),
    ("groq", "deepseek"),
    ("lm_studio", "openrouter"),
])
def test_circuit_registry_providers_are_isolated(provider_a: str, provider_b: str):
    """Tripping one provider's circuit must not affect any other provider."""
    GlobalCircuitRegistry.reset_all()
    cb_a = GlobalCircuitRegistry.get_breaker(provider_a)
    cb_b = GlobalCircuitRegistry.get_breaker(provider_b)

    # Trip provider_a to OPEN
    for _ in range(4):
        cb_a.record_failure("error")

    assert cb_a.state == CircuitState.OPEN
    assert cb_b.state == CircuitState.CLOSED  # provider_b unaffected


# ============================================================================
# 9. Singleton registry returns same instance always
# ============================================================================

def test_circuit_registry_singleton():
    inst_1 = GlobalCircuitRegistry.get_instance()
    inst_2 = GlobalCircuitRegistry.get_instance()
    assert inst_1 is inst_2


# ============================================================================
# 10. All PRUBETH providers are independently trackable in registry
# ============================================================================

@pytest.mark.parametrize("provider", PROVIDERS)
def test_circuit_registry_tracks_all_providers(provider: str):
    GlobalCircuitRegistry.reset_all()
    breaker = GlobalCircuitRegistry.get_breaker(provider)
    assert breaker is not None
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True


# ============================================================================
# 11. CircuitState string values
# ============================================================================

def test_circuit_state_string_values():
    assert CircuitState.CLOSED == "CLOSED"
    assert CircuitState.OPEN == "OPEN"
    assert CircuitState.HALF_OPEN == "HALF_OPEN"


# ============================================================================
# 12. Record failure stores last error message
# ============================================================================

def test_circuit_records_last_error_message():
    cb = ProviderCircuitBreaker(failure_threshold=10)
    cb.record_failure("ConnectionTimeout: upstream refused connection")
    assert "ConnectionTimeout" in cb._last_error


# ============================================================================
# 13. High-volume failure recording stress test
# ============================================================================

def test_circuit_high_volume_failure_recording():
    cb = ProviderCircuitBreaker(failure_threshold=100)
    for i in range(99):
        cb.record_failure(f"error_{i}")
    assert cb.state == CircuitState.CLOSED
    cb.record_failure("final")
    assert cb.state == CircuitState.OPEN
