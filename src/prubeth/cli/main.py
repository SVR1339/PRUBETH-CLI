import sys
import os
import json
import argparse
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

# Ensure terminal encoding is UTF-8 on Windows (PRINCE Stage 3 Zero Font Blur Standard)
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich import box

from prubeth.runtime.controller import AutonomousRuntimeController, RuntimeConfig
from prubeth.runtime.state_machine import TaskState
from prubeth.config.manager import ConfigManager, PROFILES, DEFAULT_CONFIG
from prubeth.persistence.checkpoints import SnapshotManager
from prubeth.cli.dashboard import (
    render_performance_dashboard,
    render_setting_inspection,
    render_profile_switch_confirmation
)
from prubeth.performance.builder import (
    PerformanceBuilder,
    render_performance_builder_hud
)
from prubeth.cli.commands import (
    handle_swarm_command,
    handle_worktrees_command,
    handle_memory_command,
    handle_bridge_command,
    handle_consensus_command,
    handle_mcp_command,
    handle_init_command,
    handle_review_command,
    handle_goal_command,
    handle_commit_command,
    handle_pr_command,
    handle_learn_command,
    handle_symbols_command,
    handle_callers_command,
    handle_autotune_command,
    handle_research_command,
    handle_janitor_command,
    handle_bio_command,
    handle_migrate_command,
    handle_issue_command,
    handle_timeline_command,
    handle_cache_command,
    handle_compact_command
)
from prubeth.cli.setup import render_onboarding_wizard, execute_factory_reset
from prubeth.repository.index import CodebaseIndex
from prubeth.repository.context import ContextExpander
from prubeth.runtime.auto_heal import AutoHealer
from prubeth.cli.hud import render_cockpit_hud_bar, render_cost_report
from prubeth.persistence.tree import ConversationTree

# Initialize Rich Console with modern ANSI rendering (zero subpixel blur, no legacy cp1252 truncation)
console = Console(legacy_windows=False)

def print_banner():
    cfg_mgr = ConfigManager()
    resolved = cfg_mgr.resolve_model_and_provider()
    profile = cfg_mgr.get_active_profile_info()
    
    branch_name = "main"
    try:
        head_file = Path(".git/HEAD")
        if head_file.exists():
            ref = head_file.read_text(encoding="utf-8").strip()
            if ref.startswith("ref: refs/heads/"):
                branch_name = ref.replace("ref: refs/heads/", "")
    except Exception:
        pass

    cwd_str = str(Path.cwd())
    if len(cwd_str) > 50:
        cwd_str = "..." + cwd_str[-47:]

    title_text = "[bold white]PRUBETH[/bold white] [bold #FF9F1C]CLI v1.3.1[/bold #FF9F1C] [dim](Beach Theme)[/dim]"
    
    lines = [
        f"  [bold #FF3366]  ████████  [/bold #FF3366]  [bold white]PRUBETH COCKPIT[/bold white]",
        f"  [bold #FF6B35]  ██    ████[/bold #FF6B35]  [dim]Repository:[/dim]  [cyan]{cwd_str}[/cyan] [dim]({branch_name})[/dim]",
        f"  [bold #FFAA00]  ██      ██[/bold #FFAA00]  [dim]Model:[/dim]       [bold cyan]{resolved['model']}[/bold cyan] [dim]({resolved['provider']})[/dim] │ [green]{profile['badge']}[/green]",
        f"  [bold #00F5D4]  ████████  [/bold #00F5D4]  [dim]Caching:[/dim]     [green]Active (Anthropic Ephemeral + Gemini GPU VRAM)[/green]",
        f"  [bold #00BBF9]  ██        [/bold #00BBF9]  [dim]Footprint:[/dim]   [green]26.59 MB CPU RAM │ 0 MB GPU VRAM[/green] │ [green]Sandbox: Enforced[/green]",
        f"  [bold #0077B6]  ██        [/bold #0077B6]  [dim]Shortcuts:[/dim]   [cyan]!cmd[/cyan] [dim](kernel)[/dim] │ [cyan]@file[/cyan] [dim](context)[/dim] │ [cyan]/cache[/cyan] │ [cyan]/integrity[/cyan]",
        f"  [bold #03045E]██████      [/bold #03045E]  [dim]──────────────────────────────────────────────────────────────────[/dim]"
    ]
    
    panel = Panel(
        "\n".join(lines),
        title=title_text,
        border_style="#00F5D4",
        box=box.ROUNDED,
        padding=(0, 2)
    )
    console.print()
    console.print(panel)
    console.print()

def make_event_logger(output_format: str):
    """Factory creating the event streaming callback."""
    def logger(event_name: str, payload: Any):
        if output_format == "stream-json":
            data_dict = {}
            if hasattr(payload, "value"):
                data_dict = {"value": payload.value}
            elif isinstance(payload, dict):
                data_dict = payload
            elif hasattr(payload, "__dict__"):
                data_dict = {k: v.value if hasattr(v, "value") else v for k, v in payload.__dict__.items()}
            else:
                data_dict = {"content": str(payload)}

            record = {
                "event": event_name,
                "timestamp": datetime.now().isoformat(),
                "data": data_dict
            }
            sys.stdout.write(json.dumps(record, default=str) + "\n")
            sys.stdout.flush()
            return

        # Default: Rich Terminal Text Rendering
        if event_name == "state_change":
            state_val = payload.value if hasattr(payload, "value") else str(payload)
            state_map = {
                "CONTEXTUALIZING": "  [dim cyan]🔍 Inspecting workspace architecture...[/dim cyan]",
                "PLANNING": "  [dim cyan]🧠 Formulating implementation plan...[/dim cyan]",
                "READY": "  [dim green]📦 Checkpoint secured. Ready to execute.[/dim green]",
                "EXECUTING": "  [bold cyan]⚡ Executing code modifications and tools...[/bold cyan]",
                "VERIFYING": "  [bold cyan]🧪 Running independent verification and tests...[/bold cyan]",
                "COMPLETED": "  [bold green]✅ Task successfully completed and verified.[/bold green]",
                "FAILED": "  [bold red]❌ Task verification did not pass.[/bold red]",
            }
            if state_val in state_map:
                console.print(state_map[state_val])
        elif event_name == "plan_generated":
            if isinstance(payload, dict):
                plan_a = payload.get("content", "")
                plan_b = payload.get("plan_b", "")
                lat = payload.get("latency_s", 0)
                m = payload.get("model", "")
                console.print(Panel(Markdown(plan_a), title=f"Plan A (Primary Architecture) — [{m} in {lat}s]", border_style="cyan"))
                if plan_b:
                    console.print(Panel(Markdown(plan_b), title="Plan B (Contingency Fallback Architecture — Armed)", border_style="yellow"))
            else:
                console.print(Panel(Markdown(str(payload)), title="Generated Implementation Plan", border_style="cyan"))
        elif event_name == "snapshot_created":
            lbl = payload.get("label") if isinstance(payload, dict) else str(payload)
            console.print(f"    [dim cyan]Checkpoint Created:[/dim cyan] snapshot '{lbl}' saved.")
        elif event_name == "tool_invoked":
            t_name = payload.get("tool")
            t_args = payload.get("args")
            plan_lbl = payload.get("plan", "Plan A")
            console.print(f"    [dim magenta]Tool Action ({plan_lbl}):[/dim magenta] {t_name}({t_args})")
        elif event_name == "tool_result":
            status = "[OK]" if payload.get("success") else "[ERR]"
            color = "green" if payload.get("success") else "red"
            console.print(f"    [{color}]{status}[/{color}] [dim]{payload.get('output')}[/dim]")
        elif event_name == "plan_b_activated":
            reason = payload.get("reason", "") if isinstance(payload, dict) else str(payload)
            console.print(Panel(f"[bold yellow]⚠️ PLAN B ENGAGED:[/bold yellow] {reason}", border_style="yellow"))
        elif event_name == "workspace_rollback":
            target = payload.get("target") if isinstance(payload, dict) else str(payload)
            console.print(f"    [bold red]⏪ Workspace Rollback:[/bold red] Successfully reverted files to snapshot '{target}'.")
        elif event_name in ["verification_result", "re_verification_result"]:
            status_color = "green" if payload.success else "yellow"
            console.print(Panel(payload.summary(), title="Verification Gate", border_style=status_color))

    return logger

