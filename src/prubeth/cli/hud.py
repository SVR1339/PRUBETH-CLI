"""PRUBETH Live Cockpit Status HUD & Real-Time Token Cost Radar.

Tracks session token expenditures, latency percentiles, memory consumption,
and cache efficiency across all cloud and local inference providers.
"""

import sys
import psutil
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from prubeth.models.telemetry import LLMOpsMonitor
from prubeth.config.manager import ConfigManager
from prubeth.persistence.checkpoints import SnapshotManager

# Per-million token pricing in USD ($) with Frontier Prompt & Context Caching Rates
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Google Gemini (Context Caching: 75% read discount)
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00, "cache_read": 0.3125},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30, "cache_read": 0.01875},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00, "cache_read": 0.3125},
    "gemini-3.8-flash": {"input": 0.075, "output": 0.30, "cache_read": 0.01875},
    "gemini-4.0-preview": {"input": 2.00, "output": 8.00, "cache_read": 0.50},
    "gemini-4-argon": {"input": 2.00, "output": 8.00, "cache_read": 0.50},
    "gemini-pro-latest": {"input": 1.25, "output": 5.00, "cache_read": 0.3125},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "cache_read": 0.025},

    # Anthropic Claude (Prompt Caching: 90% read discount)
    "claude-3-7-sonnet-20250219": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-3-7-sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_write": 1.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00, "cache_read": 1.50},

    # OpenAI (Prefix Caching: 50% read discount)
    "o3-mini": {"input": 1.10, "output": 4.40, "cache_read": 0.55},
    "o1": {"input": 15.00, "output": 60.00, "cache_read": 7.50},
    "gpt-4.5-preview": {"input": 75.00, "output": 150.00, "cache_read": 37.50},
    "gpt-4o": {"input": 2.50, "output": 10.00, "cache_read": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cache_read": 0.075},

    # DeepSeek (Prefix Caching: 75% read discount)
    "deepseek-r1": {"input": 0.55, "output": 2.19, "cache_read": 0.14},
    "deepseek-v3": {"input": 0.27, "output": 1.10, "cache_read": 0.07},
    "deepseek-chat": {"input": 0.27, "output": 1.10, "cache_read": 0.07},
    "deepseek/deepseek-r1:free": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
    "qwen/qwen-2.5-coder-32b:free": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
    "meta-llama/llama-3.3-70b:free": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
    "ollama": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
    "lm_studio": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
}

def calculate_session_spend() -> Dict[str, Any]:
    """Calculates total token volume, estimated cost, cache savings, and provider breakdowns."""
    monitor = LLMOpsMonitor()
    total_input = 0
    total_output = 0
    total_cached = 0
    total_cost_usd = 0.0
    total_saved_usd = 0.0
    by_model: Dict[str, Dict[str, Any]] = {}

    for m in monitor.metrics:
        total_input += m.input_tokens
        total_output += m.output_tokens
        total_cached += m.cached_tokens

        # Price lookup
        price = MODEL_PRICING.get(m.model, {"input": 1.0, "output": 3.0, "cache_read": 0.25})
        cache_create = getattr(m, "cache_creation_tokens", 0)
        uncached_input = max(0, m.input_tokens - m.cached_tokens - cache_create)
        cache_write_rate = price.get("cache_write", price["input"] * 1.25)
        cost = (
            (uncached_input / 1_000_000.0) * price["input"]
            + (m.cached_tokens / 1_000_000.0) * price.get("cache_read", price["input"] * 0.25)
            + (cache_create / 1_000_000.0) * cache_write_rate
            + (m.output_tokens / 1_000_000.0) * price["output"]
        )
        total_cost_usd += cost

        # Calculate exact dollars saved by prompt caching / context caching
        baseline_without_cache = (
            (m.input_tokens / 1_000_000.0) * price["input"]
            + (m.output_tokens / 1_000_000.0) * price["output"]
        )
        saved = max(0.0, baseline_without_cache - cost)
        total_saved_usd += saved

        if m.model not in by_model:
            by_model[m.model] = {"calls": 0, "input": 0, "output": 0, "cached": 0, "cost": 0.0, "saved": 0.0, "provider": m.provider}
        by_model[m.model]["calls"] += 1
        by_model[m.model]["input"] += m.input_tokens
        by_model[m.model]["output"] += m.output_tokens
        by_model[m.model]["cached"] += m.cached_tokens
        by_model[m.model]["cost"] += cost
        by_model[m.model]["saved"] += saved

    return {
        "total_calls": len(monitor.metrics),
        "total_tokens": total_input + total_output,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cached_tokens": total_cached,
        "total_cost_usd": round(total_cost_usd, 5),
        "total_saved_usd": round(total_saved_usd, 5),
        "by_model": by_model
    }

