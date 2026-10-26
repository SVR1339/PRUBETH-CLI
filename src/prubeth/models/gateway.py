import os
import json
import time
import socket
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
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
    tool_calls: Optional[List[Dict[str, Any]]] = None
    cached_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def tokens_input(self) -> int:
        return self.prompt_tokens

    @property
    def tokens_output(self) -> int:
        return self.candidate_tokens

    @property
    def tokens_cached(self) -> int:
        return self.cached_tokens

    @property
    def tokens_cache_creation(self) -> int:
        return self.cache_creation_tokens

class UniversalModelGateway:
    """Subsystem 6: High-Performance Universal Model Gateway.
    
    Provides host-grade optimization over any guest AI model (Google, Anthropic,
    OpenAI, DeepSeek, Groq, Ollama, LM Studio, OpenRouter) with native tool calling,
    prompt-caching prefix stability and auto-failover.
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
        prompt: Union[str, List[Dict[str, Any]]],
        system_instruction: str = "",
        model_name: Optional[str] = None,
        model_tier: str = "fast",
        prefer_local: bool = False,
        stream_cb: Optional[Any] = None,
        tools: Any = False,
        cached_content: Optional[str] = None,
        **kwargs
    ) -> GenerationResponse:
        """Single-turn or multi-turn generation wrapper backward-compatible with all existing subsystems."""
        if isinstance(prompt, list):
            messages = prompt
        else:
            messages = [{"role": "user", "content": prompt}]
        return self.generate_chat(
            messages=messages,
            system_instruction=system_instruction,
            tools=tools,
            model_name=model_name,
            model_tier=model_tier,
            prefer_local=prefer_local,
            cached_content=cached_content,
            stream_cb=stream_cb
        )

    def create_gemini_context_cache(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        system_instruction: str = "",
        tools: Any = False,
        ttl_s: int = 300,
        display_name: str = "prubeth-context-cache",
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates an explicit Gemini context cache session (cachedContents API) with custom TTL and tool declarations."""
        cfg = self.cfg_mgr.load_config()
        resolved = self.cfg_mgr.resolve_model_and_provider(model)
        key = api_key or resolved["api_key"]
        ep = endpoint or resolved["endpoint"] or cfg.get("provider_endpoints", {}).get("google", "https://generativelanguage.googleapis.com/v1beta")

        if not key:
            raise ValueError("Google Gemini API key required to create context cache. Set GEMINI_API_KEY.")

        clean_model = model if model.startswith("models/") else f"models/{model}"

        payload: Dict[str, Any] = {
            "model": clean_model,
            "displayName": display_name,
            "contents": contents,
            "ttl": f"{ttl_s}s"
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            from prubeth.tools.definitions import to_google_tools
            payload["tools"] = to_google_tools()

        url = f"{ep.rstrip('/')}/cachedContents?key={key}"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def generate_chat(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        system_instruction: str = "",
        tools: Any = False,
        model_name: Optional[str] = None,
        model_tier: str = "fast",
        prefer_local: bool = False,
        cached_content: Optional[str] = None,
        stream_cb: Optional[Any] = None
    ) -> GenerationResponse:
        """Routes structured multi-turn conversation to the optimal provider with native tool calling."""
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
        enable_caching = resolved.get("enable_caching", True)
        anthropic_cache_turns = resolved.get("anthropic_cache_turns", 2)
        thinking_budget = resolved.get("thinking_budget", 2048)
        reasoning_effort = resolved.get("reasoning_effort", "medium")

        t0 = time.time()
        try:
            if provider == "google":
                resp = self._generate_google(
                    model, messages, system_instruction, api_key, endpoint,
                    tools=tools, cached_content=cached_content, thinking_budget=thinking_budget,
                    timeout=cloud_timeout, stream_cb=stream_cb
                )
            elif provider == "anthropic":
                resp = self._generate_anthropic(
                    model, messages, system_instruction, api_key, endpoint,
                    tools=tools, enable_caching=enable_caching, anthropic_cache_turns=anthropic_cache_turns,
                    thinking_budget=thinking_budget, timeout=cloud_timeout, stream_cb=stream_cb
                )
            else:
                resp = self._generate_openai_compatible(
                    model, messages, system_instruction, api_key, endpoint, provider,
                    tools=tools, reasoning_effort=reasoning_effort, timeout=cloud_timeout, stream_cb=stream_cb
                )

            resp.latency_s = round(time.time() - t0, 3)
            from prubeth.models.telemetry import LLMOpsMonitor
            LLMOpsMonitor().record_call(
                model=resp.model or model,
                provider=resp.provider or provider,
                latency_s=resp.latency_s,
                input_tokens=resp.tokens_input,
                output_tokens=resp.tokens_output,
                cached_tokens=resp.tokens_cached,
                success=True,
                cache_creation_tokens=resp.tokens_cache_creation
            )
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
                        messages,
                        system_instruction,
                        local_loaded["api_key"],
                        local_loaded["endpoint"],
                        local_loaded["provider"],
                        tools=tools,
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
                        ("openrouter", "openrouter/free", or_key, or_endpoint),
                        ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free", or_key, or_endpoint),
                        ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free", or_key, or_endpoint),
                        ("openrouter", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", or_key, or_endpoint),
                        ("openrouter", "nvidia/nemotron-3.5-lightning:free", or_key, or_endpoint),
                        ("openrouter", "cohere/north-mini-code:free", or_key, or_endpoint),
                        ("openrouter", "google/gemma-4-31b-it:free", or_key, or_endpoint),
                        ("openrouter", "google/gemma-4-26b-a4b-it:free", or_key, or_endpoint)
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
                        ("google", "gemini-4-argon", gemini_key, gemini_endpoint),
                        ("google", "gemini-3.1-pro-preview", gemini_key, gemini_endpoint),
                        ("google", "gemini-3.8-flash", gemini_key, gemini_endpoint),
                        ("google", "gemini-pro-latest", gemini_key, gemini_endpoint),
                        ("google", "gemini-3.5-flash", gemini_key, gemini_endpoint),
                        ("google", "gemini-flash-latest", gemini_key, gemini_endpoint),
                        ("google", "gemini-3.1-flash-lite", gemini_key, gemini_endpoint)
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
                        resp = self._generate_google(fb_model, messages, system_instruction, fb_key, fb_endpoint, tools=tools, timeout=cloud_timeout)
                    elif fb_provider == "anthropic":
                        resp = self._generate_anthropic(fb_model, messages, system_instruction, fb_key, fb_endpoint, tools=tools, enable_caching=enable_caching, timeout=cloud_timeout)
                    else:
                        resp = self._generate_openai_compatible(fb_model, messages, system_instruction, fb_key, fb_endpoint, fb_provider, tools=tools, timeout=cloud_timeout)
                    
                    resp.latency_s = round(time.time() - t0, 3)
                    LLMOpsMonitor().record_call(fb_model, fb_provider, resp.latency_s, success=True)
                    return resp
                except Exception:
                    continue

            raise RuntimeError(f"Universal Gateway Error [{provider}/{model}]: {str(primary_err)}. All fallback models in resilience chain exhausted.")

    def _generate_google(
        self,
        model: str,
        messages: Union[str, List[Dict[str, Any]]],
        system_instruction: str,
        api_key: str,
        endpoint: str,
        tools: Any = False,
        cached_content: Optional[str] = None,
        thinking_budget: int = 2048,
        timeout: float = 12.0,
        stream_cb: Optional[Any] = None
    ) -> GenerationResponse:
        """High-speed native Google Gemini v1beta REST integration with function calling, streaming, and explicit context caching."""
        if not api_key:
            raise ValueError("Google Gemini API key missing. Set GEMINI_API_KEY or configure with `prubeth config set api_keys.google <KEY>`.")

        # Build strict Highest-to-Lowest Google frontier model hierarchy
        google_hierarchy = [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-4.0-preview",
            "gemini-4-argon",
            "gemini-3.1-pro-preview",
            "gemini-pro-latest",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-2.0-flash",
            "gemini-flash-latest",
            "gemini-3.1-flash-lite"
        ]
        models_to_try = [model]
        for m in google_hierarchy:
            if m not in models_to_try:
                models_to_try.append(m)

        # Build native structured contents list
        contents = []
        if isinstance(messages, str):
            contents.append({"role": "user", "parts": [{"text": messages}]})
        else:
            for m in messages:
                role = m.get("role", "user")
                if role == "user":
                    contents.append({"role": "user", "parts": [{"text": m.get("content", "")}]})
                elif role in ["model", "assistant"]:
                    parts = []
                    if m.get("content"):
                        parts.append({"text": m["content"]})
                    for tc in m.get("tool_calls", []):
                        parts.append({"functionCall": {"name": tc["name"], "args": tc.get("args", {})}})
                    contents.append({"role": "model", "parts": parts or [{"text": ""}]})
                elif role in ["tool", "function"]:
                    contents.append({
                        "role": "function",
                        "parts": [{
                            "functionResponse": {
                                "name": m.get("name", "tool"),
                                "response": {"name": m.get("name", "tool"), "content": str(m.get("content", ""))}
                            }
                        }]
                    })

        payload: Dict[str, Any] = {"contents": contents}

        # Explicit Context Caching (Google Gemini cachedContents)
        # Note: If cachedContent is provided, systemInstruction & tools are omitted
        # at call-time because they are already baked into the server VRAM cache session.
        if cached_content:
            payload["cachedContent"] = (
                cached_content if cached_content.startswith("cachedContents/")
                else f"cachedContents/{cached_content}"
            )
        else:
            if system_instruction:
                payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
            if tools:
                from prubeth.tools.definitions import to_google_tools
                payload["tools"] = to_google_tools()

        # Google Gemini 2.5 / 2.0 Extended Thinking Budget Configuration
        if thinking_budget > 0:
            payload["generationConfig"] = {
                "thinkingConfig": {
                    "thinkingBudget": thinking_budget
                }
            }

        data_bytes = json.dumps(payload).encode("utf-8")

        last_error = ""
        for target_m in models_to_try:
            if stream_cb:
                url = f"{endpoint}/models/{target_m}:streamGenerateContent?alt=sse&key={api_key}"
            else:
                url = f"{endpoint}/models/{target_m}:generateContent?key={api_key}"

            req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        if stream_cb:
                            accumulated = []
                            tool_calls = []
                            stream_cached = 0
                            stream_prompt = 0
                            stream_cand = 0
                            stream_thinking = 0
                            for raw_line in resp:
                                line = raw_line.decode("utf-8", errors="ignore").strip()
                                if line.startswith("data:"):
                                    chunk_str = line[5:].strip()
                                    if chunk_str:
                                        try:
                                            chunk = json.loads(chunk_str)
                                            u_meta = chunk.get("usageMetadata", {})
                                            if u_meta:
                                                stream_prompt = u_meta.get("promptTokenCount", stream_prompt)
                                                stream_cand = u_meta.get("candidatesTokenCount", stream_cand)
                                                stream_cached = u_meta.get("cachedContentTokenCount", stream_cached)
                                                stream_thinking = u_meta.get("thoughtsTokenCount", stream_thinking)

                                            parts = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                            for p in parts:
                                                t = p.get("text", "")
                                                if t:
                                                    accumulated.append(t)
                                                    stream_cb(t)
                                                if "functionCall" in p:
                                                    fc = p["functionCall"]
                                                    tool_calls.append({
                                                        "id": f"call_{len(tool_calls)+1}",
                                                        "name": fc.get("name", ""),
                                                        "args": fc.get("args", {})
                                                    })
                                        except Exception:
                                            pass
                            full_text = "".join(accumulated)
                            return GenerationResponse(
                                text=full_text,
                                prompt_tokens=stream_prompt,
                                candidate_tokens=stream_cand,
                                thinking_tokens=stream_thinking,
                                model=target_m,
                                provider="google",
                                tool_calls=tool_calls if tool_calls else None,
                                cached_tokens=stream_cached
                            )
                        else:
                            data = json.loads(resp.read().decode("utf-8"))
                            candidate = data.get("candidates", [{}])[0]
                            parts = candidate.get("content", {}).get("parts", [])
                            text_parts = []
                            tool_calls = []
                            for p in parts:
                                if "text" in p and p["text"]:
                                    text_parts.append(p["text"])
                                if "functionCall" in p:
                                    fc = p["functionCall"]
                                    tool_calls.append({
                                        "id": f"call_{len(tool_calls)+1}",
                                        "name": fc.get("name", ""),
                                        "args": fc.get("args", {})
                                    })
                            text = "".join(text_parts)
                            usage = data.get("usageMetadata", {})
                            return GenerationResponse(
                                text=text,
                                prompt_tokens=usage.get("promptTokenCount", 0),
                                candidate_tokens=usage.get("candidatesTokenCount", 0),
                                thinking_tokens=usage.get("thoughtsTokenCount", 0),
                                model=target_m,
                                provider="google",
                                tool_calls=tool_calls if tool_calls else None,
                                cached_tokens=usage.get("cachedContentTokenCount", 0)
                            )
                except urllib.error.HTTPError as e:
                    last_error = e.read().decode("utf-8", errors="ignore")
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
        messages: Union[str, List[Dict[str, Any]]],
        system_instruction: str,
        api_key: str,
        endpoint: str,
        tools: Any = False,
        enable_caching: bool = True,
        anthropic_cache_turns: int = 2,
        thinking_budget: int = 2048,
        timeout: float = 12.0,
        stream_cb: Optional[Any] = None
    ) -> GenerationResponse:
        """Native Anthropic Claude API with function calling and multi-breakpoint ephemeral prompt caching."""
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

        formatted_messages = []
        if isinstance(messages, str):
            formatted_messages.append({"role": "user", "content": messages})
        else:
            for m in messages:
                role = m.get("role", "user")
                if role == "user":
                    formatted_messages.append({"role": "user", "content": m.get("content", "")})
                elif role in ["assistant", "model"]:
                    blocks = []
                    if m.get("content"):
                        blocks.append({"type": "text", "text": m["content"]})
                    for tc in m.get("tool_calls", []):
                        blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id", f"toolu_{len(blocks)+1}"),
                            "name": tc["name"],
                            "input": tc.get("args", {})
                        })
                    formatted_messages.append({"role": "assistant", "content": blocks or ""})
                elif role == "tool":
                    formatted_messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id", ""),
                            "content": str(m.get("content", ""))
                        }]
                    })

        # Breakpoints 3 & 4: Multi-turn conversation ephemeral prompt caching breakpoints
        if enable_caching and formatted_messages and anthropic_cache_turns > 0:
            pins_remaining = min(2, anthropic_cache_turns)
            for msg in reversed(formatted_messages):
                if pins_remaining <= 0:
                    break
                if msg.get("role") == "user":
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        msg["content"] = [
                            {
                                "type": "text",
                                "text": content,
                                "cache_control": {"type": "ephemeral"}
                            }
                        ]
                        pins_remaining -= 1
                    elif isinstance(content, list) and content:
                        last_block = content[-1]
                        if isinstance(last_block, dict) and "cache_control" not in last_block:
                            last_block["cache_control"] = {"type": "ephemeral"}
                            pins_remaining -= 1

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "messages": formatted_messages
        }

        # Claude 3.7 Extended Hybrid Thinking Budget
        if thinking_budget > 0 and ("3-7" in model or "3.7" in model):
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget
            }
            payload["max_tokens"] = max(payload.get("max_tokens", 4096), thinking_budget + 2048)

        # Breakpoint 1: Static System Instruction Prefix
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

        # Breakpoint 2: Tool Catalog Schema
        if tools:
            from prubeth.tools.definitions import to_anthropic_tools
            anth_tools = to_anthropic_tools()
            if enable_caching and anth_tools:
                anth_tools[-1]["cache_control"] = {"type": "ephemeral"}
            payload["tools"] = anth_tools

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content_blocks = data.get("content", [])
            text_parts = []
            tool_calls = []
            thinking_tokens_count = 0
            for b in content_blocks:
                if b.get("type") == "text":
                    text_parts.append(b.get("text", ""))
                elif b.get("type") == "thinking":
                    th_text = b.get("thinking", "")
                    thinking_tokens_count += len(th_text.split())
                elif b.get("type") == "tool_use":
                    tool_calls.append({
                        "id": b.get("id", ""),
                        "name": b.get("name", ""),
                        "args": b.get("input", {})
                    })
            text = "".join(text_parts)
            usage = data.get("usage", {})
            cache_read = usage.get("cache_read_input_tokens", 0)
            cache_create = usage.get("cache_creation_input_tokens", 0)
            raw_input = usage.get("input_tokens", 0)
            total_prompt_tokens = raw_input + cache_read + cache_create

            return GenerationResponse(
                text=text,
                prompt_tokens=total_prompt_tokens,
                candidate_tokens=usage.get("output_tokens", 0),
                thinking_tokens=thinking_tokens_count or usage.get("thinking_tokens", 0),
                model=model,
                provider="anthropic",
                tool_calls=tool_calls if tool_calls else None,
                cached_tokens=cache_read,
                cache_creation_tokens=cache_create
            )

    def _generate_openai_compatible(
        self,
        model: str,
        messages: Union[str, List[Dict[str, Any]]],
        system_instruction: str,
        api_key: str,
        endpoint: str,
        provider_name: str,
        tools: Any = False,
        reasoning_effort: Optional[str] = "medium",
        timeout: float = 12.0,
        stream_cb: Optional[Any] = None
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

        formatted_messages = []
        if system_instruction:
            formatted_messages.append({"role": "system", "content": system_instruction})

        if isinstance(messages, str):
            formatted_messages.append({"role": "user", "content": messages})
        else:
            for m in messages:
                role = m.get("role", "user")
                if role == "tool":
                    formatted_messages.append({
                        "role": "tool",
                        "tool_call_id": m.get("tool_call_id", "call_1"),
                        "content": str(m.get("content", ""))
                    })
                elif role in ["assistant", "model"]:
                    tcs = []
                    for tc in m.get("tool_calls", []):
                        tcs.append({
                            "id": tc.get("id", f"call_{len(tcs)+1}"),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("args", {}))
                            }
                        })
                    entry: Dict[str, Any] = {"role": "assistant", "content": m.get("content") or ""}
                    if tcs:
                        entry["tool_calls"] = tcs
                    formatted_messages.append(entry)
                else:
                    formatted_messages.append({"role": role, "content": m.get("content", "")})

        is_reasoning_model = any(m in model.lower() for m in ["o1", "o3", "o3-mini"])
        payload: Dict[str, Any] = {
            "model": model,
            "messages": formatted_messages
        }
        if is_reasoning_model:
            if reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort
        else:
            payload["temperature"] = 0.2
        if tools:
            from prubeth.tools.definitions import to_openai_tools
            payload["tools"] = to_openai_tools()

        if stream_cb:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}

        req_timeout = 30.0 if provider_name in ["lm_studio", "ollama"] and "localhost" in url else timeout
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                if stream_cb:
                    accumulated = []
                    stream_cached = 0
                    stream_prompt = 0
                    stream_completion = 0
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if line.startswith("data:"):
                            chunk_str = line[5:].strip()
                            if chunk_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(chunk_str)
                                u = chunk.get("usage")
                                if u:
                                    stream_prompt = u.get("prompt_tokens", stream_prompt)
                                    stream_completion = u.get("completion_tokens", stream_completion)
                                    p_det = u.get("prompt_tokens_details", {}) or {}
                                    stream_cached = p_det.get("cached_tokens", 0) or u.get("prompt_cache_hit_tokens", 0) or u.get("cached_tokens", 0)

                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    accumulated.append(delta)
                                    stream_cb(delta)
                            except Exception:
                                pass
                    return GenerationResponse(
                        text="".join(accumulated),
                        prompt_tokens=stream_prompt,
                        candidate_tokens=stream_completion,
                        model=model,
                        provider=provider_name,
                        cached_tokens=stream_cached
                    )
                else:
                    data = json.loads(resp.read().decode("utf-8"))
                    choice = data["choices"][0]
                    message = choice.get("message", {})

                    text = message.get("content", "") or ""
                    reasoning = message.get("reasoning_content", "") or ""
                    raw_tool_calls = message.get("tool_calls", [])
                    tool_calls = []
                    for tc in raw_tool_calls:
                        fn = tc.get("function", {})
                        try:
                            args = json.loads(fn.get("arguments", "{}"))
                        except Exception:
                            args = {"raw": fn.get("arguments", "")}
                        tool_calls.append({
                            "id": tc.get("id", ""),
                            "name": fn.get("name", ""),
                            "args": args
                        })

                    usage = data.get("usage", {}) or {}
                    prompt_details = usage.get("prompt_tokens_details", {}) or {}
                    comp_details = usage.get("completion_tokens_details", {}) or {}

                    cached_toks = (
                        prompt_details.get("cached_tokens", 0)
                        or usage.get("prompt_cache_hit_tokens", 0)
                        or usage.get("cached_tokens", 0)
                    )
                    reasoning_toks = comp_details.get("reasoning_tokens", 0)
                    if not reasoning_toks and reasoning:
                        reasoning_toks = len(reasoning.split())

                    return GenerationResponse(
                        text=text,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        candidate_tokens=usage.get("completion_tokens", 0),
                        thinking_tokens=reasoning_toks,
                        model=model,
                        provider=provider_name,
                        tool_calls=tool_calls if tool_calls else None,
                        cached_tokens=cached_toks
                    )
        except urllib.error.HTTPError as e:
            # If server rejected native 'tools' schema, retry once cleanly without tools parameter
            if tools and e.code in [400, 422]:
                return self._generate_openai_compatible(
                    model, messages, system_instruction, api_key, endpoint,
                    provider_name, tools=False, reasoning_effort=reasoning_effort, timeout=timeout, stream_cb=stream_cb
                )
            raise
        except urllib.error.URLError as e:
            if "localhost" in url:
                raise RuntimeError(f"Local server connection failed at {url}. Make sure {provider_name.upper()} is running.")
            raise

# Backward-compatible alias
ModelGateway = UniversalModelGateway
