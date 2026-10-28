"""PRUBETH Precision Circuit Breaker & Endpoint Health State Machine.

Protects against hung network connections, server outages (502/503), and rate limit lockouts
by automatically tripping failed provider endpoints and cleanly routing to local/backup inference.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Dict, Any, Optional


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operations: requests flow through
    OPEN = "OPEN"            # Tripped: requests fail fast to trigger backup models
    HALF_OPEN = "HALF_OPEN"  # Testing: single canary request allowed


class CircuitBreakerOpenError(Exception):
    """Raised when an inference call is attempted on an open circuit."""
    pass


class ProviderCircuitBreaker:
    """Per-endpoint circuit breaker state machine."""

    def __init__(
        self,
        failure_threshold: int = 4,
        cooldown_s: float = 25.0,
        recovery_successes: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self.recovery_successes = recovery_successes

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_state_change = time.time()
        self._last_error = ""

    @property
    def state(self) -> CircuitState:
        """Computes current state with automatic transition from OPEN to HALF_OPEN after cooldown."""
        if self._state == CircuitState.OPEN:
            if (time.time() - self._last_state_change) >= self.cooldown_s:
                self._state = CircuitState.HALF_OPEN
                self._consecutive_successes = 0
                self._last_state_change = time.time()
        return self._state

    def can_execute(self) -> bool:
        """Determines whether a request to this provider is permitted."""
        st = self.state
        return st in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Records a successful request completion."""
        st = self.state
        if st == CircuitState.HALF_OPEN:
            self._consecutive_successes += 1
            if self._consecutive_successes >= self.recovery_successes:
                self._state = CircuitState.CLOSED
                self._consecutive_failures = 0
                self._last_state_change = time.time()
        else:
            self._consecutive_failures = 0

    def record_failure(self, error_message: str = "") -> None:
        """Records a failed request (e.g. timeout, 503, 500, or 429)."""
        self._last_error = error_message
        self._consecutive_failures += 1
        st = self.state

        if st == CircuitState.HALF_OPEN:
            # Canary failed -> trip back to OPEN immediately
            self._state = CircuitState.OPEN
            self._last_state_change = time.time()
        elif st == CircuitState.CLOSED:
            if self._consecutive_failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._last_state_change = time.time()

    def reset(self) -> None:
        """Manually resets the circuit breaker to CLOSED."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_state_change = time.time()
        self._last_error = ""


class GlobalCircuitRegistry:
    """Maintains independent circuit breakers for all registered providers and endpoints."""

    _instance: Optional[GlobalCircuitRegistry] = None

    def __init__(self):
        self._breakers: Dict[str, ProviderCircuitBreaker] = {}

    @classmethod
    def get_instance(cls) -> GlobalCircuitRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def get_breaker(cls, provider_id: str) -> ProviderCircuitBreaker:
        inst = cls.get_instance()
        key = provider_id.lower().strip()
        if key not in inst._breakers:
            inst._breakers[key] = ProviderCircuitBreaker()
        return inst._breakers[key]

    @classmethod
    def reset_all(cls) -> None:
        inst = cls.get_instance()
        for b in inst._breakers.values():
            b.reset()