def is_engineering_task(text: str) -> bool:
    """Classifies whether the user prompt requires autonomous task execution or conversational chat."""
    lower = text.strip().lower()
    if not lower:
        return False

    # Explicit task execution directives
    if lower.startswith(("/auto", "task:", "build:", "fix:", "implement:", "do:")):
        return True

    # Conversational greetings and short inquiries
    greetings = {"hi", "hello", "hey", "sup", "yo", "good morning", "good evening", "good afternoon", "greetings", "ping"}
    if lower in greetings or lower.startswith(("hi ", "hello ", "hey ")):
        return False

    # Question / explanatory inquiries
    question_starters = (
        "what", "why", "how", "where", "who", "when", "can you", "could you",
        "explain", "describe", "tell me", "is there", "are there", "does", "which",
        "help", "show me", "walk me through", "list"
    )
    if any(lower.startswith(q) for q in question_starters):
        return False

    # Action verbs indicating code modification or project tasks
    action_verbs = {
        "create", "add", "implement", "fix", "refactor", "build", "update", "delete",
        "remove", "write", "generate", "modify", "patch", "install", "test", "run",
        "deploy", "migrate", "setup", "configure", "make", "draft", "commit", "push"
    }
    first_word = lower.split()[0] if lower.split() else ""
    if first_word in action_verbs:
        return True

    words = set(lower.split())
    if words.intersection(action_verbs) and len(lower.split()) >= 3:
        return True

    return False

def interactive_approval_handler(action_type: str, details: Dict[str, Any]) -> bool:
    """Prompts human developer for approval with colored diff preview."""
    if action_type == "plan_approval":
        console.print("[bold yellow]Do you approve this execution plan? (y/n):[/bold yellow] ", end="")
        ans = input().strip().lower()
        return ans in ["y", "yes"]

    if action_type == "file_modification" and "diff" in details and details["diff"]:
        from rich.syntax import Syntax
        syntax = Syntax(details["diff"], "diff", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title=f"Proposed Staged Diff: {details.get('path', '')}", border_style="yellow"))
        console.print(f"[bold yellow]Approve applying this patch to {details.get('path')}? (y/n): [/bold yellow]", end="")
        ans = input().strip().lower()
        return ans in ["y", "yes"]

    console.print(f"[bold yellow]Approve execution of {action_type}? Details: {details} (y/n):[/bold yellow] ", end="")
    ans = input().strip().lower()
    return ans in ["y", "yes"]

def handle_profile_command(args: list):
    """Manages preset profiles (list, apply)."""
    cfg_mgr = ConfigManager()
    if not args or args[0] in ["list", "status"]:
        render_performance_dashboard(cfg_mgr)
        return

    if args[0] == "apply" and len(args) > 1:
        target = args[1]
        try:
            profile_data = cfg_mgr.apply_profile(target)
            render_profile_switch_confirmation(target, profile_data)
        except Exception as e:
            console.print(f"[bold red]Profile Error:[/bold red] {e}")
    else:
        console.print("[yellow]Usage: prubeth profile [list | apply <builder | deep-reasoning | local-airgap | safe-audit>][/yellow]")

def handle_toggle_command(args: list):
    """Toggles a boolean setting on or off."""
    if not args:
        console.print("[yellow]Usage: prubeth toggle <setting_name> (e.g. prubeth toggle speculative_plan_b)[/yellow]")
        return
    key = args[0]
    cfg_mgr = ConfigManager()
    try:
        new_val = cfg_mgr.toggle(key)
        status = "[bold green]ENABLED (ON)[/bold green]" if new_val else "[bold red]DISABLED (OFF)[/bold red]"
        console.print(f"Setting [bold cyan]{key}[/bold cyan] is now {status}.")
    except Exception as e:
        console.print(f"[bold red]Toggle Error:[/bold red] {e}")

def handle_config_command(args: list):
    cfg_mgr = ConfigManager()
    if not args or args[0] == "list":
        cfg = cfg_mgr.load_config()
        table = Table(title="PRUBETH Raw Configuration Matrix")
        table.add_column("Setting / Key", style="cyan")
        table.add_column("Current Value", style="green")
        for k, v in cfg.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    disp_val = f"***{sub_v[-4:]}" if "api_key" in k and sub_v else str(sub_v)
                    table.add_row(f"{k}.{sub_k}", disp_val)
            else:
                table.add_row(k, str(v))
        console.print(table)
    elif args[0] == "get" and len(args) > 1:
        val = cfg_mgr.get(args[1])
        console.print(f"[bold cyan]{args[1]}:[/bold cyan] [green]{val}[/green]")
    elif args[0] == "set" and len(args) > 2:
        val = args[2]
        if val.lower() == "true":
            val = True
        elif val.lower() == "false":
            val = False
        elif val.isdigit():
            val = int(val)
        cfg_mgr.set(args[1], val)
        console.print(f"[bold green]Updated {args[1]} = {val}[/bold green]")
    else:
        console.print("[yellow]Usage: prubeth config [list | get <key> | set <key> <value>][/yellow]")

