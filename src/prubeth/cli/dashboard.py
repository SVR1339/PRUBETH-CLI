"""PRUBETH Elite Visual Settings & Performance Builder Dashboard.

Renders rich, intuitive, and impressive terminal user interfaces for
developer configuration, hardware telemetry, and System Performance Index (SPI).
"""

import os
import sys
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Maintain high-clarity geometry with zero font blur (PRINCE Stage 3 Standard)
console = Console(legacy_windows=False)

from prubeth.config.manager import ConfigManager, PROFILES
from prubeth.performance.builder import PerformanceBuilder, render_score_bar

def render_performance_dashboard(cfg_mgr: ConfigManager):
    """Renders the comprehensive Elite Developer Settings & Performance HUD."""
    cfg = cfg_mgr.load_config()
    profile = cfg_mgr.get_active_profile_info()
    resolved = cfg_mgr.resolve_model_and_provider()

    builder = PerformanceBuilder(cfg_mgr)
    env = builder.probe_environment()
    spi = builder.compute_spi(cfg)

    # 1. Top HUD: System Performance Index & Telemetry Matrix
    hud_table = Table.grid(expand=True)
    hud_table.add_column(ratio=3)
    hud_table.add_column(ratio=2)

    left_text = Text()
    left_text.append("PRUBETH Autonomous Engineering Engine\n", style="bold cyan")
    left_text.append(f"Active Profile: ", style="dim")
    left_text.append(f"{profile['badge']} — {profile['name']}\n", style="bold green")
    left_text.append(f"Autonomy Rating: ", style="dim")
    left_text.append(f"{spi['autonomy_tier']}\n", style="bold cyan")
    left_text.append(f"Primary Cognitive Model: ", style="dim")
    left_text.append(f"{resolved['model']} ({resolved['provider']})\n", style="bold white")
    caching_status = "ENABLED (Prefix KV Cache Pinned)" if resolved.get("enable_caching") else "DISABLED"
    left_text.append(f"Prompt Caching: ", style="dim")
    left_text.append(f"{caching_status}\n", style="bold green" if resolved.get("enable_caching") else "yellow")

    right_bars = Table(show_header=False, box=None, padding=(0, 1))
    right_bars.add_column("Dimension", style="dim", width=20)
    right_bars.add_column("Score", width=26)
    right_bars.add_row("System Perf (SPI):", render_score_bar(spi["composite_spi"]))
    right_bars.add_row("Execution Velocity:", render_score_bar(spi["velocity"]))
    right_bars.add_row("Plan B Resilience:", render_score_bar(spi["resilience"]))
    right_bars.add_row("Workspace Security:", render_score_bar(spi["security"]))
    right_bars.add_row("RAM Footprint:", Text(f"~{env['process_memory_mb']} MB (CPU-Only)", style="bold green"))

    hud_table.add_row(left_panel := left_text, right_bars)
    console.print(Panel(hud_table, title="[bold white]PRUBETH PERFORMANCE BUILDER & MASTER SETTINGS HUD[/bold white]", border_style="cyan"))

    # 2. Profiles Selector Overview
    p_table = Table(show_lines=False, box=None, expand=True)
    p_table.add_column("Apply Command", style="bold cyan", width=34)
    p_table.add_column("Preset Profile", style="bold", width=26)
    p_table.add_column("Optimization & Environment Focus", style="dim")
    p_table.add_column("State", justify="center", width=14)

    active_p_key = cfg.get("active_profile", "builder")
    for key, data in PROFILES.items():
        is_active = (key == active_p_key)
        mark = "[bold green]● CURRENT[/bold green]" if is_active else "[dim]○ Available[/dim]"
        p_table.add_row(f"prubeth profile apply {key}", data["name"], data["desc"], mark)

    console.print(Panel(p_table, title="[bold]Curated Developer Profiles[/bold]", border_style="dim"))

    # 3. Categorized Settings Groups
    organized = cfg_mgr.get_organized_settings()
    for category, settings_list in organized.items():
        cat_table = Table(expand=True, box=None)
        cat_table.add_column("Setting Key", style="cyan", width=25)
        cat_table.add_column("Feature / Capability", style="bold white", width=28)
        cat_table.add_column("Value", justify="center", width=16)
        cat_table.add_column("Engineering Impact & Advantage", style="dim")

        for item in settings_list:
            v = item["val"]
            if isinstance(v, bool):
                badge = "[bold green]ON (Active)[/bold green]" if v else "[bold red]OFF (Inactive)[/bold red]"
            else:
                badge = f"[bold magenta]{item.get('display_val', v)}[/bold magenta]"
            cat_table.add_row(item["key"], item["name"], badge, item["impact"])

        console.print(Panel(cat_table, title=f"[bold]{category}[/bold]", border_style="blue"))

    # 4. Quick Action Guidance
    tips = (
        "[bold cyan]Quick Controls & Inspection:[/bold cyan]\n"
        "  • Inspect Any Setting: [bold]prubeth settings inspect <setting_key>[/bold] (deep impact, default, and guidance)\n"
        "  • Launch Perf Builder: [bold]prubeth tune[/bold] (hardware telemetry, SPI benchmark & auto-recommendations)\n"
        "  • Apply Profile:       [bold]prubeth profile apply <builder | deep-reasoning | local-airgap | safe-audit>[/bold]\n"
        "  • Toggle Option:       [bold]prubeth toggle <setting_key>[/bold] (e.g. prubeth toggle speculative_plan_b)\n"
        "  • Set Direct Value:    [bold]prubeth set <setting_key> <value>[/bold] (e.g. prubeth set default_model deepseek-chat)\n"
        "  • Reset Factory:       [bold]prubeth reset[/bold] (reverts all settings to default factory profile)"
    )
    console.print(Panel(tips, border_style="dim green"))

