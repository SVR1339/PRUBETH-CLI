import os
import json
import time
import socket
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from prubeth.config.manager import ConfigManager

@dataclass
class GenerationResponse:
    text: str
    prompt_tokens: int = 0
    candidate_tokens: int = 0
    thinking_tokens: int = 0
    model: str = ""
    provider: str = ""
    latency_s: float = 0.0

class UniversalModelGateway:
    """Subsystem 6: High-Performance Universal Model Gateway.
    
    Provides host-grade optimization over any guest AI model (Google, Anthropic,
    OpenAI, DeepSeek, Groq, Ollama, LM Studio, OpenRouter) with prompt-caching
    prefix stability and auto-failover.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.cfg_mgr = config_manager or ConfigManager()

    def detect_local_model(self) -> Optional[Dict[str, Any]]:
        """Fast-probes local offline engines (LM Studio and Ollama) in < 120ms.
        
        Returns the actively downloaded and loaded model details if available.
        """
        cfg = self.cfg_mgr.load_config()

        # 1. Fast probe LM Studio (127.0.0.1:1234)
        lm_endpoint = cfg.get("provider_endpoints", {}).get("lm_studio", "http://localhost:1234/v1")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.06)
                s.connect(("127.0.0.1", 1234))
            req = urllib.request.Request(f"{lm_endpoint.rstrip('/')}/models", headers={"User-Agent": "PRUBETH-CLI"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("data") and len(data["data"]) > 0:
                    model_id = data["data"][0].get("id", "local-model")
                    return {
                        "provider": "lm_studio",
                        "model": model_id,
                        "endpoint": lm_endpoint,
                        "api_key": ""
                    }
        except Exception:
            pass

        # 2. Fast probe Ollama (127.0.0.1:11434)
        ollama_endpoint = cfg.get("provider_endpoints", {}).get("ollama", "http://localhost:11434/v1")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.06)
                s.connect(("127.0.0.1", 11434))
            ollama_base = ollama_endpoint.replace("/v1", "")
            req = urllib.request.Request(f"{ollama_base.rstrip('/')}/api/tags", headers={"User-Agent": "PRUBETH-CLI"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                if models and len(models) > 0:
                    model_name = models[0].get("name", "qwen2.5-coder:7b")
                    return {
                        "provider": "ollama",
                        "model": model_name,
                        "endpoint": ollama_endpoint,
                        "api_key": ""
                    }
        except Exception:
            pass

        return None

    def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        model_name: Optional[str] = None,
        model_tier: str = "fast",
        prefer_local: bool = False
    ) -> GenerationResponse:
        """Routes generation to the requested or optimal model provider with strict Highest-to-Lowest hierarchy."""
        cfg = self.cfg_mgr.load_config()
        cloud_timeout = float(cfg.get("cloud_timeout_s", 12.0))

        # Check tier override (e.g., planner_model vs coder_model)
        target_model = model_name
        if not target_model:
            if model_tier == "reasoning" and cfg.get("planner_model"):
                target_model = cfg["planner_model"]
            elif model_tier == "fast" and cfg.get("coder_model"):
                target_model = cfg["coder_model"]

        if prefer_local and not target_model:
            target_model = "local-lm-studio"

        resolved = self.cfg_mgr.resolve_model_and_provider(target_model)
        model = resolved["model"]
        provider = "lm_studio" if prefer_local else resolved["provider"]
        endpoint = resolved["endpoint"]
        api_key = resolved["api_key"]
        enable_caching = resolved["enable_caching"]

        t0 = time.time()
        try:
            if provider == "google":
                resp = self._generate_google(model, prompt, system_instruction, api_key, endpoint, timeout=cloud_timeout)
            elif provider == "anthropic":
                resp = self._generate_anthropic(model, prompt, system_instruction, api_key, endpoint, enable_caching, timeout=cloud_timeout)
            else:
                resp = self._generate_openai_compatible(model, prompt, system_instruction, api_key, endpoint, provider, timeout=cloud_timeout)

            resp.latency_s = round(time.time() - t0, 3)
            return resp

        except Exception as primary_err:
            from prubeth.models.telemetry import LLMOpsMonitor
            LLMOpsMonitor().record_call(model, provider, time.time() - t0, success=False, error_message=str(primary_err))

            # Check if primary failure was due to high latency or timeout ("taking too much time")
            err_msg = str(primary_err).lower()
            is_timeout = (
                isinstance(primary_err, (TimeoutError, socket.timeout))
                or "timed out" in err_msg
                or "timeout" in err_msg
                or (time.time() - t0) >= cloud_timeout
            )
            # Check if primary failure was due to API Key issues (missing, 401, 403, invalid)
            is_auth_error = (
                "api key missing" in err_msg
                or "unauthorized" in err_msg
                or "forbidden" in err_msg
                or "401" in err_msg
                or "403" in err_msg
                or "invalid api key" in err_msg
            )

            # Fast-probe active local offline downloaded & loaded models (<120ms)
            local_loaded = self.detect_local_model()

            # SRE Direct Local Pivot: If API key has issues OR cloud is taking too much time, DIRECTLY RUN LOCAL
            if (is_auth_error or is_timeout) and local_loaded:
                try:
                    resp = self._generate_openai_compatible(
                        local_loaded["model"],
                        prompt,
                        system_instruction,
                        local_loaded["api_key"],
                        local_loaded["endpoint"],
                        local_loaded["provider"],
                        timeout=30.0
                    )
                    resp.latency_s = round(time.time() - t0, 3)
                    LLMOpsMonitor().record_call(local_loaded["model"], local_loaded["provider"], resp.latency_s, success=True)
                    return resp
                except Exception:
                    pass

            # Build Hierarchical Failover Cascade: STRICTLY ORDERED HIGHEST TO LOWEST MODEL
            failover_candidates = []
            
            if provider == "google":
                # Primary was Google. Fallback to OpenRouter Highest-to-Lowest free tier
                or_key = cfg.get("api_keys", {}).get("openrouter") or os.getenv("OPENROUTER_API_KEY", "")
                if or_key:
                    or_endpoint = cfg.get("provider_endpoints", {}).get("openrouter", "https://openrouter.ai/api/v1")
                    failover_candidates.extend([
                        ("openrouter", "openrouter/free", or_key, or_endpoint),                                      # Rank 1: Frontier Smart Auto-Router
                        ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free", or_key, or_endpoint),             # Rank 1: 550B Frontier Giant
                        ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free", or_key, or_endpoint),             # Rank 1: 120B MoE Reasoning
                        ("openrouter", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", or_key, or_endpoint), # Rank 1: 30B Reasoning Specialist
                        ("openrouter", "nvidia/nemotron-3.5-lightning:free", or_key, or_endpoint),                  # Rank 2: High Throughput
                        ("openrouter", "cohere/north-mini-code:free", or_key, or_endpoint),                          # Rank 2: Code Specialist
                        ("openrouter", "google/gemma-4-31b-it:free", or_key, or_endpoint),                          # Rank 3: 31B Instruction
                        ("openrouter", "google/gemma-4-26b-a4b-it:free", or_key, or_endpoint)                       # Rank 3: 26B Lightweight
                    ])
                # Google Ultra-fast Lite fallback
                gemini_key = cfg.get("api_keys", {}).get("google") or os.getenv("GEMINI_API_KEY", "")
                if gemini_key:
                    failover_candidates.append(("google", "gemini-3.1-flash-lite", gemini_key, endpoint))
            else:
                # Primary was OpenRouter or other. Fallback to Google Gemini Highest-to-Lowest cascade
                gemini_key = cfg.get("api_keys", {}).get("google") or os.getenv("GEMINI_API_KEY", "")
                if gemini_key:
                    gemini_endpoint = cfg.get("provider_endpoints", {}).get("google", "https://generativelanguage.googleapis.com/v1beta")
                    failover_candidates.extend([
                        ("google", "gemini-3.1-pro-preview", gemini_key, gemini_endpoint),  # Rank 1 Flagship Pro Reasoning
                        ("google", "gemini-pro-latest", gemini_key, gemini_endpoint),       # Rank 1 Stable Pro
                        ("google", "gemini-3.8-flash", gemini_key, gemini_endpoint),        # Rank 2 Frontier Flash
                        ("google", "gemini-3.5-flash", gemini_key, gemini_endpoint),        # Rank 2 Balanced Workhorse
                        ("google", "gemini-flash-latest", gemini_key, gemini_endpoint),     # Rank 2 Production Flash
                        ("google", "gemini-3.1-flash-lite", gemini_key, gemini_endpoint)     # Rank 3 Ultra-Fast Lite
                    ])

            # Local downloaded model fallback (100% private, zero cost, air-gapped)
            if local_loaded:
                failover_candidates.append((local_loaded["provider"], local_loaded["model"], "", local_loaded["endpoint"]))
            else:
                ollama_endpoint = cfg.get("provider_endpoints", {}).get("ollama", "http://localhost:11434/v1")
                lm_endpoint = cfg.get("provider_endpoints", {}).get("lm_studio", "http://localhost:1234/v1")
                failover_candidates.extend([
                    ("ollama", "qwen2.5-coder:7b", "", ollama_endpoint),
                    ("lm_studio", "local-model", "", lm_endpoint)
                ])

            for fb_provider, fb_model, fb_key, fb_endpoint in failover_candidates:
                try:
                    if fb_provider == "google":
                        resp = self._generate_google(fb_model, prompt, system_instruction, fb_key, fb_endpoint, timeout=cloud_timeout)
                    elif fb_provider == "anthropic":
                        resp = self._generate_anthropic(fb_model, prompt, system_instruction, fb_key, fb_endpoint, enable_caching, timeout=cloud_timeout)
                    else:
                        resp = self._generate_openai_compatible(fb_model, prompt, system_instruction, fb_key, fb_endpoint, fb_provider, timeout=cloud_timeout)
                    
                    resp.latency_s = round(time.time() - t0, 3)
                    LLMOpsMonitor().record_call(fb_model, fb_provider, resp.latency_s, success=True)
                    return resp
                except Exception:
                    continue

            raise RuntimeError(f"Universal Gateway Error [{provider}/{model}]: {str(primary_err)}. All fallback models in resilience chain exhausted.")

    def _generate_google(
        self,
        model: str,
        prompt: str,
        system_instruction: str,
        api_key: str,
        endpoint: str,
        timeout: float = 12.0
    ) -> GenerationResponse:
        """High-speed native Google Gemini v1beta REST integration with retry backoff."""
        if not api_key:
            raise ValueError("Google Gemini API key missing. Set GEMINI_API_KEY or configure with `prubeth config set api_keys.google <KEY>`.")

        # Build strict Highest-to-Lowest Google model hierarchy
        google_hierarchy = [
            "gemini-3.1-pro-preview",
            "gemini-pro-latest",
            "gemini-3.5-flash",
            "gemini-flash-latest",
            "gemini-3.1-flash-lite"
        ]
        models_to_try = [model]
        for m in google_hierarchy:
            if m not in models_to_try:
                models_to_try.append(m)

        # Stable prefix structure for prompt caching
        contents = []
        if system_instruction:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTION: {system_instruction}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}
        data_bytes = json.dumps(payload).encode("utf-8")

        last_error = ""
        for target_m in models_to_try:
            url = f"{endpoint}/models/{target_m}:generateContent?key={api_key}"
            req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        candidate = data["candidates"][0]
                        text = candidate["content"]["parts"][0]["text"]
                        usage = data.get("usageMetadata", {})
                        return GenerationResponse(
                            text=text,
                            prompt_tokens=usage.get("promptTokenCount", 0),
                            candidate_tokens=usage.get("candidatesTokenCount", 0),
                            thinking_tokens=usage.get("thoughtsTokenCount", 0),
                            model=target_m,
                            provider="google"
                        )
                except urllib.error.HTTPError as e:
                    last_error = e.read().decode("utf-8", errors="ignore")
                    # Break immediately on 404 or 429 quota exhaustion to shift to next model in hierarchy!
                    if e.code in [404, 429]:
                        break
                    if e.code == 503 and attempt < 1:
                        time.sleep(1)
                        continue
                    break
                except Exception as e:
                    last_error = str(e)
                    break

        raise RuntimeError(last_error or "Google Gemini generation failed.")

    def _generate_anthropic(
        self,
        model: str,
        prompt: str,
        system_instruction: str,
        api_key: str,
        endpoint: str,
        enable_caching: bool = True,
        timeout: float = 12.0
    ) -> GenerationResponse:
        """Native Anthropic Claude API with ephemeral prompt caching headers."""
        if not api_key:
            raise ValueError("Anthropic API key missing. Set ANTHROPIC_API_KEY or configure with `prubeth config set api_keys.anthropic <KEY>`.")

        url = f"{endpoint.rstrip('/')}/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        if enable_caching:
            headers["anthropic-beta"] = "prompt-caching-2024-07-31"

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }

        if system_instruction:
            if enable_caching:
                payload["system"] = [
                    {
                        "type": "text",
                        "text": system_instruction,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            else:
                payload["system"] = system_instruction

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = "".join([b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"])
            usage = data.get("usage", {})
            return GenerationResponse(
                text=text,
                prompt_tokens=usage.get("input_tokens", 0),
                candidate_tokens=usage.get("output_tokens", 0),
                thinking_tokens=0,
                model=model,
                provider="anthropic"
            )

    def _generate_openai_compatible(
        self,
        model: str,
        prompt: str,
        system_instruction: str,
        api_key: str,
        endpoint: str,
        provider_name: str,
        timeout: float = 12.0
    ) -> GenerationResponse:
        """Universal OpenAI-compatible endpoint handler (OpenAI, DeepSeek, Groq, Ollama, LM Studio)."""
        clean_endpoint = endpoint.rstrip("/")
        if not clean_endpoint.endswith("/chat/completions"):
            url = f"{clean_endpoint}/chat/completions"
        else:
            url = clean_endpoint

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PRUBETH-Autonomous-CLI/1.0"
        }
        if provider_name == "openrouter" or "openrouter.ai" in url:
            headers["HTTP-Referer"] = "https://github.com/prubeth-autonomous-cli"
            headers["X-Title"] = "PRUBETH Autonomous CLI"
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2
        }

        req_timeout = 30.0 if provider_name in ["lm_studio", "ollama"] and "localhost" in url else timeout
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        
        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data["choices"][0]
                message = choice.get("message", {})
                
                # Extract text or reasoning content (DeepSeek-R1 / o3-mini support)
                text = message.get("content", "") or ""
                reasoning = message.get("reasoning_content", "") or ""
                
                usage = data.get("usage", {})
                return GenerationResponse(
                    text=text,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    candidate_tokens=usage.get("completion_tokens", 0),
                    thinking_tokens=len(reasoning.split()) if reasoning else 0,
                    model=model,
                    provider=provider_name
                )
        except urllib.error.URLError as e:
            if "localhost" in url:
                raise RuntimeError(f"Local server connection failed at {url}. Make sure {provider_name.upper()} is running.")
            raise

# Backward-compatible alias
ModelGateway = UniversalModelGateway
