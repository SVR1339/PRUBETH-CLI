"""PRUBETH Universal Personal AI Provider & Key Verification Engine.

Validates and benchmarks local engines, open-source API endpoints, personal developer keys,
and any worldwide OpenAI-compatible provider with zero telemetry.
"""

from __future__ import annotations

import json
import time
import socket
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class KeyVerificationResult:
    """Detailed verification outcome for an AI provider credential."""
    provider: str
    status: str  # "valid", "invalid", "unreachable", "offline", "unconfigured"
    latency_ms: float = 0.0
    models_available: List[str] = field(default_factory=list)
    supports_thinking: bool = False
    supports_caching: bool = False
    error_message: str = ""
    endpoint: str = ""
    tier: str = "cloud_personal"  # "local", "open_source_free", "cloud_personal", "custom_worldwide"

    @property
    def is_operational(self) -> bool:
        return self.status == "valid"


class UniversalKeyVerifier:
    """Verifies personal, open-source, and local AI provider credentials worldwide.
    
    Operates 100% locally with zero telemetry: requests only ping metadata endpoints
    (e.g., /models or /tags) using minimal payload (< 1KB) to establish key validity.
    """

    DEFAULT_TIMEOUT_S = 6.0

    # Provider probing endpoints & auth patterns
    KNOWN_PROVIDERS: Dict[str, Dict[str, Any]] = {
        "google": {
            "name": "Google Gemini (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://generativelanguage.googleapis.com/v1beta/models?key={key}",
            "auth_type": "param",
            "headers": {"User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: [m.get("name", "").replace("models/", "") for m in d.get("models", [])[:10]],
            "thinking_models": ["gemini-2.5-pro", "gemini-3.1-pro-preview", "gemini-4.0-preview"],
            "caching_models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-3.1-pro-preview"]
        },
        "anthropic": {
            "name": "Anthropic Claude (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://api.anthropic.com/v1/models",
            "auth_type": "header_anthropic",
            "headers": {
                "x-api-key": "{key}",
                "anthropic-version": "2023-06-01",
                "User-Agent": "PRUBETH-CLI/1.4"
            },
            "models_extractor": lambda d: [m.get("id", "") for m in d.get("data", [])[:10]],
            "thinking_models": ["claude-3-7-sonnet-20250219"],
            "caching_models": ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
        },
        "openai": {
            "name": "OpenAI (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://api.openai.com/v1/models",
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer {key}", "User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: [m.get("id", "") for m in d.get("data", []) if "gpt" in m.get("id", "") or "o" in m.get("id", "")][:10],
            "thinking_models": ["o3-mini", "o1"],
            "caching_models": ["o3-mini", "gpt-4o", "gpt-4o-mini"]
        },
        "openrouter": {
            "name": "OpenRouter (Open Source & Multi-Model)",
            "tier": "open_source_free",
            "url": "https://openrouter.ai/api/v1/auth/key",
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer {key}", "User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: ["deepseek/deepseek-r1:free", "meta-llama/llama-3.3-70b:free", "qwen/qwen-2.5-coder-32b:free"],
            "thinking_models": ["deepseek/deepseek-r1", "deepseek/deepseek-r1:free"],
            "caching_models": ["anthropic/claude-3.7-sonnet", "google/gemini-2.5-pro"]
        },
        "deepseek": {
            "name": "DeepSeek (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://api.deepseek.com/models",
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer {key}", "User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: [m.get("id", "") for m in d.get("data", [])[:5]],
            "thinking_models": ["deepseek-reasoner", "deepseek-r1"],
            "caching_models": ["deepseek-chat", "deepseek-coder"]
        },
        "groq": {
            "name": "Groq Ultra-Fast (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://api.groq.com/openai/v1/models",
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer {key}", "User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: [m.get("id", "") for m in d.get("data", [])[:10]],
            "thinking_models": ["deepseek-r1-distill-llama-70b"],
            "caching_models": []
        },
        "mistral": {
            "name": "Mistral AI (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://api.mistral.ai/v1/models",
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer {key}", "User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: [m.get("id", "") for m in d.get("data", [])[:10]],
            "thinking_models": ["mistral-large-latest"],
            "caching_models": []
        },
        "together": {
            "name": "Together AI (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://api.together.xyz/v1/models",
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer {key}", "User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: [m.get("id", "") for m in d.get("data", [])[:10]],
            "thinking_models": ["deepseek-ai/DeepSeek-R1"],
            "caching_models": []
        },
        "xai": {
            "name": "xAI Grok (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://api.x.ai/v1/models",
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer {key}", "User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: [m.get("id", "") for m in d.get("data", [])[:10]],
            "thinking_models": ["grok-2-reasoning"],
            "caching_models": []
        },
        "cerebras": {
            "name": "Cerebras Inference (Personal Key)",
            "tier": "cloud_personal",
            "url": "https://api.cerebras.ai/v1/models",
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer {key}", "User-Agent": "PRUBETH-CLI/1.4"},
            "models_extractor": lambda d: [m.get("id", "") for m in d.get("data", [])[:10]],
            "thinking_models": [],
            "caching_models": []
        }
    }

    def verify_key(
        self,
        provider: str,
        api_key: str,
        custom_base_url: Optional[str] = None,
        timeout_s: Optional[float] = None
    ) -> KeyVerificationResult:
        """Verifies a single personal or worldwide provider API key."""
        provider_key = provider.lower().strip()
        timeout = timeout_s or self.DEFAULT_TIMEOUT_S

        # 1. Custom worldwide provider verification
        if custom_base_url and provider_key not in self.KNOWN_PROVIDERS:
            return self._verify_custom_endpoint(provider_key, api_key, custom_base_url, timeout)

        # 2. Local air-gapped engines
        if provider_key in ["ollama", "lm_studio", "local"]:
            return self.verify_local_engine(provider_key, custom_base_url, timeout)

        # 3. Known personal / open-source cloud provider
        meta = self.KNOWN_PROVIDERS.get(provider_key)
        if not meta:
            # Fallback to OpenAI-compatible assumption for unknown provider
            if api_key:
                return KeyVerificationResult(
                    provider=provider,
                    status="valid",
                    tier="custom_worldwide",
                    error_message="Unknown provider treated as generic API key."
                )
            return KeyVerificationResult(
                provider=provider,
                status="unconfigured",
                tier="custom_worldwide",
                error_message="No key provided."
            )

        if not api_key or not api_key.strip():
            return KeyVerificationResult(
                provider=provider_key,
                status="unconfigured",
                tier=meta["tier"],
                error_message="API key is empty or not set."
            )

        clean_key = api_key.strip()
        target_url = meta["url"].format(key=clean_key)
        headers = {k: v.format(key=clean_key) for k, v in meta["headers"].items()}

        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                raw = resp.read().decode("utf-8")
                try:
                    data = json.loads(raw)
                    extractor = meta.get("models_extractor", lambda d: [])
                    extracted = extractor(data)
                except Exception:
                    extracted = []

                # Filter empty items
                clean_models = [m for m in extracted if m]
                thinking = bool(meta.get("thinking_models"))
                caching = bool(meta.get("caching_models"))

                return KeyVerificationResult(
                    provider=provider_key,
                    status="valid",
                    latency_ms=round(elapsed_ms, 2),
                    models_available=clean_models,
                    supports_thinking=thinking,
                    supports_caching=caching,
                    endpoint=target_url.split("?")[0],
                    tier=meta["tier"]
                )

        except urllib.error.HTTPError as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            msg = f"HTTP {e.code}: {e.reason}"
            if e.code in [401, 403]:
                msg = f"Invalid Credentials (HTTP {e.code}): Check that your personal key is active."
            elif e.code == 429:
                # 429 indicates the key is recognized but quota or rate-limited
                return KeyVerificationResult(
                    provider=provider_key,
                    status="valid",
                    latency_ms=round(elapsed_ms, 2),
                    supports_thinking=bool(meta.get("thinking_models")),
                    supports_caching=bool(meta.get("caching_models")),
                    error_message="Key valid but currently rate-limited (HTTP 429).",
                    tier=meta["tier"]
                )
            return KeyVerificationResult(
                provider=provider_key,
                status="invalid",
                latency_ms=round(elapsed_ms, 2),
                error_message=msg,
                tier=meta["tier"]
            )

        except (urllib.error.URLError, socket.timeout) as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return KeyVerificationResult(
                provider=provider_key,
                status="unreachable",
                latency_ms=round(elapsed_ms, 2),
                error_message=f"Network unreachable: {e}",
                tier=meta["tier"]
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return KeyVerificationResult(
                provider=provider_key,
                status="invalid",
                latency_ms=round(elapsed_ms, 2),
                error_message=f"Verification failed: {e}",
                tier=meta["tier"]
            )

    def verify_local_engine(
        self,
        engine_type: str = "ollama",
        endpoint: Optional[str] = None,
        timeout_s: float = 0.5
    ) -> KeyVerificationResult:
        """Pings local air-gapped engines (Ollama or LM Studio) with ultra-low latency."""
        t0 = time.perf_counter()

        if "lm" in engine_type.lower():
            target = endpoint or "http://127.0.0.1:1234/v1"
            probe_url = f"{target.rstrip('/')}/models"
            host, port = "127.0.0.1", 1234
        else:
            raw_target = endpoint or "http://127.0.0.1:11434"
            target = raw_target.replace("/v1", "").rstrip("/")
            probe_url = f"{target}/api/tags"
            host, port = "127.0.0.1", 11434

        # Fast socket probe (< 60ms) to ensure port is listening
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.06)
                s.connect((host, port))
        except Exception:
            return KeyVerificationResult(
                provider=engine_type,
                status="offline",
                latency_ms=0.0,
                error_message=f"Local service not running on {host}:{port}.",
                endpoint=target,
                tier="local"
            )

        try:
            req = urllib.request.Request(probe_url, headers={"User-Agent": "PRUBETH-CLI/1.4"})
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                models = []
                if "models" in data:
                    models = [m.get("name", "") for m in data["models"]]
                elif "data" in data:
                    models = [m.get("id", "") for m in data["data"]]

                return KeyVerificationResult(
                    provider=engine_type,
                    status="valid",
                    latency_ms=round(elapsed_ms, 2),
                    models_available=models[:10],
                    supports_thinking=any("r1" in m.lower() for m in models),
                    supports_caching=False,
                    endpoint=target,
                    tier="local"
                )
        except Exception as e:
            return KeyVerificationResult(
                provider=engine_type,
                status="unreachable",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error_message=str(e),
                endpoint=target,
                tier="local"
            )

    def _verify_custom_endpoint(
        self,
        provider_name: str,
        api_key: str,
        base_url: str,
        timeout_s: float
    ) -> KeyVerificationResult:
        """Verifies any custom worldwide OpenAI-compatible endpoint."""
        clean_url = base_url.rstrip("/")
        models_url = f"{clean_url}/models"
        headers = {"User-Agent": "PRUBETH-CLI/1.4"}
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"

        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(models_url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("id", "") for m in data.get("data", [])[:10]]
                return KeyVerificationResult(
                    provider=provider_name,
                    status="valid",
                    latency_ms=round(elapsed_ms, 2),
                    models_available=models,
                    endpoint=clean_url,
                    tier="custom_worldwide"
                )
        except urllib.error.HTTPError as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return KeyVerificationResult(
                provider=provider_name,
                status="invalid" if e.code in [401, 403] else "unreachable",
                latency_ms=round(elapsed_ms, 2),
                error_message=f"HTTP {e.code}: {e.reason}",
                endpoint=clean_url,
                tier="custom_worldwide"
            )
        except Exception as e:
            return KeyVerificationResult(
                provider=provider_name,
                status="unreachable",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error_message=str(e),
                endpoint=clean_url,
                tier="custom_worldwide"
            )

    def scan_all_configured(self, cfg_manager: Any) -> Dict[str, KeyVerificationResult]:
        """Scans all configured API keys and local runtimes across the system."""
        cfg = cfg_manager.load_config()
        keys = cfg.get("api_keys", {})
        endpoints = cfg.get("provider_endpoints", {})

        results: Dict[str, KeyVerificationResult] = {}

        # 1. Probe local engines first (sub-millisecond when offline)
        results["ollama"] = self.verify_local_engine("ollama", endpoints.get("ollama"))
        results["lm_studio"] = self.verify_local_engine("lm_studio", endpoints.get("lm_studio"))

        # 2. Check cloud & open-source keys
        for prov in ["google", "openrouter", "anthropic", "openai", "deepseek", "groq", "mistral", "together", "xai"]:
            k = keys.get(prov, "")
            # Check env var if missing
            if not k:
                env_map = {
                    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
                    "openrouter": ["OPENROUTER_API_KEY"],
                    "anthropic": ["ANTHROPIC_API_KEY"],
                    "openai": ["OPENAI_API_KEY"],
                    "deepseek": ["DEEPSEEK_API_KEY"],
                    "groq": ["GROQ_API_KEY"],
                    "mistral": ["MISTRAL_API_KEY"],
                    "together": ["TOGETHER_API_KEY"],
                    "xai": ["XAI_API_KEY"]
                }
                import os
                for ev in env_map.get(prov, []):
                    if os.environ.get(ev):
                        k = os.environ[ev]
                        break

            if k:
                results[prov] = self.verify_key(prov, k, custom_base_url=endpoints.get(prov))
            else:
                results[prov] = KeyVerificationResult(
                    provider=prov,
                    status="unconfigured",
                    tier=self.KNOWN_PROVIDERS.get(prov, {}).get("tier", "cloud_personal"),
                    error_message="No personal API key configured."
                )

        # 3. Custom worldwide providers registered in config
        custom_providers = cfg.get("custom_providers", {})
        for name, custom_meta in custom_providers.items():
            base_url = custom_meta.get("base_url", "")
            key = custom_meta.get("api_key", "")
            results[name] = self.verify_key(name, key, custom_base_url=base_url)

        return results

    verify = verify_key
