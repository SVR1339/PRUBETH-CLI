"""Comprehensive Unit Tests for PRUBETH Cockpit HUD, Spend Calculations, and Telemetry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from prubeth.cli.hud import (
    MODEL_PRICING,
    calculate_session_spend,
    get_current_process_memory_mb,
    render_cockpit_hud_bar,
    render_cost_report,
)
from prubeth.models.telemetry import ModelCallMetrics


def test_model_pricing_catalog_invariants():
    """Validates that all registered models have non-negative input, output, and cache rates."""
    assert len(MODEL_PRICING) >= 20
    for model_name, rates in MODEL_PRICING.items():
        assert "input" in rates
        assert "output" in rates
        assert "cache_read" in rates
        assert rates["input"] >= 0.0
        assert rates["output"] >= 0.0
        assert rates["cache_read"] >= 0.0
        # Cache read rate should always be strictly <= input rate
        assert rates["cache_read"] <= rates["input"]


def test_calculate_session_spend_empty():
    """Validates session spend calculation when no LLM calls have occurred."""
    with patch("prubeth.cli.hud.LLMOpsMonitor") as MockMonitor:
        MockMonitor.return_value.metrics = []
        spend = calculate_session_spend()
        assert spend["total_calls"] == 0
        assert spend["total_tokens"] == 0
        assert spend["input_tokens"] == 0
        assert spend["output_tokens"] == 0
        assert spend["cached_tokens"] == 0
        assert spend["total_cost_usd"] == 0.0
        assert spend["total_saved_usd"] == 0.0
        assert spend["by_model"] == {}


def test_calculate_session_spend_single_call():
    """Validates accurate spend and savings calculation for a single cached API call."""
    metric = ModelCallMetrics(
        model="gemini-2.5-pro",
        provider="google",
        input_tokens=100_000,
        output_tokens=2_000,
        cached_tokens=80_000,
        latency_s=1.2,
        success=True,
    )
    with patch("prubeth.cli.hud.LLMOpsMonitor") as MockMonitor:
        MockMonitor.return_value.metrics = [metric]
        spend = calculate_session_spend()

        assert spend["total_calls"] == 1
        assert spend["total_tokens"] == 102_000
        assert spend["input_tokens"] == 100_000
        assert spend["output_tokens"] == 2_000
        assert spend["cached_tokens"] == 80_000
        assert spend["total_cost_usd"] > 0.0
        assert spend["total_saved_usd"] > 0.0
        assert "gemini-2.5-pro" in spend["by_model"]
        assert spend["by_model"]["gemini-2.5-pro"]["calls"] == 1


def test_calculate_session_spend_free_model():
    """Validates that local and free models incur strictly $0.00 spend."""
    metric = ModelCallMetrics(
        model="ollama",
        provider="ollama",
        input_tokens=50_000,
        output_tokens=5_000,
        cached_tokens=20_000,
        latency_s=2.5,
        success=True,
    )
    with patch("prubeth.cli.hud.LLMOpsMonitor") as MockMonitor:
        MockMonitor.return_value.metrics = [metric]
        spend = calculate_session_spend()

        assert spend["total_cost_usd"] == 0.0
        assert spend["total_saved_usd"] == 0.0
        assert spend["by_model"]["ollama"]["cost"] == 0.0


def test_calculate_session_spend_fallback_unknown_model():
    """Validates fallback pricing when an uncatalogued model is passed."""
    metric = ModelCallMetrics(
        model="custom-future-model-v99",
        provider="openai_compatible",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cached_tokens=0,
        latency_s=1.0,
        success=True,
    )
    with patch("prubeth.cli.hud.LLMOpsMonitor") as MockMonitor:
        MockMonitor.return_value.metrics = [metric]
        spend = calculate_session_spend()
        assert spend["total_cost_usd"] == 4.0  # 1.0 input + 3.0 output default


def test_get_current_process_memory_mb():
    """Validates memory inspection returns a positive float."""
    ram = get_current_process_memory_mb()
    assert isinstance(ram, float)
    assert ram > 0.0


def test_render_cockpit_hud_bar():
    """Validates HUD bar rendering without raising exceptions."""
    mock_console = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.resolve_model_and_provider.return_value = {"model": "gemini-2.5-pro", "provider": "google"}
    mock_cfg.get_active_profile_info.return_value = {"name": "BUILDER (Active)"}

    with patch("prubeth.cli.hud.SnapshotManager") as MockSnap:
        MockSnap.return_value.list_snapshots.return_value = ["snap-abc12345"]
        render_cockpit_hud_bar(mock_console, mock_cfg, current_model="gemini-2.5-pro")
        assert mock_console.print.called
        output_str = str(mock_console.print.call_args[0][0])
        assert "BUILDER" in output_str
        assert "gemini-2.5-pro" in output_str
        assert "RAM:" in output_str


def test_render_cost_report_empty_and_populated():
    """Validates detailed cost report rendering with empty and populated telemetry."""
    mock_console = MagicMock()
    with patch("prubeth.cli.hud.calculate_session_spend") as MockSpend:
        # Empty
        MockSpend.return_value = {
            "total_calls": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "total_cost_usd": 0.0,
            "total_saved_usd": 0.0,
            "by_model": {},
        }
        render_cost_report(mock_console)
        assert mock_console.print.called

        # Populated
        MockSpend.return_value = {
            "total_calls": 2,
            "total_tokens": 15000,
            "input_tokens": 10000,
            "output_tokens": 5000,
            "cached_tokens": 4000,
            "total_cost_usd": 0.025,
            "total_saved_usd": 0.005,
            "by_model": {
                "claude-3-7-sonnet": {
                    "provider": "anthropic",
                    "calls": 2,
                    "input": 10000,
                    "cached": 4000,
                    "output": 5000,
                    "cost": 0.025,
                    "saved": 0.005,
                }
            },
        }
        render_cost_report(mock_console)
        assert mock_console.print.call_count >= 2