def render_setting_inspection(cfg_mgr: ConfigManager, key: str):
    """Renders a deep technical and operational breakdown card for an individual setting."""
    meta = cfg_mgr.inspect_setting(key)
    if not meta:
        console.print(f"[bold red]Unknown Setting:[/bold red] '{key}'. Run 'prubeth settings' to see all valid keys.")
        return

    table = Table(show_header=False, box=None, expand=True)
    table.add_column("Property", style="bold cyan", width=22)
    table.add_column("Details", style="white")

    table.add_row("Setting Key:", f"[bold]{meta['key']}[/bold]")
    table.add_row("Feature Label:", f"[bold green]{meta['label']}[/bold green]")
    table.add_row("Category:", meta["category"])
    table.add_row("Value Type:", meta["type"].upper())

    # Current value with styling
    cur_v = meta["current_value"]
    if isinstance(cur_v, bool):
        cur_disp = "[bold green]ON (True)[/bold green]" if cur_v else "[bold red]OFF (False)[/bold red]"
    else:
        cur_disp = f"[bold magenta]{cur_v}[/bold magenta]"
    table.add_row("Current Value:", cur_disp)
    table.add_row("Factory Default:", str(meta["default_value"]))
    table.add_row("Elite Recommendation:", f"[bold yellow]{meta['recommendation']}[/bold yellow]")

    if meta.get("choices"):
        table.add_row("Allowed Choices:", ", ".join(meta["choices"]))
    if meta.get("range"):
        table.add_row("Valid Range:", f"{meta['range'][0]} to {meta['range'][1]}")

    table.add_row("Explanation:", meta["description"])
    table.add_row("Engineering Impact:", f"[italic]{meta['impact']}[/italic]")

    action_cmd = f"prubeth toggle {key}" if meta["type"] == "bool" else f"prubeth set {key} <value>"
    table.add_row("Quick Action:", f"[bold cyan]{action_cmd}[/bold cyan]")

    console.print(Panel(table, title=f"[bold white]SETTING INSPECTOR: {meta['key']}[/bold white]", border_style="cyan"))

def render_profile_switch_confirmation(profile_name: str, profile_data: Dict[str, Any]):
    """Renders a visual badge when a profile is switched."""
    badge = profile_data.get("badge", profile_name.upper())
    name = profile_data.get("name", profile_name)
    desc = profile_data.get("desc", "")
    console.print(f"\n[bold green]✓ APPLIED PROFILE:[/bold green] [bold cyan]{badge}[/bold cyan] ({name})")
    console.print(f"[dim]{desc}[/dim]\n")