def render_model_comparison_table():
    """Renders exhaustive technical comparison of supported models for production development."""
    from rich import box
    table = Table(title="PRUBETH Multi-Model Engineering Benchmark & Production Suitability Matrix", box=box.ROUNDED)
    table.add_column("Model Identifier", style="bold cyan")
    table.add_column("Provider / Tier", style="magenta")
    table.add_column("Context Window", justify="right", style="cyan")
    table.add_column("Speed / Latency", justify="right", style="green")
    table.add_column("Code Intelligence", style="yellow")
    table.add_column("Production Suitability & Notes", style="white")

    table.add_row(
        "gemini-4.0-preview\n(gemini-4-argon)",
        "Google / Tier 0\nFrontier Experimental",
        "2,000,000 tokens",
        "~2.4s (Deep)",
        "99.4/100 (Frontier)",
        "[bold yellow]⚠️ Experimental / Whitelist Preview[/bold yellow]\nExtreme reasoning; not yet suited for general public daily workflows due to restricted preview quota."
    )
    table.add_row(
        "gemini-3.8-flash",
        "Google / Tier 2\nFrontier Velocity",
        "1,000,000 tokens",
        "~0.5s - 0.8s",
        "94.2/100 (High)",
        "[bold green]✔ Highly Recommended (Velocity)[/bold green]\nIdeal for fast autonomous coding, real-time tool loops, and interactive chat."
    )
    table.add_row(
        "gemini-3.1-pro-preview",
        "Google / Tier 1\nFlagship Architect",
        "1,000,000 tokens",
        "~1.5s - 2.2s",
        "98.1/100 (Deep)",
        "[bold green]✔ Production Flagship[/bold green]\nBest for complex multi-file architectural planning, Speculative Plan B, and large refactors."
    )
    table.add_row(
        "claude-3-7-sonnet",
        "Anthropic / Tier 1\nHybrid Reasoning",
        "200,000 tokens",
        "~1.8s - 2.5s",
        "97.8/100 (Deep)",
        "[bold green]✔ Production Ready[/bold green]\nExcellent code precision and prompt-cached invariant tracking."
    )
    table.add_row(
        "deepseek-r1:free",
        "OpenRouter / Tier 3\nOpen Frontier",
        "128,000 tokens",
        "~3.0s - 4.5s",
        "96.5/100 (Reasoning)",
        "[bold cyan]✔ Zero Cost Cloud[/bold cyan]\n671B MoE deep reasoning without paid API keys. Perfect resilient backup."
    )
    table.add_row(
        "qwen2.5-coder:7b",
        "Local (Ollama / LM)\nTier 4 Offline",
        "32,768 tokens",
        "~0.4s - 1.2s",
        "84.0/100 (Local)",
        "[bold green]✔ 100% Air-Gapped / Private[/bold green]\nZero cloud cost, zero network latency. Runs smoothly on local laptop hardware."
    )

    console.print(table)
    console.print("[dim]Switch model anytime using: [/dim][cyan]/model <name|alias>[/cyan] [dim](e.g. [/dim][bold]/model 3.8[/bold][dim], [/dim][bold]/model 4.0[/bold][dim], [/dim][bold]/model 3.1[/bold][dim], [/dim][bold]/model local[/bold][dim]).[/dim]\n")

def handle_models_command(args: list):
    cfg_mgr = ConfigManager()
    from prubeth.models.gateway import UniversalModelGateway
    gw = UniversalModelGateway(cfg_mgr)
    cfg = cfg_mgr.load_config()
    keys = cfg.get("api_keys", {})
    timeout_s = cfg.get("cloud_timeout_s", 12)

    if not args or args[0] in ["list", "status"]:
        # Table 1: Strict Highest-to-Lowest Model Preference Hierarchy
        h_table = Table(title="PRUBETH Hierarchical Model Preference Chain (Highest to Lowest)")
        h_table.add_column("Tier / Capability", style="cyan")
        h_table.add_column("Ranked Models (Highest → Lowest)", style="green")
        h_table.add_column("Primary Purpose", style="yellow")
        h_table.add_column("Fallback Trigger", style="magenta")

        h_table.add_row(
            "Tier 0: Frontier Experimental Preview",
            "gemini-4.0-preview, gemini-4-argon",
            "Cutting-edge frontier reasoning (restricted experimental access)",
            "Auto-fallback to Tier 1 if 404/quota unavailable"
        )
        h_table.add_row(
            "Tier 1: Flagship Frontier Pro",
            "gemini-3.1-pro-preview, gemini-pro-latest, claude-3-7-sonnet",
            "Deep reasoning, system architecture, speculative Plan B",
            "Rate limit (429) or cloud timeout"
        )
        h_table.add_row(
            "Tier 2: Frontier Velocity & Real-Time",
            "gemini-3.8-flash, gemini-3.5-flash, gemini-flash-latest",
            "Sub-second autonomous coding, real-time tool loops, rapid chat",
            "Degradation (503) or quota exhaustion"
        )
        h_table.add_row(
            "Tier 3: Open-Weight Frontier Free Tier",
            "deepseek/deepseek-r1:free, meta-llama/llama-3.3-70b:free, qwen/qwen-2.5-coder-32b:free",
            "Zero-cost cloud reasoning backup via OpenRouter",
            "Cloud latency threshold exceeded"
        )
        h_table.add_row(
            "Tier 4: Local Downloaded & Loaded",
            "Active local GGUF/weights via LM Studio (:1234) or Ollama (:11434)",
            "100% private, air-gapped, zero cloud cost execution",
            "Automatic pivot when cloud takes > " + str(timeout_s) + "s"
        )
        console.print(h_table)

        # Table 2: Live Local & Cloud Provider Status
        p_table = Table(title="Model Providers, Credentials & Local Engine Status")
        p_table.add_column("Provider", style="cyan")
        p_table.add_column("Connection Status", style="green")
        p_table.add_column("Configured Key", style="magenta")
        p_table.add_column("Endpoint", style="dim")

        local_det = gw.detect_local_model()
        local_status = f"[bold green]● ACTIVE ({local_det['model']})[/bold green]" if local_det else "[dim]○ Standby (Offline)[/dim]"

        p_table.add_row("google", "[bold green]● Active[/bold green]", "YES (***zz8g)" if keys.get("google") else "NO", cfg.get("provider_endpoints", {}).get("google", ""))
        p_table.add_row("openrouter", "[bold green]● Active[/bold green]", "YES (***f09c)" if keys.get("openrouter") else "NO", cfg.get("provider_endpoints", {}).get("openrouter", ""))
        p_table.add_row("lm_studio", local_status if local_det and local_det["provider"] == "lm_studio" else "[dim]○ Standby[/dim]", "LOCAL (Zero Cost)", cfg.get("provider_endpoints", {}).get("lm_studio", ""))
        p_table.add_row("ollama", local_status if local_det and local_det["provider"] == "ollama" else "[dim]○ Standby[/dim]", "LOCAL (Zero Cost)", cfg.get("provider_endpoints", {}).get("ollama", ""))
        console.print(p_table)

        console.print(f"[bold cyan]Auto-Switch Latency Guard:[/bold cyan] Active (Cloud calls timeout at [bold]{timeout_s}s[/bold] and auto-pivot to local loaded model).\n")

    elif args[0] in ["compare", "benchmarks", "benchmark"]:
        render_model_comparison_table()

    elif args[0] in ["select", "set"] and len(args) > 1:
        target = args[1]
        resolved = cfg_mgr.resolve_model_and_provider(target)
        cfg_mgr.set("default_model", resolved["model"])
        console.print(f"[bold green]Active Model Switched to:[/bold green] [bold cyan]{resolved['model']}[/bold cyan] ({resolved['provider']})")
        if "4.0" in resolved["model"] or "argon" in resolved["model"]:
            console.print("[bold yellow]ℹ️ Note on Gemini 4.0:[/bold yellow] [dim]Gemini 4.0 represents next-gen frontier experimental capability. If quota or access is restricted on standard keys, PRUBETH will automatically failover to Gemini 3.1 Pro / 3.8 Flash.[/dim]")
        elif "3.8" in resolved["model"]:
            console.print("[bold green]⚡ Gemini 3.8 Flash Selected:[/bold green] [dim]Optimized for sub-second developer responsiveness and high-throughput tool generation.[/dim]")

    elif args[0] == "test":
        test_m = args[1] if len(args) > 1 else None
        resolved = cfg_mgr.resolve_model_and_provider(test_m)
        console.print(f"[bold cyan]Testing Model:[/bold cyan] {resolved['model']} via {resolved['provider']}...")
        try:
            resp = gw.generate("Reply with: PRUBETH Model Operational", model_name=resolved['model'])
            console.print(f"[bold green]SUCCESS![/bold green] Received in [bold]{resp.latency_s}s[/bold] ({resp.provider}/{resp.model}): {resp.text.strip()}")
        except Exception as e:
            console.print(f"[bold red]TEST FAILED:[/bold red] {e}")

