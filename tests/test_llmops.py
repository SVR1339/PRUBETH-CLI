import unittest
from prubeth.models.telemetry import LLMOpsMonitor

class TestLLMOps(unittest.TestCase):
    """LLMOps: Telemetry, Observability, and Provider Health Monitoring Verification."""

    def setUp(self):
        self.monitor = LLMOpsMonitor()
        self.monitor.reset()

    def test_record_call_and_provider_health(self):
        """LLMOps: Verify recording model calls and calculating health metrics."""
        self.monitor.record_call(
            model="gemini-3.5-flash",
            provider="google",
            latency_s=0.45,
            input_tokens=1000,
            output_tokens=200,
            cached_tokens=800,
            success=True
        )
        self.monitor.record_call(
            model="gemini-3.5-flash",
            provider="google",
            latency_s=0.55,
            input_tokens=1200,
            output_tokens=250,
            cached_tokens=900,
            success=True
        )

        health = self.monitor.get_provider_health("google")
        self.assertEqual(health["provider"], "google")
        self.assertEqual(health["status"], "HEALTHY")
        self.assertEqual(health["total_calls"], 2)
        self.assertEqual(health["success_rate"], 1.0)
        self.assertAlmostEqual(health["avg_latency_s"], 0.50, delta=0.01)
        self.assertGreater(health["cache_efficiency"], 0.70)

    def test_provider_degradation_detection(self):
        """LLMOps: Consecutive failures flag provider status as DEGRADED or CRITICAL."""
        self.monitor.record_call("gpt-4o", "openai", latency_s=1.2, success=False, error_message="Rate limit 429")
        self.monitor.record_call("gpt-4o", "openai", latency_s=1.5, success=False, error_message="Internal Server Error 500")

        health = self.monitor.get_provider_health("openai")
        self.assertEqual(health["status"], "CRITICAL")
        self.assertEqual(health["success_rate"], 0.0)

if __name__ == "__main__":
    unittest.main()
