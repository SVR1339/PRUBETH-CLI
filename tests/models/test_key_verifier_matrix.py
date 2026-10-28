"""PRUBETH Universal Key Verifier — Provider Schema & Credential Matrix Tests.

Tests the KeyVerificationResult structure, provider registry completeness,
tier classification, capability metadata, and offline/mocked verification paths.
All tests are 100% offline — no real network calls are made.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import asdict

from prubeth.models.key_verifier import (
    KeyVerificationResult,
    UniversalKeyVerifier,
)

PERSONAL_CLOUD_PROVIDERS = ["google", "anthropic", "openai", "deepseek", "groq", "mistral", "together", "xai", "cerebras"]
LOCAL_PROVIDERS = ["ollama", "lm_studio"]
OPEN_SOURCE_FREE_PROVIDERS = ["openrouter"]

ALL_PROVIDERS = PERSONAL_CLOUD_PROVIDERS + LOCAL_PROVIDERS + OPEN_SOURCE_FREE_PROVIDERS


# ============================================================================
# 1. KeyVerificationResult dataclass structure
# ============================================================================

def test_key_verification_result_fields():
    result = KeyVerificationResult(
        provider="google",
        status="valid",
        latency_ms=42.0,
        models_available=["gemini-2.5-pro", "gemini-2.5-flash"],
        supports_thinking=True,
        supports_caching=True,
        error_message="",
        endpoint="https://generativelanguage.googleapis.com/v1beta",
        tier="cloud_personal",
    )
    assert result.is_operational is True
    assert result.provider == "google"
    assert result.tier == "cloud_personal"
    assert len(result.models_available) == 2


@pytest.mark.parametrize("status,expected", [
    ("valid", True),
    ("invalid", False),
    ("unreachable", False),
    ("offline", False),
    ("unconfigured", False),
])
def test_key_result_is_operational_status_matrix(status: str, expected: bool):
    result = KeyVerificationResult(provider="google", status=status)
    assert result.is_operational is expected


# ============================================================================
# 2. Provider registry completeness
# ============================================================================

def test_known_providers_registry_not_empty():
    assert len(UniversalKeyVerifier.KNOWN_PROVIDERS) >= 9


@pytest.mark.parametrize("provider", ["google", "anthropic", "openai", "deepseek", "groq", "mistral"])
def test_known_providers_required_entries_present(provider: str):
    assert provider in UniversalKeyVerifier.KNOWN_PROVIDERS
    entry = UniversalKeyVerifier.KNOWN_PROVIDERS[provider]
    assert "name" in entry
    assert "tier" in entry
    assert "url" in entry


@pytest.mark.parametrize("provider", ["google", "anthropic", "openai", "deepseek", "groq", "mistral"])
def test_provider_entries_have_thinking_and_caching_metadata(provider: str):
    entry = UniversalKeyVerifier.KNOWN_PROVIDERS[provider]
    assert "thinking_models" in entry
    assert "caching_models" in entry
    assert isinstance(entry["thinking_models"], list)
    assert isinstance(entry["caching_models"], list)


# ============================================================================
# 3. Tier classification correctness
# ============================================================================

@pytest.mark.parametrize("provider,expected_tier", [
    ("google", "cloud_personal"),
    ("anthropic", "cloud_personal"),
    ("openai", "cloud_personal"),
    ("openrouter", "open_source_free"),
    ("deepseek", "cloud_personal"),
    ("groq", "cloud_personal"),
])
def test_provider_tier_classifications(provider: str, expected_tier: str):
    entry = UniversalKeyVerifier.KNOWN_PROVIDERS[provider]
    assert entry["tier"] == expected_tier


# ============================================================================
# 4. Offline / unconfigured verification result
# ============================================================================

def test_verifier_unconfigured_returns_unconfigured_status():
    verifier = UniversalKeyVerifier()
    result = verifier.verify("nonexistent_provider_xyz", "")
    assert result.status == "unconfigured"
    assert result.is_operational is False


def test_verifier_empty_key_returns_unconfigured():
    verifier = UniversalKeyVerifier()
    result = verifier.verify("google", "")
    assert result.status == "unconfigured"
    assert "unconfigured" in result.status or result.error_message or not result.is_operational


# ============================================================================
# 5. Mocked valid response — Google Gemini
# ============================================================================

def test_verifier_google_valid_key_mocked():
    mock_response_data = {
        "models": [
            {"name": "models/gemini-2.5-pro"},
            {"name": "models/gemini-2.5-flash"},
            {"name": "models/gemini-3.8-flash"},
        ]
    }
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_response_data).encode()
    mock_response.status = 200
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        verifier = UniversalKeyVerifier()
        result = verifier.verify("google", "AIzaFakeKey12345")

    assert result.provider == "google"
    assert result.status == "valid"
    assert result.is_operational is True
    assert len(result.models_available) >= 1


# ============================================================================
# 6. Mocked 401 / Invalid key response
# ============================================================================

def test_verifier_invalid_key_mocked():
    import urllib.error
    http_error = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models?key=bad",
        code=401,
        msg="API key not valid",
        hdrs=None,
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=http_error):
        verifier = UniversalKeyVerifier()
        result = verifier.verify("google", "bad-key")

    assert result.status == "invalid"
    assert result.is_operational is False


# ============================================================================
# 7. Mocked network unreachable
# ============================================================================

def test_verifier_network_unreachable_mocked():
    import urllib.error
    url_error = urllib.error.URLError(reason="Connection refused")
    with patch("urllib.request.urlopen", side_effect=url_error):
        verifier = UniversalKeyVerifier()
        result = verifier.verify("openai", "sk-fake-openai-key")

    assert result.status in ("unreachable", "invalid")
    assert result.is_operational is False


# ============================================================================
# 8. Capabilities detection — thinking and caching flags
# ============================================================================

@pytest.mark.parametrize("provider,model,expect_thinking,expect_caching", [
    ("google", "gemini-2.5-pro", True, True),
    ("anthropic", "claude-3-7-sonnet-20250219", True, True),
    ("openai", "o3-mini", True, True),
    ("deepseek", "deepseek-r1", True, False),
])
def test_thinking_and_caching_detection(provider: str, model: str, expect_thinking: bool, expect_caching: bool):
    entry = UniversalKeyVerifier.KNOWN_PROVIDERS.get(provider)
    if not entry:
        pytest.skip(f"Provider {provider} not in KNOWN_PROVIDERS")
    detected_thinking = model in entry.get("thinking_models", [])
    detected_caching = model in entry.get("caching_models", [])
    assert detected_thinking == expect_thinking
    assert detected_caching == expect_caching


# ============================================================================
# 9. Batch verification summary structure
# ============================================================================

def test_verifier_batch_summary_structure():
    verifier = UniversalKeyVerifier()
    mock_cfg = MagicMock()
    mock_cfg.load_config.return_value = {
        "api_keys": {},
        "provider_endpoints": {}
    }
    with patch.object(verifier, "verify_local_engine", return_value=KeyVerificationResult(provider="ollama", status="offline")):
        results = verifier.scan_all_configured(mock_cfg)
    assert isinstance(results, dict)
    assert "ollama" in results
    assert "google" in results
    assert any(r.status == "unconfigured" for r in results.values())