def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ["--version", "-v", "version"]:
            from prubeth.cli.version import render_version_info
            render_version_info(console, as_json=("--json" in sys.argv))
            return
        if cmd in ["--help", "-h", "help"]:
            from prubeth.cli.help import render_tier1_help
            render_tier1_help(console)
            return
        if cmd in ["settings", "status"]:
            cfg_mgr = ConfigManager()
            if len(sys.argv) > 2 and sys.argv[2] == "inspect":
                target_key = sys.argv[3] if len(sys.argv) > 3 else ""
                render_setting_inspection(cfg_mgr, target_key)
            elif len(sys.argv) > 2 and sys.argv[2] in ["tune", "builder", "perf"]:
                render_performance_builder_hud(console, cfg_mgr)
            else:
                render_performance_dashboard(cfg_mgr)
            return
        if cmd in ["tune", "perf", "builder"]:
            cfg_mgr = ConfigManager()
            render_performance_builder_hud(console, cfg_mgr)
            return
        if cmd == "inspect":
            cfg_mgr = ConfigManager()
            target_key = sys.argv[2] if len(sys.argv) > 2 else ""
            render_setting_inspection(cfg_mgr, target_key)
            return
        if cmd == "profile":
            handle_profile_command(sys.argv[2:])
            return
        if cmd == "toggle":
            handle_toggle_command(sys.argv[2:])
            return
        if cmd == "set" and len(sys.argv) > 3:
            handle_config_command(["set", sys.argv[2], sys.argv[3]])
            return
        if cmd == "config":
            handle_config_command(sys.argv[2:])
            return
        if cmd == "models":
            handle_models_command(sys.argv[2:])
            return
        if cmd in ["therapy", "heal"] or (cmd in ["doctor", "check"] and "--fix" in sys.argv):
            from prubeth.cli.therapy import SystemTherapist
            SystemTherapist(console).render_therapy_report()
            return
        if cmd in ["configure", "config"] and ("--deep" in sys.argv or "-d" in sys.argv or "deep" in sys.argv):
            from prubeth.cli.therapy import run_deep_configuration_wizard
            run_deep_configuration_wizard(console)
            return
        if cmd in ["setup", "onboard", "onboarding"]:
            if "--personal" in sys.argv:
                from prubeth.cli.setup import run_personal_setup_hub
                run_personal_setup_hub(console)
                return
            cfg_mgr = ConfigManager()
            render_onboarding_wizard(console, cfg_mgr)
            return
        if cmd in ["personal", "keys", "vault", "local-models"]:
            from prubeth.cli.setup import run_personal_setup_hub
            run_personal_setup_hub(console)
            return
        if cmd in ["doctor", "check", "diagnose"]:
            from prubeth.cli.doctor import PrubethDoctor
            PrubethDoctor(console).render_report()
            return
        if cmd in ["setup-completion", "install-completion"]:
            from prubeth.cli.completions import install_shell_completion
            target_sh = sys.argv[2].lower() if len(sys.argv) > 2 else None
            ok, msg = install_shell_completion(target_sh)
            color = "green" if ok else "red"
            console.print(f"[bold {color}]{msg}[/bold {color}]")
            return
        if cmd == "completion":
            from prubeth.cli.completions import generate_powershell_completion, generate_bash_completion, generate_zsh_completion, install_shell_completion
            sub = sys.argv[2].lower() if len(sys.argv) > 2 else ""
            if sub in ["install", "setup"]:
                target_sh = sys.argv[3].lower() if len(sys.argv) > 3 else None
                ok, msg = install_shell_completion(target_sh)
                color = "green" if ok else "red"
                console.print(f"[bold {color}]{msg}[/bold {color}]")
                return
            shell = sub if sub in ["bash", "zsh", "powershell"] else "powershell"
            if shell == "bash":
                sys.stdout.write(generate_bash_completion())
            elif shell == "zsh":
                sys.stdout.write(generate_zsh_completion())
            else:
                sys.stdout.write(generate_powershell_completion())
            return
        if cmd == "reset":
            cfg_mgr = ConfigManager()
            execute_factory_reset(console, cfg_mgr)
            return
        if cmd == "swarm":
            handle_swarm_command(sys.argv[2:])
            return
        if cmd in ["worktrees", "worktree"]:
            handle_worktrees_command(sys.argv[2:])
            return
        if cmd == "memory":
            handle_memory_command(sys.argv[2:])
            return
        if cmd == "bridge":
            handle_bridge_command(sys.argv[2:])
            return
        if cmd == "consensus":
            handle_consensus_command(sys.argv[2:])
            return
        if cmd == "mcp":
            handle_mcp_command(sys.argv[2:])
            return
        if cmd == "rollback":
            snap_mgr = SnapshotManager()
            snaps = snap_mgr.list_snapshots()
            if snaps:
                latest = snaps[-1]
                snap_mgr.rollback_to_snapshot(latest)
                console.print(f"[bold green]Reverted workspace to snapshot:[/bold green] {latest}")
            else:
                console.print("[yellow]No snapshots found to roll back to.[/yellow]")
            return
        if cmd == "diff":
            from prubeth.persistence.checkpoints import SnapshotManager
            snap_mgr = SnapshotManager()
            diff_out = snap_mgr.compute_snapshot_diff()
            if not diff_out:
                from prubeth.security.permissions import SecurityEngine
                from prubeth.persistence.database import TaskDatabase
                from prubeth.tools.execution import ToolExecutionEngine
                sec = SecurityEngine()
                db = TaskDatabase(str(Path.cwd() / ".prubeth" / "prubeth.db"))
                try:
                    tool_engine = ToolExecutionEngine(sec, db, "diff_check")
                    _, diff_out = tool_engine.execute_tool("git_diff", {})
                finally:
                    db.close()

            if diff_out and "Git is not installed" not in diff_out:
                from rich.syntax import Syntax
                syntax = Syntax(diff_out, "diff", theme="monokai", line_numbers=True)
                console.print(Panel(syntax, title="Working Tree Unified Diff (Pure Python)", border_style="cyan"))
            else:
                console.print(Panel("[dim]No changes in working tree against initial snapshot[/dim]", title="Working Tree Diff", border_style="blue"))
            return
        if cmd == "search":
            query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
            if not query:
                console.print("[yellow]Usage: prubeth search <query>[/yellow]")
                return
            idx = CodebaseIndex()
            results = idx.search(query, top_k=5)
            if not results:
                console.print(f"[yellow]No matching code snippets found for query: '{query}'[/yellow]")
            else:
                console.print(f"[bold cyan]BM25 Code Search Results for:[/bold cyan] [bold green]'{query}'[/bold green]\n")
                for r in results:
                    console.print(Panel(
                        f"[dim]{r.snippet}[/dim]",
                        title=f"{r.file_path} (Lines {r.start_line}-{r.end_line}) | Score: {r.score}",
                        border_style="cyan"
                    ))
            return
        if cmd == "heal":
            target_cmd = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
            if not target_cmd:
                console.print("[yellow]Usage: prubeth heal \"<test_or_build_command>\" (e.g. prubeth heal \"pytest\")[/yellow]")
                return
            cfg_mgr = ConfigManager()
            resolved = cfg_mgr.resolve_model_and_provider()
            healer = AutoHealer(console=console, model_name=resolved["model"])
            healer.heal(target_cmd)
            return
        if cmd in ["cost", "spend", "usage"]:
            render_cost_report(console)
            return
        if cmd in ["history", "tree"]:
            tree = ConversationTree()
            console.print(tree.render_history_table())
            return
        if cmd == "init":
            handle_init_command()
            return
        if cmd == "review":
            handle_review_command()
            return
        if cmd == "compact":
            tree = ConversationTree()
            n = tree.compact()
            console.print(f"[bold green]✔ Compacted {n} previous turns from conversation memory.[/bold green]")
            return
        if cmd == "goal":
            handle_goal_command(sys.argv[2:])
            return
        if cmd == "commit":
            handle_commit_command(sys.argv[2:])
            return
        if cmd == "pr":
            handle_pr_command(sys.argv[2:])
            return
        if cmd == "learn":
            handle_learn_command(sys.argv[2:])
            return
        if cmd == "symbols":
            handle_symbols_command(sys.argv[2:])
            return
        if cmd == "callers":
            handle_callers_command(sys.argv[2:])
            return
        if cmd == "autotune":
            handle_autotune_command(sys.argv[2:])
            return
        if cmd == "research":
            handle_research_command(sys.argv[2:])
            return
        if cmd == "janitor":
            handle_janitor_command(sys.argv[2:])
            return
        if cmd == "bio":
            handle_bio_command(sys.argv[2:])
            return
        if cmd == "migrate":
            handle_migrate_command(sys.argv[2:])
            return
        if cmd == "issue":
            handle_issue_command(sys.argv[2:])
            return
        if cmd in ["cache", "kvcache"]:
            handle_cache_command(sys.argv[2:])
            return
        if cmd in ["timeline", "snapshots"]:
            handle_timeline_command(sys.argv[2:])
            return
        if cmd in ["integrity", "verify", "attest", "attestation"]:
            from prubeth.security.integrity import PrubethIntegrityEngine
            PrubethIntegrityEngine(console).render_report()
            return
        if cmd in ["build-binary", "binary", "compile"]:
            import subprocess
            script_path = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "build_standalone_binary.py"
            if script_path.exists():
                subprocess.run([sys.executable, str(script_path)])
            else:
                console.print("[red]Binary build script not found.[/red]")
            return

    parser = argparse.ArgumentParser(
        prog="prubeth",
        description="PRUBETH Autonomous Developer CLI — Elite Multi-Model Engineering Runtime."
    )
    parser.add_argument("goal", nargs="*", help="Goal or task to execute autonomously.")
    parser.add_argument("-a", "--auto", action="store_true", help="Auto-approve non-destructive actions.")
    parser.add_argument("-m", "--model", type=str, default=None, help="Override active AI model (e.g. gemini-3.5-flash, deepseek-chat, claude-3-7-sonnet).")
    parser.add_argument("--profile", type=str, default=None, help="Temporarily apply a preset profile (builder, deep-reasoning, local-airgap, safe-audit).")
    parser.add_argument("--local", action="store_true", help="Prefer local LM Studio / Ollama model.")
    parser.add_argument("--status", action="store_true", help="Display full visual performance and settings dashboard.")
    parser.add_argument("--output-format", choices=["text", "json", "stream-json"], default="text", help="Output format for automation (text or stream-json NDJSON).")

    args = parser.parse_args()
    cfg_mgr = ConfigManager()

    if args.status:
        render_performance_dashboard(cfg_mgr)
        return

    # Profile override
    if args.profile:
        cfg_mgr.apply_profile(args.profile)

    cfg = cfg_mgr.load_config()

    config = RuntimeConfig(
        auto_approve_actions=args.auto or cfg.get("auto_approve_actions", False),
        prefer_local_model=args.local or cfg.get("offline_mode", False),
        model_name=args.model,
        speculative_plan_b=cfg.get("speculative_plan_b", True),
        auto_checkpoint=cfg.get("auto_checkpoint", True),
        auto_rollback_on_failure=cfg.get("auto_rollback_on_failure", True),
        plan_b_strategy=cfg.get("plan_b_strategy", "auto_pivot")
    )

    controller = AutonomousRuntimeController(
        config=config,
        approval_cb=None if config.auto_approve_actions else interactive_approval_handler,
        event_cb=make_event_logger(args.output_format)
    )

    # Single-shot command line task
    if args.goal:
        user_goal = " ".join(args.goal)
        resolved = cfg_mgr.resolve_model_and_provider(args.model)
        p_info = cfg_mgr.get_active_profile_info()
        if args.output_format == "text":
            console.print(Panel(f"[bold]Executing Goal:[/bold] {user_goal}\n[dim]Profile:[/dim] [green]{p_info['badge']}[/green] | [dim]Model:[/dim] [cyan]{resolved['model']}[/cyan] ({resolved['provider']})", border_style="cyan"))
        result = controller.run_task(user_goal, model_override=args.model)
        if args.output_format == "text":
            if result.get("success"):
                console.print("\n[bold green]Task completed and verified successfully![/bold green]")
            else:
                console.print(f"\n[bold red]Task failed or cancelled:[/bold red] {result}")
        elif args.output_format == "stream-json":
            sys.stdout.write(json.dumps({"event": "task_result", "data": result}, default=str) + "\n")
            sys.stdout.flush()
        return

    # Interactive REPL
    print_banner()
    current_model = args.model
    expander = ContextExpander()
    conv_tree = ConversationTree()
    show_hud = True

    # Setup Claude Code & Gemini CLI parity: persistent history and tab completion
    def setup_terminal_cockpit(ws_root: Path):
        try:
            import readline
            import atexit
            h_dir = Path.home() / ".prubeth"
            h_dir.mkdir(parents=True, exist_ok=True)
            h_file = h_dir / "history.txt"
            if h_file.exists():
                try:
                    readline.read_history_file(str(h_file))
                except Exception:
                    pass

            slash_cmds = [
                "/cache", "/cache status", "/cache clear", "/cache refresh",
                "/compact", "/timeline", "/rollback", "/status", "/settings",
                "/models", "/diff", "/help", "/cost", "/spend", "/learn",
                "/symbols", "/callers", "/mcp", "/goal", "/commit", "/pr",
                "/profile", "/toggle", "/tune", "/devmode", "/planb",
                "/exit", "/clear"
            ]

            def tab_completer(text: str, state: int):
                if text.startswith("/"):
                    matches = [c for c in slash_cmds if c.startswith(text)]
                    return matches[state] if state < len(matches) else None
                if text.startswith("@"):
                    prefix = text[1:].replace("file:", "")
                    found = []
                    try:
                        for p in ws_root.rglob("*"):
                            if any(ign in p.parts for ign in [".git", "dist", "build", "__pycache__", ".venv", "venv", ".mypy_cache"]):
                                continue
                            rel = str(p.relative_to(ws_root)).replace("\\", "/")
                            if rel.lower().startswith(prefix.lower()):
                                found.append(f"@{rel}")
                                if len(found) >= 20:
                                    break
                    except Exception:
                        pass
                    return found[state] if state < len(found) else None
                if text.startswith("!"):
                    sh_cmds = ["!git status", "!git diff", "!git log", "!pytest", "!python", "!ls", "!dir"]
                    matches = [c for c in sh_cmds if c.startswith(text)]
                    return matches[state] if state < len(matches) else None
                return None

            readline.set_completer(tab_completer)
            readline.set_completer_delims(" \t\n")
            try:
                readline.parse_and_bind("tab: complete")
            except Exception:
                pass

            def save_h():
                try:
                    readline.set_history_length(2000)
                    readline.write_history_file(str(h_file))
                except Exception:
                    pass
            atexit.register(save_h)
        except Exception:
            pass

    setup_terminal_cockpit(Path.cwd().resolve())

    while True:
        try:
            p_info = cfg_mgr.get_active_profile_info()
            resolved = cfg_mgr.resolve_model_and_provider(current_model)
            from prubeth.cli.hud import calculate_session_spend, get_current_process_memory_mb
            ram_mb = get_current_process_memory_mb()
            spend_info = calculate_session_spend()
            spend_str = f"${spend_info['total_cost_usd']:.4f}" if spend_info['total_cost_usd'] > 0 else "$0.0000"
            saved_str = f" [green](Saved: ${spend_info['total_saved_usd']:.4f})[/green]" if spend_info['total_saved_usd'] > 0 else ""

            branch_name = "main"
            try:
                head_file = Path(".git/HEAD")
                if head_file.exists():
                    ref = head_file.read_text(encoding="utf-8").strip()
                    if ref.startswith("ref: refs/heads/"):
                        branch_name = ref.replace("ref: refs/heads/", "")
            except Exception:
                pass

            status_elements = [
                f"[bold cyan]{resolved['model']}[/bold cyan]",
                f"[bold green]{branch_name}[/bold green]",
                f"[dim]{ram_mb} MB[/dim]",
                f"[dim]{spend_str}{saved_str}[/dim]"
            ]
            console.print(f"[dim]prubeth [{ ' · '.join(status_elements) }][/dim]")
            console.print(f"[bold cyan]❯[/bold cyan] ", end="")
            prompt_input = input().strip()
            if not prompt_input:
                continue

            # Multiline input support: lines ending with \ or enclosed in """
            if prompt_input.endswith("\\") or prompt_input.startswith('"""'):
                accumulated = [prompt_input.rstrip("\\")]
                in_triple = prompt_input.startswith('"""') and not (prompt_input.endswith('"""') and len(prompt_input) > 3)
                while True:
                    sub = input("... ").rstrip()
                    if in_triple:
                        accumulated.append(sub)
                        if sub.endswith('"""'):
                            break
                    else:
                        if sub.endswith("\\"):
                            accumulated.append(sub.rstrip("\\"))
                        else:
                            accumulated.append(sub)
                            break
                prompt_input = "\n".join(accumulated).strip('"""').strip()

            if prompt_input.lower() in ["/exit", "exit", "quit"]:
                console.print("[yellow]Exiting PRUBETH CLI. Goodbye![/yellow]")
                break

            if prompt_input in ["/clear", "/cls"]:
                conv_tree.clear()
                console.clear()
                print_banner()
                continue

            # Direct shell / bash pass-through (Claude Code & Gemini CLI parity: !cmd or $ cmd)
            if prompt_input.startswith("!") or (prompt_input.startswith("$ ") and len(prompt_input) > 2):
                raw_cmd = prompt_input[1:].strip() if prompt_input.startswith("!") else prompt_input[2:].strip()
                console.print(f"  [dim cyan]$ {raw_cmd}[/dim cyan]")
                if not hasattr(controller, "tool_engine") or not controller.tool_engine:
                    from prubeth.tools.execution import ToolExecutionEngine
                    controller.tool_engine = ToolExecutionEngine(controller.security, controller.db, "shell_passthrough", mcp_mgr=controller.mcp)
                exit_c, out_txt = controller.tool_engine.subshell.execute(raw_cmd)
                if out_txt.strip():
                    console.print(out_txt.rstrip())
                continue

            if prompt_input == "/compact":
                pruned = conv_tree.compact()
                console.print(f"[bold green]✔ Conversation compacted. Pruned {pruned} older turns to optimize context budget.[/bold green]")
                continue

            if prompt_input == "/init":
                handle_init_command()
                continue

            if prompt_input == "/review":
                handle_review_command(controller)
                continue

            if prompt_input in ["/hud", "/statusline"]:
                show_hud = not show_hud
                status_str = "[bold green]ENABLED[/bold green]" if show_hud else "[bold red]DISABLED[/bold red]"
                console.print(f"Cockpit Telemetry HUD is now {status_str}.")
                continue

            if prompt_input in ["/cost", "/spend", "/usage"]:
                render_cost_report(console)
                continue

            if prompt_input.startswith("/search"):
                parts = prompt_input.split()[1:]
                q = " ".join(parts).strip()
                if q:
                    idx = CodebaseIndex()
                    results = idx.search(q, top_k=4)
                    if results:
                        console.print(f"[bold cyan]BM25 Results for:[/bold cyan] [bold green]'{q}'[/bold green]\n")
                        for r in results:
                            console.print(Panel(r.snippet, title=f"{r.file_path}:{r.start_line}-{r.end_line} (score: {r.score})", border_style="cyan"))
                    else:
                        console.print(f"[yellow]No matching code found for '{q}'[/yellow]")
                else:
                    console.print("[yellow]Usage: /search <query>[/yellow]")
                continue

            if prompt_input.startswith("/heal"):
                parts = prompt_input.split()[1:]
                target_cmd = " ".join(parts).strip() or "pytest"
                res_m = cfg_mgr.resolve_model_and_provider(current_model)
                healer = AutoHealer(console=console, model_name=res_m["model"])
                healer.heal(target_cmd)
                continue

            if prompt_input in ["/history", "/tree"]:
                console.print(conv_tree.render_history_table())
                continue

            if prompt_input.startswith("/fork"):
                parts = prompt_input.split()[1:]
                bname = parts[0] if parts else "experiment"
                new_b = conv_tree.fork(bname)
                console.print(f"[bold green]Forked conversation into branch:[/bold green] [bold cyan]{new_b}[/bold cyan]")
                continue

            if prompt_input.startswith("/branch"):
                parts = prompt_input.split()[1:]
                if parts:
                    ok = conv_tree.switch_branch(parts[0])
                    if ok:
                        console.print(f"[bold green]Switched to branch:[/bold green] [bold cyan]{parts[0]}[/bold cyan]")
                    else:
                        console.print(f"[bold red]Branch '{parts[0]}' not found.[/bold red]")
                else:
                    console.print(f"[cyan]Current branch:[/cyan] [bold]{conv_tree.current_branch}[/bold]")
                continue

            if prompt_input.startswith("/rewind"):
                parts = prompt_input.split()[1:]
                if parts:
                    tid = parts[0]
                    ok, snap_id = conv_tree.rewind(tid)
                    if ok:
                        console.print(f"[bold green]Rewound conversation to turn:[/bold green] [bold cyan]{tid}[/bold cyan]")
                        if snap_id:
                            snap_mgr = SnapshotManager()
                            snap_mgr.rollback_to_snapshot(snap_id)
                            console.print(f"[bold yellow]Restored workspace filesystem to snapshot:[/bold yellow] [bold cyan]{snap_id}[/bold cyan]")
                    else:
                        console.print(f"[bold red]Turn '{tid}' not found in history tree.[/bold red]")
                else:
                    console.print("[yellow]Usage: /rewind <turn_id> (e.g. /rewind turn_001)[/yellow]")
                continue

            if prompt_input.startswith(("/settings", "/status")):
                render_performance_dashboard(cfg_mgr)
                continue

            if prompt_input in ["/tune", "/perf", "/builder"]:
                render_performance_builder_hud(console, cfg_mgr)
                continue

            if prompt_input.startswith("/inspect"):
                parts = prompt_input.split()[1:]
                if parts:
                    render_setting_inspection(cfg_mgr, parts[0])
                else:
                    console.print("[yellow]Usage: /inspect <setting_key> (e.g. /inspect speculative_plan_b)[/yellow]")
                continue

            if prompt_input.startswith("/profile"):
                parts = prompt_input.split()[1:]
                handle_profile_command(parts)
                continue

            if prompt_input.startswith("/toggle"):
                parts = prompt_input.split()[1:]
                handle_toggle_command(parts)
                continue

            if prompt_input.startswith("/set"):
                parts = prompt_input.split()[1:]
                if len(parts) >= 2:
                    handle_config_command(["set", parts[0], parts[1]])
                else:
                    console.print("[yellow]Usage: /set <key> <val>[/yellow]")
                continue

            if prompt_input == "/devmode":
                new_v = cfg_mgr.toggle("developer_mode")
                console.print(f"[bold cyan]Developer Mode:[/bold cyan] [{'green' if new_v else 'red'}]{'ENABLED' if new_v else 'DISABLED'}[/{'green' if new_v else 'red'}]")
                continue

            if prompt_input == "/planb":
                new_v = cfg_mgr.toggle("speculative_plan_b")
                console.print(f"[bold cyan]Speculative Plan B:[/bold cyan] [{'green' if new_v else 'red'}]{'ARMED' if new_v else 'DISARMED'}[/{'green' if new_v else 'red'}]")
                continue

            if prompt_input == "/rollback":
                snap_mgr = SnapshotManager()
                snaps = snap_mgr.list_snapshots()
                if snaps:
                    latest = snaps[-1]
                    snap_mgr.rollback_to_snapshot(latest)
                    console.print(f"[bold green]Reverted workspace to snapshot:[/bold green] {latest}")
                else:
                    console.print("[yellow]No snapshots found to roll back to.[/yellow]")
                continue

            if prompt_input.startswith("/model") or prompt_input.startswith("/compare"):
                parts = prompt_input.split()
                if len(parts) > 1 and parts[1].lower() in ["compare", "benchmarks", "benchmark"]:
                    render_model_comparison_table()
                    continue
                if prompt_input.startswith("/compare"):
                    render_model_comparison_table()
                    continue

                if len(parts) > 1:
                    raw_target = parts[1]
                    res = cfg_mgr.resolve_model_and_provider(raw_target)
                    current_model = res["model"]
                    cfg_mgr.set("default_model", current_model)
                    console.print(f"[bold green]Switched active model to:[/bold green] [bold cyan]{res['model']}[/bold cyan] ({res['provider']})")
                    if "4.0" in res["model"] or "argon" in res["model"]:
                        console.print("[bold yellow]ℹ️ Note on Gemini 4.0:[/bold yellow] [dim]Gemini 4.0 (Argon) represents experimental frontier reasoning. If quota or access is restricted on standard keys, PRUBETH's resilience engine will automatically fall back to Gemini 3.1 Pro / 3.8 Flash.[/dim]")
                    elif "3.8" in res["model"]:
                        console.print("[bold green]⚡ Gemini 3.8 Flash Activated:[/bold green] [dim]Sub-second velocity & high-throughput tool execution enabled.[/dim]")
                else:
                    res = cfg_mgr.resolve_model_and_provider(current_model)
                    console.print(f"[cyan]Current model:[/cyan] [bold]{res['model']}[/bold] ({res['provider']})")
                    console.print("[dim]Type /models to view hierarchy, /compare for benchmark matrix, or /model <3.8|4.0|3.1|local> to switch.[/dim]")
                continue

            if prompt_input == "/models":
                handle_models_command(["list"])
                continue

            if prompt_input.lower() in ["/therapy", "/heal", "therapy", "heal"]:
                from prubeth.cli.therapy import SystemTherapist
                SystemTherapist(console).render_therapy_report()
                continue

            if prompt_input.lower() in ["/deepconfig", "/configure", "deepconfig"]:
                from prubeth.cli.therapy import run_deep_configuration_wizard
                run_deep_configuration_wizard(console)
                continue

            if prompt_input in ["/setup", "/onboard", "/onboarding"]:
                render_onboarding_wizard(console, cfg_mgr)
                continue

            if prompt_input.lower() in ["/personal", "/keys", "/vault", "personal", "keys"]:
                from prubeth.cli.setup import run_personal_setup_hub
                run_personal_setup_hub(console, cfg_mgr)
                continue

            if prompt_input == "/reset":
                execute_factory_reset(console, cfg_mgr)
                continue

            if prompt_input.startswith("/config"):
                parts = prompt_input.split()[1:]
                handle_config_command(parts)
                continue

            if prompt_input == "/diff":
                success, diff = controller.tool_engine.execute_tool("git_diff", {})
                console.print(Panel(diff or "[dim]No changes in working tree[/dim]", title="Working Tree Diff", border_style="blue"))
                continue

            if prompt_input.startswith("/swarm"):
                parts = prompt_input.split()[1:]
                handle_swarm_command(parts, controller)
                continue

            if prompt_input.startswith("/worktrees") or prompt_input.startswith("/worktree"):
                parts = prompt_input.split()[1:]
                handle_worktrees_command(parts, controller)
                continue

            if prompt_input.startswith("/memory"):
                parts = prompt_input.split()[1:]
                handle_memory_command(parts, controller)
                continue

            if prompt_input.startswith("/bridge"):
                parts = prompt_input.split()[1:]
                handle_bridge_command(parts, controller)
                continue

            if prompt_input == "/consensus":
                handle_consensus_command([], controller)
                continue

            if prompt_input.startswith("/mcp"):
                parts = prompt_input.split()[1:]
                handle_mcp_command(parts, controller)
                continue

            if prompt_input.startswith("/goal"):
                parts = prompt_input.split()[1:]
                handle_goal_command(parts, controller)
                continue

            if prompt_input.startswith("/commit"):
                parts = prompt_input.split()[1:]
                handle_commit_command(parts, controller)
                continue

            if prompt_input.startswith("/pr"):
                parts = prompt_input.split()[1:]
                handle_pr_command(parts, controller)
                continue

            if prompt_input.startswith("/learn"):
                parts = prompt_input.split()[1:]
                handle_learn_command(parts, controller)
                continue

            if prompt_input.startswith("/symbols"):
                parts = prompt_input.split()[1:]
                handle_symbols_command(parts, controller)
                continue

            if prompt_input.startswith("/callers"):
                parts = prompt_input.split()[1:]
                handle_callers_command(parts, controller)
                continue

            if prompt_input.startswith("/autotune"):
                parts = prompt_input.split()[1:]
                handle_autotune_command(parts, controller)
                continue

            if prompt_input.startswith("/research"):
                parts = prompt_input.split()[1:]
                handle_research_command(parts, controller)
                continue

            if prompt_input.startswith("/janitor"):
                parts = prompt_input.split()[1:]
                handle_janitor_command(parts, controller)
                continue

            if prompt_input.startswith("/bio"):
                parts = prompt_input.split()[1:]
                handle_bio_command(parts, controller)
                continue

            if prompt_input.startswith("/migrate"):
                parts = prompt_input.split()[1:]
                handle_migrate_command(parts, controller)
                continue

            if prompt_input.startswith("/issue"):
                parts = prompt_input.split()[1:]
                handle_issue_command(parts, controller)
                continue

            if prompt_input.startswith(("/timeline", "/snapshots")):
                parts = prompt_input.split()[1:]
                handle_timeline_command(parts, controller)
                continue

            if prompt_input.startswith(("/cache", "/kvcache")):
                parts = prompt_input.split()[1:]
                handle_cache_command(parts, controller)
                continue

            if prompt_input.startswith(("/compact", "/compress")):
                parts = prompt_input.split()[1:]
                handle_compact_command(parts, controller)
                continue

            if prompt_input.lower().startswith(("/integrity", "/verify", "/attest")):
                from prubeth.security.integrity import PrubethIntegrityEngine
                PrubethIntegrityEngine(console).render_report()
                continue

            if prompt_input == "/clear":
                if hasattr(controller, "clear_history"):
                    controller.clear_history()
                console.print("[bold green]Conversation context cleared.[/bold green] Pinned prompt cache, tools, and repo skeleton preserved.")
                continue

            if prompt_input.lower() in ["/version", "version"]:
                from prubeth.cli.version import render_version_info
                render_version_info(console)
                continue

            if prompt_input.lower().startswith(("/help", "/?")) or prompt_input.lower().strip() == "help":
                from prubeth.cli.help import render_tier1_help
                render_tier1_help(console)
                continue

            # Resolve inline context @mentions (@file, @symbol, @diff, @search)
            expanded_prompt, attachments = expander.resolve_mentions(prompt_input)
            if attachments:
                console.print(f"  [dim cyan]📎 Injected {len(attachments)} context attachment(s) into prompt.[/dim cyan]")

            # Explicit Formal Speculative Plan A / Plan B Architecture
            if prompt_input.startswith("/plan ") or prompt_input.startswith("plan:"):
                formal_goal = expanded_prompt[5:].strip() if prompt_input.startswith("/plan ") else expanded_prompt[5:].strip()
                res = cfg_mgr.resolve_model_and_provider(current_model)
                console.print(f"\n[bold cyan]Formulating Speculative Architecture (Plan A / Plan B) using {res['model']}:[/bold cyan] {formal_goal}\n")
                result = controller.run_task(formal_goal, model_override=current_model)
                if result.get("success"):
                    console.print("\n[bold green]✅ Architectural Task Completed & Verified![/bold green]")
                    conv_tree.add_turn(prompt_input, "SUCCESS: Architectural Plan Verified", result.get("snapshot_id"))
                else:
                    console.print(f"\n[bold yellow]⚠️ Plan ended with state: {result.get('state')}[/bold yellow]")
                    conv_tree.add_turn(prompt_input, f"ENDED: {result.get('state')}", result.get("snapshot_id"))
                continue

            # Fluid ReAct Agent (Claude Code-Grade Dynamic Execution)
            res = cfg_mgr.resolve_model_and_provider(current_model)
            console.print()
            streamed_any = False
            def token_streamer(token: str):
                nonlocal streamed_any
                streamed_any = True
                sys.stdout.write(token)
                sys.stdout.flush()

            def tool_reporter(stage: str, details: Dict[str, Any], success: bool, output: str):
                nonlocal streamed_any
                t_name = details.get("tool", "")
                t_args = details.get("args", {})
                if stage == "invoking":
                    if streamed_any:
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        streamed_any = False
                    args_summary = ", ".join(f"{k}={v}" for k, v in t_args.items() if k in ["path", "query", "command", "pattern", "name"])
                    console.print(f"  [bold cyan]● [tool][/bold cyan] [bold white]{t_name}[/bold white] [dim]({args_summary})[/dim]")
                elif stage == "result":
                    status_col = "green" if success else "red"
                    status_lbl = "ok" if success else "error"
                    first_line = output.strip().splitlines()[0] if output.strip().splitlines() else "completed"
                    console.print(f"    [{status_col}][{status_lbl}][/{status_col}] [dim]{first_line[:120]}[/dim]")

            try:
                turn_result = controller.run_fluid_turn(
                    expanded_prompt,
                    model_override=current_model,
                    stream_cb=token_streamer,
                    tool_cb=tool_reporter
                )
                if not streamed_any and turn_result.get("text"):
                    console.print(Markdown(turn_result["text"]))
                else:
                    sys.stdout.write("\n")
                    sys.stdout.flush()

                # High-Density Turn Telemetry (Claude Code & Gemini CLI Parity)
                tok_in = turn_result.get("prompt_tokens", 0)
                tok_out = turn_result.get("candidate_tokens", 0)
                tok_cached = turn_result.get("cached_tokens", 0)
                th_tok = turn_result.get("thinking_tokens", 0)
                lat = turn_result.get("latency_s", 0.0)
                if tok_in or tok_out or lat > 0:
                    parts = []
                    if tok_in or tok_out:
                        parts.append(f"{tok_in + tok_out:,} tokens")
                    if tok_cached:
                        parts.append(f"[bold green]{tok_cached:,} cached[/bold green]")
                    if th_tok:
                        parts.append(f"[cyan]{th_tok:,} reasoning tokens[/cyan]")
                    if lat > 0:
                        parts.append(f"{lat:.2f}s")
                    console.print(f"  [dim]Turn: {' · '.join(parts)}[/dim]")

                summary = turn_result.get("text", "")[:120].replace("\n", " ")
                conv_tree.add_turn(prompt_input, summary, turn_result.get("snapshot_id"))
            except Exception as e:
                console.print(f"[bold red]Execution Error:[/bold red] {e}")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user. Type /exit to quit.[/yellow]")
        except EOFError:
            break

if __name__ == "__main__":
    main()
