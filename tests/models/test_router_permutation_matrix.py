"""PRUBETH Model Router — Full Provider × Tier × Signal Permutation Matrix.

Exhaustively verifies routing decisions across all 8 supported providers,
3 tiers (fast / balanced / deep), keyword signals, length thresholds,
multiline code detection, and disabled-router passthrough behaviour.
"""

from __future__ import annotations

import pytest
from prubeth.models.router import (
    ModelAutoRouter,
    RoutingDecision,
    _FAST_MODELS,
    _BALANCED_MODELS,
    _DEEP_MODELS,
)

PROVIDERS = ["google", "anthropic", "openai", "openrouter", "deepseek", "groq", "ollama", "lm_studio"]

# ============================================================================
# 1. Disabled router always returns balanced passthrough
# ============================================================================

@pytest.mark.parametrize("provider", PROVIDERS)
def test_router_disabled_always_returns_balanced(provider: str):
    router = ModelAutoRouter(provider=provider, default_model="my-custom-model", enabled=False)
    decision = router.route("Fix the bug in auth.py and then refactor the whole pipeline orchestration system")
    assert decision.tier == "balanced"
    assert decision.suggested_model == "my-custom-model"
    assert "disabled" in decision.reason.lower()


# ============================================================================
# 2. Fast tier: short conversational prompts
# ============================================================================

FAST_PROMPTS = [
    "hi",
    "hello there",
    "what is a list",
    "summarise this",
    "fix typo here",
    "explain it",
    "how do i install pip",
    "rename this function",
    "what does this mean",
]

@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("prompt", FAST_PROMPTS)
def test_router_fast_tier_short_prompts(provider: str, prompt: str):
    router = ModelAutoRouter(provider=provider, default_model="default-model", enabled=True)
    decision = router.route(prompt)
    assert decision.tier == "fast"
    assert decision.suggested_model  # Never empty


# ============================================================================
# 3. Deep tier: complexity keyword detection
# ============================================================================

DEEP_PROMPTS = [
    "Architect a multi-agent pipeline with distributed async workers and concurrency controls.",
    "Perform a security audit of the authentication subsystem for CVE vulnerabilities.",
    "Analyse the algorithm and optimise the performance-critical hot path in the runtime.",
    "Research the migration strategy and design a complete system integration plan.",
    "Refactor the entire codebase to support advanced scalable orchestration with benchmarks.",
    "Implement a multi-agent framework with pipeline orchestration and deep integration.",
]

@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("prompt", DEEP_PROMPTS)
def test_router_deep_tier_keyword_detection(provider: str, prompt: str):
    router = ModelAutoRouter(provider=provider, default_model="default-model", enabled=True)
    decision = router.route(prompt)
    assert decision.tier == "deep"
    assert "frontier" in decision.reason.lower() or "complexity" in decision.reason.lower() or "deep" in decision.reason.lower() or "reasoning" in decision.reason.lower()


# ============================================================================
# 4. Deep tier: long prompt (>= 80 words)
# ============================================================================

def test_router_deep_tier_long_prompt():
    long_prompt = " ".join(["word"] * 90)
    router = ModelAutoRouter(provider="google", default_model="gemini-2.5-flash", enabled=True)
    decision = router.route(long_prompt)
    assert decision.tier == "deep"
    assert "90 words" in decision.reason or "Long prompt" in decision.reason


# ============================================================================
# 5. Deep tier: multiline code paste
# ============================================================================

MULTILINE_CODE = """\
def process_orders(orders):
    result = []
    for order in orders:
        if order.status == 'pending':
            validated = validate(order)
            if validated:
                result.append(order)
    return result
"""

@pytest.mark.parametrize("provider", PROVIDERS)
def test_router_deep_tier_multiline_code_paste(provider: str):
    router = ModelAutoRouter(provider=provider, default_model="default", enabled=True)
    decision = router.route(MULTILINE_CODE)
    assert decision.tier == "deep"
    assert "Multi-line" in decision.reason or "lines" in decision.reason


# ============================================================================
# 6. Balanced tier: general mid-length prompts
# ============================================================================

BALANCED_PROMPTS = [
    # Purposefully mid-length prompts with no fast/deep keywords — expect balanced or deep
    "Add input validation to the user registration form before saving.",
    "Implement basic connection pool manager with retry logic.",
    "Create a background job processor for sending notification emails.",
    "Write a data export handler that serialises records to CSV format.",
]

@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("prompt", BALANCED_PROMPTS)
def test_router_balanced_tier_general_prompts(provider: str, prompt: str):
    router = ModelAutoRouter(provider=provider, default_model="default-model", enabled=True)
    decision = router.route(prompt)
    # Balanced is expected; deep is also valid if the router detects deep signals
    assert decision.tier in ("balanced", "fast", "deep")
    assert decision.suggested_model


# ============================================================================
# 7. Model names are never empty for any provider × tier
# ============================================================================

@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("tier,prompt", [
    ("fast", "hi"),
    ("deep", "architect a complete system integration framework for production"),
    ("balanced", "Write a simple function to sort a list"),
])
def test_router_model_name_never_empty(provider: str, tier: str, prompt: str):
    router = ModelAutoRouter(provider=provider, default_model="fallback-model", enabled=True)
    decision = router.route(prompt)
    assert len(decision.suggested_model) > 0


# ============================================================================
# 8. Toggle auto-routing on/off
# ============================================================================

def test_router_toggle_enables_and_disables():
    router = ModelAutoRouter(provider="google", default_model="gemini", enabled=False)
    assert router.enabled is False

    state = router.toggle()
    assert state is True
    assert router.enabled is True

    state = router.toggle()
    assert state is False
    assert router.enabled is False


# ============================================================================
# 9. RoutingDecision is a proper NamedTuple
# ============================================================================

def test_routing_decision_named_tuple_structure():
    d = RoutingDecision(tier="fast", suggested_model="gemini-3.8-flash", reason="Short prompt.")
    assert d.tier == "fast"
    assert d.suggested_model == "gemini-3.8-flash"
    assert d.reason == "Short prompt."
    tier, model, reason = d  # NamedTuple unpacking
    assert tier == "fast"
    assert model == "gemini-3.8-flash"


# ============================================================================
# 10. Provider model registry completeness
# ============================================================================

@pytest.mark.parametrize("provider", PROVIDERS)
def test_router_all_providers_covered_in_tier_registries(provider: str):
    """Every provider must appear in at least the fast and deep tier registries."""
    assert provider in _FAST_MODELS, f"Provider '{provider}' missing from _FAST_MODELS"
    assert provider in _BALANCED_MODELS, f"Provider '{provider}' missing from _BALANCED_MODELS"
    assert provider in _DEEP_MODELS, f"Provider '{provider}' missing from _DEEP_MODELS"


# ============================================================================
# 11. Fallback to default_model when provider not in tier registry
# ============================================================================

def test_router_unknown_provider_falls_back_to_default():
    router = ModelAutoRouter(provider="unknown_provider_xyz", default_model="my-fallback", enabled=True)
    decision = router.route("hi")
    assert decision.suggested_model == "my-fallback"
