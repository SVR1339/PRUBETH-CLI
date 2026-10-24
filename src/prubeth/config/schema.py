"""PRUBETH Configuration Schema, Typings, and Settings Metadata Registry.

Provides rigorous typing, descriptive impact analysis, validation rules,
and recommendations for all developer options.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass

@dataclass
class SettingDefinition:
    key: str
    category: str
    label: str
    value_type: str  # "bool", "int", "str", "choice"
    default: Any
    choices: Optional[List[str]] = None
    range_bounds: Optional[Tuple[int, int]] = None
    description: str = ""
    impact: str = ""
    recommendation: str = ""
    restart_required: bool = False

# Consistent Categories
CAT_PERFORMANCE = "⚡ Core Performance & Acceleration"
CAT_COGNITIVE = "🧠 Cognitive Intelligence & Routing"
CAT_RESILIENCE = "🛡️ Plan B & Autonomous Resilience"
CAT_SECURITY = "🔒 Security, Sandboxing & Integrity"
CAT_DEV_EXP = "🔧 Developer Experience & Observability"

SETTING_REGISTRY: Dict[str, SettingDefinition] = {
    # 1. Performance & Acceleration
    "enable_prompt_caching": SettingDefinition(
        key="enable_prompt_caching",
        category=CAT_PERFORMANCE,
        label="Prefix-Stable Prompt Caching",
        value_type="bool",
        default=True,
        description="Maintains system prompt, tools, and repo skeleton byte-identical at the head of every call to leverage provider KV-cache reuse.",
        impact="Reduces Time-to-First-Token (TTFT) by up to 75% on Gemini and saves up to 90% cache read input costs on Claude/DeepSeek.",
        recommendation="Always ON for remote LLM providers (Gemini, Claude, DeepSeek)."
    ),
    "watchdog_timeout_s": SettingDefinition(
        key="watchdog_timeout_s",
        category=CAT_PERFORMANCE,
        label="Subprocess Execution Watchdog",
        value_type="int",
        default=45,
        range_bounds=(5, 300),
        description="Maximum execution seconds allocated to any shell command, build step, or test runner before terminating the child process.",
        impact="Prevents the agent from freezing indefinitely on interactive stdin prompts, infinite loops, or hanging test servers.",
        recommendation="30-45s for standard development; 90-120s for slow builds or local GGUF models."
    ),
    "max_execution_turns": SettingDefinition(
        key="max_execution_turns",
        category=CAT_PERFORMANCE,
        label="Max Autonomous Turns Budget",
        value_type="int",
        default=10,
        range_bounds=(3, 30),
        description="The upper limit of autonomous tool calls and reasoning cycles allowed per task before forcing verification or user review.",
        impact="Guards against runaway token burn and looping hallucination spirals.",
        recommendation="8-12 turns for typical feature tasks; 15-20 turns for complex multi-module refactoring."
    ),
    "stream_tokens": SettingDefinition(
        key="stream_tokens",
        category=CAT_PERFORMANCE,
        label="Real-Time Token Streaming",
        value_type="bool",
        default=True,
        description="Streams LLM output deltas and reasoning tokens directly into the terminal or IDE named pipe in real time.",
        impact="Zero perceptible latency wait; developer observes agent thoughts as they emerge.",
        recommendation="Always ON for interactive terminal and IDE use."
    ),
    "cloud_timeout_s": SettingDefinition(
        key="cloud_timeout_s",
        category=CAT_PERFORMANCE,
        label="Cloud Timeout & Local Auto-Switch",
        value_type="int",
        default=12,
        range_bounds=(3, 60),
        description="Maximum seconds allowed for remote cloud model inference before declaring latency timeout and automatically pivoting to local downloaded & loaded models.",
        impact="Eliminates indefinite developer wait when remote cloud APIs stall, queue, or experience degraded performance.",
        recommendation="10-15s for high-velocity coding with instant local fallback."
    ),

    # 2. Cognitive Models & Routing
    "default_model": SettingDefinition(
        key="default_model",
        category=CAT_COGNITIVE,
        label="Primary Autonomous AI Model",
        value_type="str",
        default="gemini-3.1-pro-preview",
        description="The main foundation model invoked for architecture analysis, tool planning, code authoring, and self-healing.",
        impact="Directly dictates reasoning depth, coding quality, and generation velocity.",
        recommendation="gemini-3.1-pro-preview for highest reasoning capability; openrouter/free for dynamic frontier open-weights."
    ),
    "default_provider": SettingDefinition(
        key="default_provider",
        category=CAT_COGNITIVE,
        label="Default Provider Gateway",
        value_type="choice",
        default="google",
        choices=["google", "anthropic", "openai", "deepseek", "groq", "lm_studio", "ollama", "openrouter"],
        description="Target backend routing protocol (Google v1beta, Anthropic Messages API, or OpenAI-compatible endpoint).",
        impact="Determines authentication scheme, API endpoints, and caching protocols.",
        recommendation="google for Gemini; lm_studio for offline privacy."
    ),
    "planner_model": SettingDefinition(
        key="planner_model",
        category=CAT_COGNITIVE,
        label="Specialized Planning Model Override",
        value_type="str",
        default="",
        description="Optional high-reasoning model override invoked strictly during the INITIAL PLANNING phase (e.g. DeepSeek-R1 or o3-mini).",
        impact="Allows pairing an ultra-deep thinking planner with an ultra-fast coder for optimum speed and cost.",
        recommendation="Leave empty to inherit default_model, or specify a reasoning model for complex refactoring."
    ),
    "coder_model": SettingDefinition(
        key="coder_model",
        category=CAT_COGNITIVE,
        label="Specialized Coding Model Override",
        value_type="str",
        default="",
        description="Optional fast code-synthesis model override invoked strictly during file editing and tool execution turns.",
        impact="Minimizes cost and accelerates execution speed during repetitive edits.",
        recommendation="Leave empty to inherit default_model."
    ),

    # 3. Plan B & Autonomous Resilience
    "speculative_plan_b": SettingDefinition(
        key="speculative_plan_b",
        category=CAT_RESILIENCE,
        label="Speculative Plan B Drafting",
        value_type="bool",
        default=True,
        description="Directs the runtime to generate an orthogonal contingency plan (Plan B) during the initial planning turn at negligible marginal token cost.",
        impact="Eliminates developer stoppage: if Plan A fails tests after diagnostic healing, the agent immediately pivots to Plan B.",
        recommendation="Always ON. This is the cornerstone of PRUBETH's zero-stoppage guarantee."
    ),
    "plan_b_strategy": SettingDefinition(
        key="plan_b_strategy",
        category=CAT_RESILIENCE,
        label="Plan B Failover Action",
        value_type="choice",
        default="auto_pivot",
        choices=["auto_pivot", "fallback_model", "ask_developer"],
        description="Determines how the runtime handles a complete Plan A exhaustion.",
        impact="auto_pivot rolls back files and executes Plan B autonomously. fallback_model switches from cloud to local GGUF. ask_developer pauses for user input.",
        recommendation="auto_pivot for autonomous hands-free velocity; ask_developer for critical production systems."
    ),
    "self_healing_retries": SettingDefinition(
        key="self_healing_retries",
        category=CAT_RESILIENCE,
        label="Self-Healing Diagnostic Retries",
        value_type="int",
        default=3,
        range_bounds=(1, 10),
        description="Number of consecutive compiler/test error diagnosis and repair loops allowed before triggering contingency failover.",
        impact="Allows the agent to autonomously fix syntax typos, missing imports, and logic mismatches using compiler feedback.",
        recommendation="3 retries for balanced velocity; 5 for complex refactoring."
    ),
    "auto_checkpoint": SettingDefinition(
        key="auto_checkpoint",
        category=CAT_RESILIENCE,
        label="Shadow Filesystem Checkpointing",
        value_type="bool",
        default=True,
        description="Captures pure-Python filesystem snapshots (.prubeth/snapshots/) before any file modifications without requiring Git.",
        impact="Guarantees safe state restoration even if host machine lacks Git or operates on uncommitted dirty trees.",
        recommendation="Always ON."
    ),
    "auto_rollback_on_failure": SettingDefinition(
        key="auto_rollback_on_failure",
        category=CAT_RESILIENCE,
        label="Atomic Workspace Rollback",
        value_type="bool",
        default=True,
        description="Reverts the workspace to its pristine pre-task snapshot if all plans and recovery attempts fail verification.",
        impact="Leaves the developer's repository in a clean, buildable state rather than leaving corrupted or half-edited files behind.",
        recommendation="Always ON."
    ),

    # 4. Security, Sandboxing & Integrity
    "strict_sandbox": SettingDefinition(
        key="strict_sandbox",
        category=CAT_SECURITY,
        label="Workspace Path Jail",
        value_type="bool",
        default=True,
        description="Restricts all tool-level file reads, writes, and shell operations strictly inside the active workspace directory.",
        impact="Blocks path traversal attacks (e.g. ../../Windows/System32) and prevents unintended modification of external user files.",
        recommendation="Always ON."
    ),
    "auto_approve_actions": SettingDefinition(
        key="auto_approve_actions",
        category=CAT_SECURITY,
        label="Autonomous Execution Mode",
        value_type="bool",
        default=True,
        description="Allows the agent to execute non-destructive tools (file reads, edits, safe tests) without interactive approval prompts.",
        impact="Enables unattended, high-speed autonomous execution. Set to False if human verification is required before edits.",
        recommendation="ON for Builder profile; OFF for Safe-Audit profile."
    ),
    "offline_mode": SettingDefinition(
        key="offline_mode",
        category=CAT_SECURITY,
        label="Air-Gapped Offline Mode",
        value_type="bool",
        default=False,
        description="Cuts off all cloud egress and directs all model calls strictly to local localhost inference engines (LM Studio / Ollama).",
        impact="Guarantees zero proprietary code or sensitive data ever leaves the local machine.",
        recommendation="ON for classified or NDA air-gapped codebases; OFF for maximum frontier model reasoning."
    ),

    # 5. Developer Experience & Observability
    "developer_mode": SettingDefinition(
        key="developer_mode",
        category=CAT_DEV_EXP,
        label="Elite Developer Diagnostics & HUD",
        value_type="bool",
        default=True,
        description="Displays real-time hardware telemetry, model TTFT latency, token counts, and state machine transitions in the CLI.",
        impact="Provides total transparency into what the agent is doing, why it made decisions, and how fast the backend is responding.",
        recommendation="Always ON."
    ),
    "log_level": SettingDefinition(
        key="log_level",
        category=CAT_DEV_EXP,
        label="Diagnostic Logging Verbosity",
        value_type="choice",
        default="INFO",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        description="Granularity of execution logs saved to .prubeth/logs/ and SQLite database.",
        impact="DEBUG captures raw HTTP payloads and tool inputs; INFO captures state changes and execution milestones.",
        recommendation="INFO for daily development; DEBUG for troubleshooting."
    ),
    "verbose_tool_output": SettingDefinition(
        key="verbose_tool_output",
        category=CAT_DEV_EXP,
        label="Unclipped Tool Output",
        value_type="bool",
        default=False,
        description="Prints unclipped stdout and stderr from commands instead of intelligent 10-line summaries.",
        impact="Helpful when diagnosing massive compiler outputs or deeply nested stack traces.",
        recommendation="OFF for clean terminal display; ON during compiler debugging."
    )
}

def validate_setting_value(key: str, value: Any) -> Tuple[bool, Any, str]:
    """Validates and coerces setting value according to schema."""
    if key not in SETTING_REGISTRY:
        return False, None, f"Unknown setting '{key}'. Run 'prubeth settings' to see available keys."

    meta = SETTING_REGISTRY[key]
    
    # 1. Boolean validation
    if meta.value_type == "bool":
        if isinstance(value, bool):
            return True, value, ""
        if isinstance(value, str):
            clean = value.lower().strip()
            if clean in ["true", "1", "yes", "on", "enable", "enabled"]:
                return True, True, ""
            if clean in ["false", "0", "no", "off", "disable", "disabled"]:
                return True, False, ""
        return False, None, f"Setting '{key}' expects a boolean (true/false, on/off)."

    # 2. Integer validation
    if meta.value_type == "int":
        try:
            val_int = int(value)
            if meta.range_bounds:
                min_b, max_b = meta.range_bounds
                if not (min_b <= val_int <= max_b):
                    return False, None, f"Setting '{key}' must be between {min_b} and {max_b} (got {val_int})."
            return True, val_int, ""
        except (ValueError, TypeError):
            return False, None, f"Setting '{key}' expects an integer."

    # 3. Choice validation
    if meta.value_type == "choice":
        val_str = str(value).strip().lower()
        if meta.choices and val_str not in [c.lower() for c in meta.choices]:
            choices_str = ", ".join(meta.choices)
            return False, None, f"Setting '{key}' must be one of: {choices_str} (got '{val_str}')."
        return True, val_str, ""

    # 4. String validation
    val_str = str(value).strip() if value is not None else ""
    return True, val_str, ""
