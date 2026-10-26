"""PRUBETH Frontier Prompt & Context Caching Subsystem.

Implements native host-grade cloning of:
1. Anthropic Claude Ephemeral Prompt Caching (4 breakpoints, anthropic-beta header, 90% read discount).
2. Google Gemini Context Caching (explicit cachedContents REST API, GPU VRAM tool & system instruction baking, TTL lifecycle).
3. OpenAI & DeepSeek 1024-token Prefix KV Cache Pinning.
"""

import time
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

@dataclass
class GeminiCacheSession:
    """Represents an active server-side Google Gemini GPU VRAM context cache session."""
    name: str                 # e.g. "cachedContents/ab12cd34ef56"
    model: str                # e.g. "models/gemini-2.5-pro"
    display_name: str
    create_time: str
    expire_time: str
    total_tokens: int
    created_at_epoch: float
    ttl_s: int
    context_hash: str

    @property
    def is_expired(self) -> bool:
        """Checks if session has expired or is within 15 seconds of expiration."""
        return time.time() >= (self.created_at_epoch + self.ttl_s - 15)

    @property
    def remaining_seconds(self) -> int:
        """Returns remaining seconds before cache expiration."""
        return max(0, int((self.created_at_epoch + self.ttl_s) - time.time()))

class ContextCacheManager:
    """Subsystem 17: Autonomous Prompt KV & Context Cache Lifecycle Manager.
    
    Clones and coordinates:
    - Google Gemini cachedContents explicit REST lifecycle with GPU VRAM persistence.
    - Anthropic Claude 4-breakpoint ephemeral prompt caching.
    - OpenAI / DeepSeek prefix KV cache alignment.
    """

    def __init__(self, workspace_root: Optional[Path] = None, config_manager: Optional[Any] = None, gateway: Optional[Any] = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        from prubeth.config.manager import ConfigManager
        from prubeth.models.gateway import UniversalModelGateway
        self.cfg_mgr = config_manager or ConfigManager()
        self.gateway = gateway or UniversalModelGateway(self.cfg_mgr)
        self.active_gemini_session: Optional[GeminiCacheSession] = None
        self.total_cache_hits: int = 0

    def compute_context_hash(self, workspace_context: str, system_instruction: str) -> str:
        """Computes deterministic SHA-256 hash of codebase context and system instruction."""
        hasher = hashlib.sha256()
        hasher.update(system_instruction.encode("utf-8"))
        hasher.update(workspace_context.encode("utf-8"))
        return hasher.hexdigest()[:16]

    def get_or_create_gemini_session(
        self,
        model: str,
        workspace_context: str,
        system_instruction: str = "",
        tools: Any = True,
        ttl_s: Optional[int] = None,
        api_key: Optional[str] = None
    ) -> Optional[str]:
        """Clones Google Gemini explicit cachedContents creation and returns active cache name.
        
        Checks if an active, unexpired session exists for the exact same codebase snapshot.
        If valid, reuses the session instantly (< 1ms).
        If expired or drifted, creates a new cachedContents session in Google GPU VRAM.
        """
        import os
        cfg = self.cfg_mgr.load_config()
        if not cfg.get("enable_context_caching", True):
            return None

        resolved = self.cfg_mgr.resolve_model_and_provider(model)
        if resolved["provider"] != "google":
            return None

        key = api_key or resolved["api_key"] or os.getenv("GEMINI_API_KEY", "")
        if not key:
            return None

        clean_model = resolved["model"]
        target_ttl = ttl_s or int(cfg.get("context_cache_ttl_s", 300))
        ctx_hash = self.compute_context_hash(workspace_context, system_instruction)

        # 1. Reuse existing valid session if context has not drifted and TTL is active
        if (
            self.active_gemini_session
            and self.active_gemini_session.model in [clean_model, f"models/{clean_model}"]
            and self.active_gemini_session.context_hash == ctx_hash
            and not self.active_gemini_session.is_expired
        ):
            self.total_cache_hits += 1
            return self.active_gemini_session.name

        # 2. Check minimum token threshold before incurring cache creation overhead
        min_tokens = int(cfg.get("prompt_cache_min_tokens", 1024))
        approx_tokens = max(
            len(workspace_context.split()) + len(system_instruction.split()),
            len(workspace_context) // 4
        )
        if approx_tokens < min_tokens:
            return None

        # 3. Create explicit Gemini cachedContents session via REST API
        try:
            contents = [
                {
                    "role": "user",
                    "parts": [{"text": f"Workspace Codebase Context & Instructions:\n{workspace_context}"}]
                }
            ]
            cache_meta = self.gateway.create_gemini_context_cache(
                model=clean_model,
                contents=contents,
                system_instruction=system_instruction,
                tools=tools,
                ttl_s=target_ttl,
                display_name=f"prubeth-{self.workspace_root.name}",
                api_key=key
            )
            cache_name = cache_meta.get("name", "")
            if cache_name:
                u_meta = cache_meta.get("usageMetadata", {})
                self.active_gemini_session = GeminiCacheSession(
                    name=cache_name,
                    model=clean_model,
                    display_name=cache_meta.get("displayName", "prubeth-cache"),
                    create_time=cache_meta.get("createTime", ""),
                    expire_time=cache_meta.get("expireTime", ""),
                    total_tokens=u_meta.get("totalTokenCount", approx_tokens),
                    created_at_epoch=time.time(),
                    ttl_s=target_ttl,
                    context_hash=ctx_hash
                )
                self.total_cache_hits += 1
                return cache_name
        except Exception:
            # Graceful fallback: un-cached generation proceeds without interruption
            pass

        return None

    def invalidate_gemini_cache(self):
        """Invalidates and purges the active Gemini context cache session."""
        self.active_gemini_session = None

    def get_cache_telemetry(self, current_model: Optional[str] = None) -> Dict[str, Any]:
        """Returns deep telemetry for both Context Caching (Gemini) and Prompt Caching (Claude/OpenAI)."""
        cfg = self.cfg_mgr.load_config()
        resolved = self.cfg_mgr.resolve_model_and_provider(current_model)
        from prubeth.cli.hud import calculate_session_spend
        spend = calculate_session_spend()

        gemini_info = None
        if self.active_gemini_session and not self.active_gemini_session.is_expired:
            gemini_info = {
                "name": self.active_gemini_session.name,
                "model": self.active_gemini_session.model,
                "remaining_seconds": self.active_gemini_session.remaining_seconds,
                "total_tokens": self.active_gemini_session.total_tokens,
                "expire_time": self.active_gemini_session.expire_time,
                "status": "ACTIVE_VRAM_PERSISTED"
            }

        provider = resolved["provider"]
        if provider == "google":
            method_name = "Context Caching (cachedContents REST API)"
            discount_desc = "75% read discount in server GPU VRAM"
        elif provider == "anthropic":
            method_name = "Prompt Caching (Ephemeral headers)"
            discount_desc = "90% read discount across 4 breakpoints"
        elif provider in ["openai", "deepseek"]:
            method_name = "Prefix KV Cache Pinning"
            discount_desc = "50-75% discount on 1024-token boundaries"
        else:
            method_name = "Local GGUF In-Memory KV Reuse"
            discount_desc = "100% free offline memory reuse"

        return {
            "model": resolved["model"],
            "provider": provider,
            "method_name": method_name,
            "discount_desc": discount_desc,
            "enable_prompt_caching": cfg.get("enable_prompt_caching", True),
            "enable_context_caching": cfg.get("enable_context_caching", True),
            "anthropic_cache_turns": cfg.get("anthropic_cache_turns", 2),
            "context_cache_ttl_s": cfg.get("context_cache_ttl_s", 300),
            "gemini_session": gemini_info,
            "session_cached_tokens": spend.get("cached_tokens", 0),
            "session_saved_usd": spend.get("total_saved_usd", 0.0),
            "total_cache_hits": self.total_cache_hits
        }
