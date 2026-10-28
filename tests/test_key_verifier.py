"""Tests for UniversalKeyVerifier — Personal & Worldwide AI Key Verification Engine."""

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prubeth.models.key_verifier import UniversalKeyVerifier, KeyVerificationResult
from prubeth.cli.commands import handle_verify_command


@pytest.fixture
def verifier():
    return UniversalKeyVerifier()


class TestUniversalKeyVerifier:

    def test_unconfigured_key_returns_unconfigured_status(self, verifier):
        res = verifier.verify_key("google", "")
        assert res.status == "unconfigured"
        assert not res.is_operational

    def test_verify_google_valid_key(self, verifier):
        mock_payload = json.dumps({
            "models": [
                {"name": "models/gemini-2.5-pro"},
                {"name": "models/gemini-2.5-flash"}
            ]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_payload
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = verifier.verify_key("google", "test_gemini_key_123")
            assert res.status == "valid"
            assert res.is_operational
            assert "gemini-2.5-pro" in res.models_available
            assert res.supports_thinking
            assert res.supports_caching
            assert res.tier == "cloud_personal"

    def test_verify_anthropic_valid_key(self, verifier):
        mock_payload = json.dumps({
            "data": [
                {"id": "claude-3-7-sonnet-20250219"},
                {"id": "claude-3-5-sonnet-20241022"}
            ]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_payload
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = verifier.verify_key("anthropic", "sk-ant-test12345")
            assert res.status == "valid"
            assert "claude-3-7-sonnet-20250219" in res.models_available
            assert res.supports_thinking

    def test_verify_openai_valid_key(self, verifier):
        mock_payload = json.dumps({
            "data": [
                {"id": "o3-mini"},
                {"id": "gpt-4o"}
            ]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_payload
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = verifier.verify_key("openai", "sk-proj-test12345")
            assert res.status == "valid"
            assert "o3-mini" in res.models_available

    def test_verify_invalid_key_401(self, verifier):
        http_err = urllib.error.HTTPError(
            url="https://api.openai.com/v1/models",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            res = verifier.verify_key("openai", "invalid_key")
            assert res.status == "invalid"
            assert "Invalid Credentials" in res.error_message

    def test_verify_rate_limited_key_429(self, verifier):
        http_err = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            res = verifier.verify_key("google", "valid_key_but_429")
            # 429 means key is authentic but rate-limited
            assert res.status == "valid"
            assert "429" in res.error_message

    def test_verify_local_offline(self, verifier):
        # When socket connection fails, should report offline without throwing
        with patch("socket.socket.connect", side_effect=ConnectionRefusedError()):
            res = verifier.verify_local_engine("ollama")
            assert res.status == "offline"
            assert res.tier == "local"

    def test_verify_custom_worldwide_endpoint(self, verifier):
        mock_payload = json.dumps({
            "data": [{"id": "mistral-7b-custom"}]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_payload
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = verifier._verify_custom_endpoint(
                "my_worldwide_llm",
                "custom_key_999",
                "https://llm.mycompany.org/v1",
                timeout_s=2.0
            )
            assert res.status == "valid"
            assert res.tier == "custom_worldwide"
            assert "mistral-7b-custom" in res.models_available

    def test_scan_all_configured(self, verifier):
        mock_cfg = MagicMock()
        mock_cfg.load_config.return_value = {
            "api_keys": {"google": "key1", "openrouter": "key2"},
            "provider_endpoints": {},
            "custom_providers": {}
        }
        with patch.object(verifier, "verify_key", return_value=KeyVerificationResult(provider="google", status="valid")), \
             patch.object(verifier, "verify_local_engine", return_value=KeyVerificationResult(provider="ollama", status="offline")):
            results = verifier.scan_all_configured(mock_cfg)
            assert "google" in results
            assert "ollama" in results
            assert len(results) >= 5

    def test_handle_verify_command_execution(self):
        # Test CLI handler execution does not crash
        with patch("prubeth.models.key_verifier.UniversalKeyVerifier.scan_all_configured", return_value={
            "google": KeyVerificationResult(provider="google", status="valid", latency_ms=45.2, models_available=["gemini-2.5-pro"])
        }):
            handle_verify_command([])

        with patch("prubeth.models.key_verifier.UniversalKeyVerifier.verify_key", return_value=KeyVerificationResult(provider="openrouter", status="valid", latency_ms=32.1)):
            handle_verify_command(["openrouter", "sk-or-test"])
