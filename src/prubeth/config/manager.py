import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from prubeth.config.schema import (
    SETTING_REGISTRY,
    validate_setting_value,
    CAT_PERFORMANCE,
    CAT_COGNITIVE,
    CAT_RESILIENCE,
    CAT_SECURITY,
    CAT_DEV_EXP
)

MODEL_ALIASES: Dict[str, str] = {
    # Frontier Google Gemini with Context Caching & Hybrid Thinking
    "2.5": "gemini-2.5-pro",
    "2.5-pro": "gemini-2.5-pro",
    "gemini-2.5": "gemini-2.5-pro",
    "gemini-2.5-pro": "gemini-2.5-pro",
    "2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "2.0": "gemini-2.0-flash",
    "2.0-flash": "gemini-2.0-flash",
    "gemini-2.0-flash": "gemini-2.0-flash",
    "1.5-pro": "gemini-1.5-pro",
    "gemini-1.5-pro": "gemini-1.5-pro",
    "1.5-flash": "gemini-1.5-flash",
    "gemini-1.5-flash": "gemini-1.5-flash",
    "4.0": "gemini-4.0-preview",
    "4": "gemini-4.0-preview",
    "gemini-4": "gemini-4.0-preview",
    "gemini-4.0": "gemini-4.0-preview",
    "argon": "gemini-4-argon",
    "gemini-4-argon": "gemini-4-argon",
    "3.8": "gemini-2.5-flash",
    "3.8-flash": "gemini-2.5-flash",
    "gemini-3.8": "gemini-2.5-flash",
    "gemini-3.8-flash": "gemini-2.5-flash",
    "3.1": "gemini-2.5-pro",
    "3.1-pro": "gemini-2.5-pro",
    "gemini-3.1": "gemini-2.5-pro",
    "gemini-3.1-pro": "gemini-2.5-pro",
    "gemini-3.1-pro-preview": "gemini-2.5-pro",
    "gemini-3.1-flash-lite": "gemini-2.5-flash",
    "3.5": "gemini-2.5-flash",
    "3.5-flash": "gemini-2.5-flash",
    "gemini-3.5": "gemini-2.5-flash",

    # Frontier Anthropic Claude with Multi-Breakpoint Ephemeral Prompt Caching
    "claude-3-7-sonnet-20250219": "claude-3-7-sonnet-20250219",
    "claude-3.7": "claude-3-7-sonnet-20250219",
    "claude-3-7-sonnet": "claude-3-7-sonnet-20250219",
    "sonnet": "claude-3-7-sonnet-20250219",
    "claude": "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
    "claude-3.5": "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
    "haiku": "claude-3-5-haiku-20241022",
    "claude-3-5-haiku": "claude-3-5-haiku-20241022",
    "opus": "claude-3-opus-20240229",

    # Frontier OpenAI with Deterministic Prefix KV Cache Pinning
    "o3": "o3-mini",
    "o3-mini": "o3-mini",
    "o1": "o1",
    "o1-preview": "o1-preview",
    "o1-mini": "o1-mini",
    "gpt-4.5": "gpt-4.5-preview",
    "gpt-4.5-preview": "gpt-4.5-preview",
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",

    # Frontier DeepSeek with 90% Discount Prefix Caching
    "r1": "deepseek/deepseek-r1:free",
    "deepseek-r1": "deepseek-r1",
    "v3": "deepseek-v3",
    "deepseek-v3": "deepseek-v3",
    "deepseek": "deepseek/deepseek-r1:free",
    "deepseek-chat": "deepseek-chat",

    # Local Offline Air-Gapped Models
    "local": "qwen2.5-coder:7b",
    "ollama": "qwen2.5-coder:7b",
    "lmstudio": "local-model"
}

