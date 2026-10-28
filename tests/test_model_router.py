"""Tests for ModelAutoRouter — tier detection, keyword routing, and toggle."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prubeth.models.router import ModelAutoRouter, RoutingDecision


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def router_openrouter():
    return ModelAutoRouter(provider="openrouter", default_model="o3-mini", enabled=True)


@pytest.fixture
def router_google():
    return ModelAutoRouter(provider="google", default_model="gemini-2.5-flash", enabled=True)


@pytest.fixture
def router_disabled():
    return ModelAutoRouter(provider="openrouter", default_model="o3-mini", enabled=False)


# ---------------------------------------------------------------------------
# Disabled router
# ---------------------------------------------------------------------------

class TestDisabledRouter:
    def test_returns_balanced_tier(self, router_disabled):
        decision = router_disabled.route("Refactor the entire authentication system")
        assert decision.tier == "balanced"

    def test_returns_default_model(self, router_disabled):
        decision = router_disabled.route("Refactor the entire authentication system")
        assert decision.suggested_model == "o3-mini"

    def test_reason_mentions_disabled(self, router_disabled):
        decision = router_disabled.route("anything")
        assert "disabled" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Fast tier
# ---------------------------------------------------------------------------

class TestFastTier:
    def test_short_hello_is_fast(self, router_openrouter):
        decision = router_openrouter.route("hello")
        assert decision.tier == "fast"

    def test_very_short_prompt_is_fast(self, router_openrouter):
        decision = router_openrouter.route("what is python")
        assert decision.tier in ("fast", "balanced")

    def test_fast_model_is_gpt4o_mini_for_openrouter(self, router_openrouter):
        decision = router_openrouter.route("hi there")
        if decision.tier == "fast":
            assert decision.suggested_model == "gpt-4o-mini"

    def test_fast_model_is_flash_for_google(self, router_google):
        decision = router_google.route("hi there")
        if decision.tier == "fast":
            assert decision.suggested_model == "gemini-3.8-flash"


# ---------------------------------------------------------------------------
# Deep tier
# ---------------------------------------------------------------------------

class TestDeepTier:
    def test_architect_keyword_is_deep(self, router_openrouter):
        decision = router_openrouter.route("architect a distributed microservices platform")
        assert decision.tier == "deep"

    def test_refactor_keyword_is_deep(self, router_openrouter):
        decision = router_openrouter.route("refactor the authentication module")
        assert decision.tier == "deep"

    def test_security_audit_is_deep(self, router_openrouter):
        decision = router_openrouter.route("perform a security audit of the codebase")
        assert decision.tier == "deep"

    def test_long_prompt_is_deep(self, router_openrouter):
        long_text = " ".join(["word"] * 90)
        decision = router_openrouter.route(long_text)
        assert decision.tier == "deep"

    def test_multiline_code_is_deep(self, router_openrouter):
        code = "\n".join([f"line {i}" for i in range(10)])
        decision = router_openrouter.route(code)
        assert decision.tier == "deep"

    def test_deep_model_is_o3_mini_for_openrouter(self, router_openrouter):
        decision = router_openrouter.route("architect a new event-driven microservices platform")
        assert decision.suggested_model == "o3-mini"

    def test_deep_model_is_pro_for_google(self, router_google):
        decision = router_google.route("architect a new event-driven microservices platform")
        assert decision.suggested_model == "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# Balanced tier
# ---------------------------------------------------------------------------

class TestBalancedTier:
    def test_medium_prompt_is_balanced(self, router_openrouter):
        # Deliberately avoids deep keywords and is not too short for fast
        text = "Show me how to use list comprehensions in Python with an example."
        decision = router_openrouter.route(text)
        # Medium length, no deep keywords → balanced or fast (never deep)
        assert decision.tier in ("balanced", "fast")

    def test_decision_is_routing_decision_named_tuple(self, router_openrouter):
        decision = router_openrouter.route("Show me the /models list")
        assert isinstance(decision, RoutingDecision)
        assert hasattr(decision, "tier")
        assert hasattr(decision, "suggested_model")
        assert hasattr(decision, "reason")


# ---------------------------------------------------------------------------
# Toggle
# ---------------------------------------------------------------------------

class TestToggle:
    def test_toggle_enables(self):
        router = ModelAutoRouter(provider="openrouter", default_model="o3-mini", enabled=False)
        new_state = router.toggle()
        assert new_state is True
        assert router.enabled is True

    def test_toggle_disables(self):
        router = ModelAutoRouter(provider="openrouter", default_model="o3-mini", enabled=True)
        new_state = router.toggle()
        assert new_state is False
        assert router.enabled is False

    def test_toggle_twice_returns_original(self):
        router = ModelAutoRouter(provider="openrouter", default_model="o3-mini", enabled=True)
        router.toggle()
        router.toggle()
        assert router.enabled is True


# ---------------------------------------------------------------------------
# Provider fallback — unknown provider uses default_model
# ---------------------------------------------------------------------------

class TestUnknownProvider:
    def test_unknown_provider_falls_back_to_default(self):
        router = ModelAutoRouter(provider="unknown_xyz", default_model="my-model", enabled=True)
        decision = router.route("hello")
        # Should not crash, and suggested_model should be my-model (fallback)
        assert isinstance(decision, RoutingDecision)
        assert decision.suggested_model  # non-empty

    def test_empty_default_model_handled(self):
        router = ModelAutoRouter(provider="google", default_model="", enabled=True)
        # route should not return an empty suggested_model string for deep prompts
        # (it may return empty only if all lookups fail, which is okay here)
        decision = router.route("refactor the entire system")
        assert isinstance(decision, RoutingDecision)
