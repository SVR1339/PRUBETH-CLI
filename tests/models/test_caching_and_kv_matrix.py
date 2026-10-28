"""PRUBETH Prompt & Context Caching Permutation Matrix Tests.

Verifies GeminiCacheSession lifecycle, TTL expiration, ContextCacheManager SHA-256
snapshot hashing, minimum token thresholds, and multi-provider caching telemetry.
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from prubeth.models.caching import GeminiCacheSession, ContextCacheManager


# ============================================================================
# 1. GeminiCacheSession Dataclass Lifecycle
# ============================================================================

def test_cache_session_not_expired_when_fresh():
    session = GeminiCacheSession(
        name="cachedContents/sess_12345",
        model="gemini-2.5-pro",
        display_name="prubeth-test",
        create_time="2026-10-28T00:00:00Z",
        expire_time="2026-10-28T00:05:00Z",
        total_tokens=15000,
        created_at_epoch=time.time(),
        ttl_s=300,
        context_hash="abc1234def5678"
    )
    assert session.is_expired is False
    assert session.remaining_seconds > 200


def test_cache_session_expired_when_ttl_elapsed():
    session = GeminiCacheSession(
        name="cachedContents/sess_old",
        model="gemini-2.5-pro",
        display_name="prubeth-test",
        create_time="2026-10-28T00:00:00Z",
        expire_time="2026-10-28T00:01:00Z",
        total_tokens=15000,
        created_at_epoch=time.time() - 300,  # 300 seconds in the past
        ttl_s=60,                            # 60s TTL
        context_hash="abc1234def5678"
    )
    assert session.is_expired is True
    assert session.remaining_seconds == 0


# ============================================================================
# 2. ContextCacheManager Hashing & Thresholds
# ============================================================================

def test_compute_context_hash_deterministic():
    mgr = ContextCacheManager()
    h1 = mgr.compute_context_hash("class Worker:\n    pass\n", "You are an autonomous engineer.")
    h2 = mgr.compute_context_hash("class Worker:\n    pass\n", "You are an autonomous engineer.")
    h3 = mgr.compute_context_hash("class Worker:\n    pass\n\n", "You are an autonomous engineer.")

    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16


def test_get_or_create_bypassed_if_below_token_threshold():
    mgr = ContextCacheManager()
    # Tiny context of 5 words is far below the default 1024 token minimum
    tiny_context = "def test(): pass"
    res = mgr.get_or_create_gemini_session(
        model="gemini-2.5-pro",
        workspace_context=tiny_context,
        system_instruction="System",
        api_key="fake-key"
    )
    assert res is None  # Below threshold, does not incur cache creation overhead


def test_invalidate_gemini_cache():
    mgr = ContextCacheManager()
    mgr.active_gemini_session = GeminiCacheSession(
        name="cachedContents/active",
        model="gemini-2.5-pro",
        display_name="prubeth-test",
        create_time="now",
        expire_time="later",
        total_tokens=2000,
        created_at_epoch=time.time(),
        ttl_s=300,
        context_hash="hash"
    )
    assert mgr.active_gemini_session is not None
    mgr.invalidate_gemini_cache()
    assert mgr.active_gemini_session is None


# ============================================================================
# 3. Cache Telemetry Across Providers
# ============================================================================

@pytest.mark.parametrize("provider_name,expected_method_prefix", [
    ("google", "Context Caching"),
    ("anthropic", "Prompt Caching"),
    ("openai", "Prefix KV Cache"),
    ("deepseek", "Prefix KV Cache"),
    ("ollama", "Local GGUF In-Memory KV Reuse"),
])
def test_cache_telemetry_provider_descriptions(provider_name: str, expected_method_prefix: str):
    mgr = ContextCacheManager()
    # Mock cfg_mgr.resolve_model_and_provider
    mgr.cfg_mgr = MagicMock()
    mgr.cfg_mgr.load_config.return_value = {
        "enable_prompt_caching": True,
        "enable_context_caching": True,
        "anthropic_cache_turns": 2,
        "context_cache_ttl_s": 300
    }
    mgr.cfg_mgr.resolve_model_and_provider.return_value = {
        "model": f"{provider_name}-model",
        "provider": provider_name
    }

    with patch("prubeth.cli.hud.calculate_session_spend", return_value={"cached_tokens": 100, "total_saved_usd": 0.05}):
        telemetry = mgr.get_cache_telemetry(f"{provider_name}-model")

    assert telemetry["provider"] == provider_name
    assert expected_method_prefix in telemetry["method_name"]
    assert "discount_desc" in telemetry
    assert telemetry["session_cached_tokens"] == 100