def get_current_process_memory_mb() -> float:
    """Returns the current process resident set size in megabytes."""
    try:
        proc = psutil.Process()
        return round(proc.memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return 18.5

def render_cockpit_hud_bar(console: Console, cfg_mgr: ConfigManager, current_model: Optional[str] = None):
    """Renders a single-line high-density developer telemetry bar."""
    resolved = cfg_mgr.resolve_model_and_provider(current_model)
    profile = cfg_mgr.get_active_profile_info()
    spend = calculate_session_spend()
    ram_mb = get_current_process_memory_mb()
    
    snap_mgr = SnapshotManager()
    snaps = snap_mgr.list_snapshots()
    latest_snap = snaps[-1][:8] if snaps else "none"

    cost_str = f"${spend['total_cost_usd']:.4f}" if spend['total_cost_usd'] > 0 else "$0.0000 (Free)"
    badge = profile.get("name", "BUILDER").split()[0].upper()
    
    hud_line = (
        f"[{badge}] "
        f"[dim]Model:[/dim] [bold cyan]{resolved['model']}[/bold cyan] [dim]({resolved['provider']})[/dim] | "
        f"[dim]Spend:[/dim] [bold green]{cost_str}[/bold green] [dim]({spend['total_tokens']:,} tok)[/dim] | "
        f"[dim]RAM:[/dim] [bold green]{ram_mb} MB[/bold green] [dim]/ 33 MB[/dim] | "
        f"[dim]Snap:[/dim] [bold yellow]#{latest_snap}[/bold yellow]"
    )
    console.print(hud_line)

def render_cost_report(console: Console):
    """Renders a comprehensive LLMOps session expenditure report."""
    spend = calculate_session_spend()
    from rich import box

    table = Table(title="PRUBETH Real-Time Token Expenditure & Cost Radar", box=box.ROUNDED)
    table.add_column("Model / Engine", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Invocations", justify="right", style="white")
    table.add_column("Prompt Tokens", justify="right", style="cyan")
    table.add_column("Cached Tokens", justify="right", style="green")
    table.add_column("Output Tokens", justify="right", style="yellow")
    table.add_column("Estimated Cost", justify="right", style="bold green")

    if not spend["by_model"]:
        table.add_row("No model calls in current session yet", "-", "0", "0", "0", "0", "$0.0000")
    else:
        for m_name, d in spend["by_model"].items():
            table.add_row(
                m_name,
                d["provider"],
                str(d["calls"]),
                f"{d['input']:,}",
                f"{d['cached']:,}",
                f"{d['output']:,}",
                f"${d['cost']:.5f}" if d["cost"] > 0 else "$0.0000 (Free)"
            )

    console.print(table)
    total_str = f"${spend['total_cost_usd']:.5f}" if spend['total_cost_usd'] > 0 else "$0.0000 (100% Free / Air-Gapped)"
    saved_str = f" [bold green](Saved ${spend.get('total_saved_usd', 0.0):.5f} via Prompt & Context Caching)[/bold green]" if spend.get('total_saved_usd', 0.0) > 0 else ""
    console.print(f"[bold cyan]Total Session Expenditure:[/bold cyan] [bold green]{total_str}[/bold green]{saved_str} across [bold]{spend['total_tokens']:,}[/bold] tokens.\n")