PROFILES: Dict[str, Dict[str, Any]] = {
    "builder": {
        "name": "Performance Builder",
        "badge": "⚡ BUILDER",
        "desc": "Maximum software engineering velocity, prompt caching enabled, and autonomous Plan B resilience.",
        "settings": {
            "developer_mode": True,
            "enable_prompt_caching": True,
            "speculative_plan_b": True,
            "plan_b_strategy": "auto_pivot",
            "auto_checkpoint": True,
            "auto_rollback_on_failure": True,
            "auto_approve_actions": True,
            "watchdog_timeout_s": 45,
            "max_execution_turns": 10,
            "self_healing_retries": 3,
            "offline_mode": False,
            "strict_sandbox": True
        }
    },
    "deep-reasoning": {
        "name": "Deep Reasoning & Architecture",
        "badge": "🧠 DEEP-REASONING",
        "desc": "Heavy cognitive rigor, extended verification loops, multi-tier recovery for complex refactors.",
        "settings": {
            "developer_mode": True,
            "enable_prompt_caching": True,
            "speculative_plan_b": True,
            "plan_b_strategy": "auto_pivot",
            "auto_checkpoint": True,
            "auto_rollback_on_failure": True,
            "auto_approve_actions": False,
            "watchdog_timeout_s": 90,
            "max_execution_turns": 15,
            "self_healing_retries": 5,
            "offline_mode": False,
            "strict_sandbox": True
        }
    },
    "local-airgap": {
        "name": "Local Air-Gapped (Offline)",
        "badge": "🛡️ AIRGAP-LOCAL",
        "desc": "100% offline, zero cloud network egress. Routes strictly to local LM Studio or Ollama GGUF models.",
        "settings": {
            "developer_mode": True,
            "enable_prompt_caching": False,
            "speculative_plan_b": True,
            "plan_b_strategy": "fallback_model",
            "auto_checkpoint": True,
            "auto_rollback_on_failure": True,
            "auto_approve_actions": False,
            "watchdog_timeout_s": 120,
            "max_execution_turns": 10,
            "self_healing_retries": 2,
            "offline_mode": True,
            "default_provider": "lm_studio",
            "default_model": "local-model",
            "strict_sandbox": True
        }
    },
    "safe-audit": {
        "name": "Strict Security & Compliance",
        "badge": "🔒 STRICT-AUDIT",
        "desc": "Human verification gate before every file edit, full diff logging, strict boundary enforcement.",
        "settings": {
            "developer_mode": True,
            "enable_prompt_caching": True,
            "speculative_plan_b": False,
            "plan_b_strategy": "ask_developer",
            "auto_checkpoint": True,
            "auto_rollback_on_failure": True,
            "auto_approve_actions": False,
            "verbose_tool_output": True,
            "watchdog_timeout_s": 45,
            "max_execution_turns": 8,
            "self_healing_retries": 2,
            "strict_sandbox": True
        }
    }
}

DEFAULT_CONFIG: Dict[str, Any] = {
    # Active Profile
    "active_profile": "builder",

    # 1. Model & Provider Preferences
    "default_model": "gemini-2.5-pro",
    "default_provider": "google",
    "planner_model": None,  # Defaults to default_model if None
    "coder_model": None,    # Defaults to default_model if None
    "cloud_timeout_s": 45,  # Latency timeout before auto-pivoting to local downloaded models (45s for reasoning models)
    "provider_endpoints": {
        "google": "https://generativelanguage.googleapis.com/v1beta",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "groq": "https://api.groq.com/openai/v1",
        "ollama": "http://localhost:11434/v1",
        "lm_studio": "http://localhost:1234/v1",
        "openrouter": "https://openrouter.ai/api/v1"
    },
    "api_keys": {
        "google": "",
        "openai": "",
        "anthropic": "",
        "deepseek": "",
        "groq": "",
        "openrouter": ""
    },

    # 2. Elite Developer Mode & Diagnostics
    "developer_mode": True,              # Shows real-time latency, token metrics, AST diffs
    "log_level": "INFO",                 # DEBUG | INFO | WARN | ERROR
    "verbose_tool_output": False,        # If true, prints raw unclipped tool stdout

    # 3. Plan B & Self-Healing Resilience
    "speculative_plan_b": True,          # Autonomously drafts Plan B alongside Plan A
    "plan_b_strategy": "auto_pivot",     # auto_pivot | fallback_model | ask_developer
    "self_healing_retries": 3,           # Test failure diagnostic & auto-fix attempts
    "auto_checkpoint": True,             # Creates shadow snapshot before destructive edits
    "auto_rollback_on_failure": True,    # Reverts workspace if all recovery attempts fail

    # 4. Anti-Freeze Watchdogs & Environment Adaptation
    "watchdog_timeout_s": 45,            # Hard kill deadline for frozen subprocesses/tools
    "offline_mode": False,               # Disables cloud requests, forces local LM Studio/Ollama
    "strict_sandbox": True,              # Jails operations strictly within workspace path
    "enable_prompt_caching": True,       # Prefix-stable KV cache optimization
    "enable_context_caching": True,      # Explicit Gemini context caching
    "context_cache_ttl_s": 300,          # Context cache session TTL in seconds
    "anthropic_cache_turns": 2,          # Ephemeral multi-turn cache breakpoint depth
    "prompt_cache_min_tokens": 1024,     # Minimum token threshold for cache persistence
    "max_execution_turns": 10,           # Max autonomous tool turns before forced verification
    "auto_approve_actions": True,        # Default True under Performance Builder profile
    "thinking_budget": 2048,             # Reasoning / thinking budget for Claude 3.7 & Gemini 2.5
    "reasoning_effort": "medium",        # low | medium | high for OpenAI o1/o3-mini models
    "default_language": "auto"           # Preferred polyglot language stack (auto | python | rust | go | ts etc)
}

