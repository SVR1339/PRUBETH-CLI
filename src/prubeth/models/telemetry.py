"""PRUBETH LLMOps Telemetry, Monitoring & Provider Health Engine.

Manages multi-provider telemetry, latency monitoring (TTFT, completion latency),
token accounting, prompt caching statistics, and health failover matrices.
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ModelCallMetrics:
    model: str
    provider: str
    latency_s: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    success: bool
    cache_creation_tokens: int = 0
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class LLMOpsMonitor:
    """LLMOps: Real-time telemetry, model reliability tracking & failover analytics."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMOpsMonitor, cls).__new__(cls)
            cls._instance.metrics: List[ModelCallMetrics] = []
            cls._instance.provider_failure_counts: Dict[str, int] = {}
        return cls._instance

    def record_call(
        self,
        model: str,
        provider: str,
        latency_s: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        success: bool = True,
        cache_creation_tokens: int = 0,
        error_message: Optional[str] = None
    ):
        """Records an inference event for LLMOps observability."""
        metric = ModelCallMetrics(
            model=model,
            provider=provider,
            latency_s=latency_s,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            success=success,
            cache_creation_tokens=cache_creation_tokens,
            error_message=error_message
        )
        self.metrics.append(metric)
        if not success:
            self.provider_failure_counts[provider] = self.provider_failure_counts.get(provider, 0) + 1

    def get_provider_health(self, provider: str) -> Dict[str, Any]:
        """Calculates success rate, average latency, and cache efficiency for a provider."""
        calls = [m for m in self.metrics if m.provider == provider]
        if not calls:
            return {"provider": provider, "status": "UNKNOWN", "total_calls": 0, "success_rate": 1.0, "avg_latency_s": 0.0}

        successes = sum(1 for m in calls if m.success)
        total_latency = sum(m.latency_s for m in calls)
        total_input = sum(m.input_tokens for m in calls)
        total_cached = sum(m.cached_tokens for m in calls)

        success_rate = successes / len(calls)
        cache_rate = (total_cached / total_input) if total_input > 0 else 0.0

        status = "HEALTHY" if success_rate >= 0.9 else ("DEGRADED" if success_rate >= 0.5 else "CRITICAL")
        return {
            "provider": provider,
            "status": status,
            "total_calls": len(calls),
            "success_rate": round(success_rate, 3),
            "avg_latency_s": round(total_latency / len(calls), 3),
            "cache_efficiency": round(cache_rate, 3)
        }

    def reset(self):
        """Resets telemetry for test isolation."""
        self.metrics.clear()
        self.provider_failure_counts.clear()
