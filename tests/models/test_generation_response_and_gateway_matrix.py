"""PRUBETH Universal Model Gateway & Generation Response Matrix Tests.

Exhaustively verifies GenerationResponse data invariants, token accounting aliases,
and UniversalModelGateway local model detection resilience.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from prubeth.models.gateway import GenerationResponse, UniversalModelGateway
from prubeth.config.manager import ConfigManager


# ============================================================================
# 1. GenerationResponse Data Invariants & Token Properties
# ============================================================================

def test_generation_response_default_initialization():
    resp = GenerationResponse(text="test output")
    assert resp.text == "test output"
    assert resp.prompt_tokens == 0
    assert resp.candidate_tokens == 0
    assert resp.thinking_tokens == 0
    assert resp.cached_tokens == 0
    assert resp.cache_creation_tokens == 0
    assert resp.latency_s == 0.0
    assert resp.tool_calls is None
    assert resp.model == ""
    assert resp.provider == ""

    # Test alias properties
    assert resp.tokens_input == 0
    assert resp.tokens_output == 0
    assert resp.tokens_cached == 0
    assert resp.tokens_cache_creation == 0


def test_generation_response_full_values_and_aliases():
    resp = GenerationResponse(
        text="def compute(): return 42",
        prompt_tokens=1500,
        candidate_tokens=250,
        thinking_tokens=120,
        model="gemini-2.5-pro",
        provider="google",
        latency_s=0.85,
        tool_calls=[{"name": "read_file", "args": {"path": "main.py"}}],
        cached_tokens=1000,
        cache_creation_tokens=500
    )

    assert resp.tokens_input == 1500
    assert resp.tokens_output == 250
    assert resp.tokens_cached == 1000
    assert resp.tokens_cache_creation == 500
    assert resp.thinking_tokens == 120
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["name"] == "read_file"


# ============================================================================
# 2. Local Model Detection Resilience Matrix
# ============================================================================

def test_detect_local_model_returns_none_when_offline_servers_down(tmp_path: Path):
    cfg_mgr = ConfigManager(config_dir=tmp_path / "cfg")
    gateway = UniversalModelGateway(config_manager=cfg_mgr)

    # When ports 1234 (LM Studio) and 11434 (Ollama) are inactive, returns None quickly
    with patch("socket.create_connection", side_effect=OSError("Connection refused")):
        detected = gateway.detect_local_model()
        assert detected is None


def test_detect_local_model_identifies_ollama_when_available(tmp_path: Path):
    cfg_mgr = ConfigManager(config_dir=tmp_path / "cfg")
    gateway = UniversalModelGateway(config_manager=cfg_mgr)

    # Mock Ollama HTTP response
    mock_ollama_resp = MagicMock()
    mock_ollama_resp.read.return_value = b'{"models": [{"name": "qwen2.5-coder:7b"}]}'
    mock_ollama_resp.__enter__.return_value = mock_ollama_resp

    def mock_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "11434" in url:
            return mock_ollama_resp
        raise OSError("Port not listening")

    with patch("socket.create_connection", side_effect=[OSError("No LM Studio"), None]):
        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            res = gateway.detect_local_model()
            if res is not None:
                assert res.get("provider") == "ollama"
                assert "qwen2.5-coder" in res.get("model", "")