class ConfigManager:
    """Subsystem 10: Configuration and Elite Developer Settings Engine."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or (Path.home() / ".prubeth")
        self.config_file = self.config_dir / "config.json"
        self._ensure_config()

    def _ensure_config(self):
        """Ensures the config file exists with default schema."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            env_file = self.config_dir / ".env"
            initial_cfg = DEFAULT_CONFIG.copy()
            if env_file.exists():
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("GEMINI_API_KEY="):
                                initial_cfg["api_keys"]["google"] = line.split("=", 1)[1].strip()
                            elif line.startswith("PRUBETH_DEFAULT_MODEL="):
                                initial_cfg["default_model"] = line.split("=", 1)[1].strip()
                except Exception:
                    pass
            self.save_config(initial_cfg)

    def load_config(self) -> Dict[str, Any]:
        """Loads configuration from JSON file, merging with defaults."""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            for k, v in data.items():
                if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                    merged[k] = {**merged[k], **v}
                else:
                    merged[k] = v
            return merged
        except Exception:
            return DEFAULT_CONFIG.copy()

    def save_config(self, cfg: Dict[str, Any]):
        """Persists configuration to JSON."""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Gets a configuration value using dot notation (e.g. 'api_keys.google')."""
        cfg = self.load_config()
        parts = key.split(".")
        current = cfg
        for p in parts:
            if isinstance(current, dict) and p in current:
                current = current[p]
            else:
                return default
        return current

    def set(self, key: str, value: Any):
        """Sets a configuration value using dot notation and saves with typed validation."""
        # Top-level schema validation if recognized
        clean_key = key.split(".")[0] if "." in key else key
        if clean_key in SETTING_REGISTRY:
            valid, coerced_val, err_msg = validate_setting_value(clean_key, value)
            if not valid:
                raise ValueError(err_msg)
            value = coerced_val

        cfg = self.load_config()
        parts = key.split(".")
        current = cfg
        for p in parts[:-1]:
            if p not in current or not isinstance(current[p], dict):
                current[p] = {}
            current = current[p]
        current[parts[-1]] = value
        self.save_config(cfg)

    def toggle(self, key: str) -> bool:
        """Flips a boolean configuration flag and returns the new value."""
        clean_key = key.strip()
        if clean_key in SETTING_REGISTRY and SETTING_REGISTRY[clean_key].value_type != "bool":
            raise ValueError(f"Setting '{clean_key}' is not a boolean flag (type: {SETTING_REGISTRY[clean_key].value_type}).")
            
        current_val = self.get(clean_key)
        if isinstance(current_val, bool):
            new_val = not current_val
            self.set(clean_key, new_val)
            return new_val
        raise ValueError(f"Setting '{clean_key}' is not a boolean flag (current type: {type(current_val).__name__}).")

    def inspect_setting(self, key: str) -> Optional[Dict[str, Any]]:
        """Returns deep technical and operational metadata for a specific setting."""
        clean_key = key.strip()
        if clean_key not in SETTING_REGISTRY:
            return None
        meta = SETTING_REGISTRY[clean_key]
        return {
            "key": meta.key,
            "category": meta.category,
            "label": meta.label,
            "type": meta.value_type,
            "current_value": self.get(meta.key),
            "default_value": meta.default,
            "choices": meta.choices,
            "range": meta.range_bounds,
            "description": meta.description,
            "impact": meta.impact,
            "recommendation": meta.recommendation
        }

    def apply_profile(self, profile_name: str) -> Dict[str, Any]:
        """Applies a curated developer preset profile."""
        clean_name = profile_name.lower().strip()
        if clean_name not in PROFILES:
            valid_keys = ", ".join(PROFILES.keys())
            raise ValueError(f"Unknown profile '{profile_name}'. Available profiles: {valid_keys}")

        profile = PROFILES[clean_name]
        cfg = self.load_config()
        cfg["active_profile"] = clean_name
        for k, v in profile["settings"].items():
            cfg[k] = v
        self.save_config(cfg)
        return profile

    def get_active_profile_info(self) -> Dict[str, Any]:
        """Returns metadata for the currently active profile."""
        cfg = self.load_config()
        p_name = cfg.get("active_profile", "builder")
        return PROFILES.get(p_name, PROFILES["builder"])

    def get_organized_settings(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns structured, developer-friendly groups of settings with explanations."""
        cfg = self.load_config()
        categories = [
            CAT_PERFORMANCE,
            CAT_COGNITIVE,
            CAT_RESILIENCE,
            CAT_SECURITY,
            CAT_DEV_EXP
        ]
        organized: Dict[str, List[Dict[str, Any]]] = {c: [] for c in categories}
        for key, defn in SETTING_REGISTRY.items():
            val = cfg.get(key, defn.default)
            disp_val = val
            if defn.value_type == "int" and key.endswith("_s"):
                disp_val = f"{val}s"
            elif defn.value_type == "str" and not val:
                disp_val = "(Inherited / None)"

            organized[defn.category].append({
                "key": key,
                "name": defn.label,
                "val": val,
                "display_val": disp_val,
                "type": defn.value_type,
                "desc": defn.description,
                "impact": defn.impact,
                "recommendation": defn.recommendation
            })
        return organized

    def resolve_model_and_provider(self, requested_model: Optional[str] = None) -> Dict[str, Any]:
        """Infers provider, endpoint, and credentials for any given or default model name."""
        cfg = self.load_config()
        
        # If offline_mode is forced, route to local
        if cfg.get("offline_mode", False):
            return {
                "model": requested_model or "local-model",
                "provider": "lm_studio",
                "endpoint": cfg.get("provider_endpoints", {}).get("lm_studio", "http://localhost:1234/v1"),
                "api_key": "",
                "enable_caching": False
            }

        raw_model = requested_model or os.getenv("PRUBETH_MODEL") or cfg.get("default_model", "gemini-2.5-pro")
        model = MODEL_ALIASES.get(raw_model.lower().strip(), raw_model)
        
        m_lower = model.lower()
        def_provider = cfg.get("default_provider", "google")
        keys = cfg.get("api_keys", {})
        has_openrouter_key = bool(keys.get("openrouter") or os.getenv("OPENROUTER_API_KEY"))

        if "/" in model or ":free" in m_lower:
            provider = "openrouter"
        elif requested_model is None and def_provider == "openrouter" and has_openrouter_key:
            provider = "openrouter"
            if model in ["o3-mini", "o1", "o1-mini", "o1-preview", "gpt-4o", "gpt-4o-mini"]:
                model = f"openai/{model}"
            elif model in ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]:
                model = f"anthropic/{model}"
            elif model in ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash-exp"]:
                model = f"google/{model}"
            elif "deepseek" in model and not model.startswith("deepseek/"):
                model = f"deepseek/{model}"
        elif "gemini" in m_lower or "gemma" in m_lower:
            provider = "google"
        elif "claude" in m_lower:
            provider = "anthropic"
        elif "deepseek" in m_lower:
            provider = "deepseek"
        elif "groq" in m_lower:
            provider = "groq"
        elif "gpt" in m_lower or "o1" in m_lower or "o3" in m_lower:
            provider = "openai"
        elif "qwen" in m_lower or "llama" in m_lower or "mistral" in m_lower or "local" in m_lower:
            provider = "lm_studio"
        else:
            provider = def_provider

        env_map = {
            "google": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY"
        }
        api_key = os.getenv(env_map.get(provider, ""), "")
        if not api_key:
            api_key = cfg.get("api_keys", {}).get(provider, "")

        if provider == "google" and not api_key:
            for env_path in [self.config_dir / ".env", Path.cwd() / ".env"]:
                if env_path.exists():
                    try:
                        with open(env_path, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.startswith("GEMINI_API_KEY="):
                                    api_key = line.split("=", 1)[1].strip()
                                    break
                    except Exception:
                        pass
                if api_key:
                    break

        endpoint = cfg.get("provider_endpoints", {}).get(provider, "")
        return {
            "model": model,
            "provider": provider,
            "endpoint": endpoint,
            "api_key": api_key,
            "enable_caching": cfg.get("enable_prompt_caching", True),
            "enable_context_caching": cfg.get("enable_context_caching", True),
            "context_cache_ttl_s": int(cfg.get("context_cache_ttl_s", 300)),
            "anthropic_cache_turns": int(cfg.get("anthropic_cache_turns", 2)),
            "prompt_cache_min_tokens": int(cfg.get("prompt_cache_min_tokens", 1024)),
            "thinking_budget": int(cfg.get("thinking_budget", 2048)),
            "reasoning_effort": str(cfg.get("reasoning_effort", "medium"))
        }
