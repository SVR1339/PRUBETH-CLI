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
    handle_mcp_command
)
from prubeth.cli.setup import render_onboarding_wizard, execute_factory_reset

# Initialize Rich Console with modern ANSI rendering (zero subpixel blur, no legacy cp1252 truncation)
console = Console(legacy_windows=False)

def print_banner():
    banner = r"""
  ██████╗ ██████╗ ██╗   ██╗██████╗ ███████╗████████╗██╗  ██╗
  ██╔══██╗██╔══██╗██║   ██║██╔══██╗██╔════╝╚══██╔══╝██║  ██║
  ██████╔╝██████╔╝██║   ██║██████╔╝█████╗     ██║   ███████║
  ██╔═══╝ ██╔══██╗██║   ██║██╔══██╗██╔══╝     ██║   ██╔══██║
  ██║     ██║  ██║╚██████╔╝██████╔╝███████╗   ██║   ██║  ██║
  ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝
"""
    console.print(f"[bold cyan]{banner}[/bold cyan]")
    cfg_mgr = ConfigManager()
    resolved = cfg_mgr.resolve_model_and_provider()
    profile = cfg_mgr.get_active_profile_info()
    
    console.print(f" [dim]Profile:[/dim] [bold green]{profile['badge']}[/bold green] ({profile['name']}) | [dim]Model:[/dim] [bold cyan]{resolved['model']}[/bold cyan] ({resolved['provider']})")
    console.print(f" [dim]Prompt Caching:[/dim] [green]ENABLED (Prefix KV Cache Pinned)[/green] | [dim]Resilience:[/dim] [green]PLAN B ARMED[/green]")
    console.print(" [dim]Type /settings for dashboard, /tune for Performance Builder, /inspect <key>, or prompt to start.[/dim]\n")

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
    """Prompts human developer for approval when required."""
    if action_type == "plan_approval":
        console.print("[bold yellow]Do you approve this execution plan? (y/n):[/bold yellow] ", end="")
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

def handle_models_command(args: list):
    cfg_mgr = ConfigManager()
    from prubeth.models.gateway import UniversalModelGateway
    gw = UniversalModelGateway(cfg_mgr)
    cfg = cfg_mgr.load_config()
    keys = cfg.get("api_keys", {})
    timeout_s = cfg.get("cloud_timeout_s", 12)

    if not args or args[0] == "list":
        # Table 1: Strict Highest-to-Lowest Model Preference Hierarchy
        h_table = Table(title="PRUBETH Hierarchical Model Preference Chain (Highest to Lowest)")
        h_table.add_column("Tier / Capability", style="cyan")
        h_table.add_column("Ranked Models (Highest → Lowest)", style="green")
        h_table.add_column("Primary Purpose", style="yellow")
        h_table.add_column("Fallback Trigger", style="magenta")

        h_table.add_row(
            "Tier 1: Flagship Frontier Pro",
            "gemini-3.1-pro-preview, gemini-pro-latest, openrouter/free",
            "Deep reasoning, system architecture, complex refactoring",
            "Rate limit (429) or cloud timeout"
        )
        h_table.add_row(
            "Tier 2: High-Performance Balanced",
            "gemini-3.5-flash, gemini-flash-latest, nvidia/nemotron-3.5-lightning:free, cohere/north-mini-code:free",
            "High-throughput autonomous coding and tool synthesis",
            "Degradation (503) or quota exhaustion"
        )
        h_table.add_row(
            "Tier 3: Ultra-Fast Lightweight",
            "gemini-3.1-flash-lite, google/gemma-4-31b-it:free, google/gemma-4-26b-a4b-it:free",
            "Sub-second verification and rapid sanity checks",
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
            cfg_mgr = ConfigManager()
            render_onboarding_wizard(console, cfg_mgr)
            return
        if cmd in ["doctor", "check", "diagnose"]:
            from prubeth.cli.doctor import PrubethDoctor
            PrubethDoctor(console).render_report()
            return
        if cmd == "completion":
            from prubeth.cli.completions import generate_powershell_completion, generate_bash_completion, generate_zsh_completion
            shell = sys.argv[2].lower() if len(sys.argv) > 2 else "powershell"
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
            from prubeth.security.permissions import SecurityEngine
            from prubeth.persistence.database import TaskDatabase
            from prubeth.tools.execution import ToolExecutionEngine
            sec = SecurityEngine()
            db = TaskDatabase(str(Path.cwd() / ".prubeth" / "prubeth.db"))
            tool_engine = ToolExecutionEngine(sec, db, "diff_check")
            _, diff_out = tool_engine.execute_tool("git_diff", {})
            console.print(Panel(diff_out or "[dim]No changes in working tree[/dim]", title="Working Tree Diff", border_style="blue"))
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
    while True:
        try:
            p_info = cfg_mgr.get_active_profile_info()
            prompt_input = input(f"\n[prubeth:{p_info['name'].split()[0].lower()}] ❯ ").strip()
            if not prompt_input:
                continue

            if prompt_input.lower() in ["/exit", "exit", "quit"]:
                console.print("[yellow]Exiting PRUBETH CLI. Goodbye![/yellow]")
                break

            if prompt_input in ["/settings", "/status"]:
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

            if prompt_input.startswith("/model"):
                parts = prompt_input.split()
                if len(parts) > 1:
                    current_model = parts[1]
                    cfg_mgr.set("default_model", current_model)
                    res = cfg_mgr.resolve_model_and_provider(current_model)
                    console.print(f"[bold green]Switched active model to:[/bold green] {res['model']} ({res['provider']})")
                else:
                    res = cfg_mgr.resolve_model_and_provider(current_model)
                    console.print(f"[cyan]Current model:[/cyan] {res['model']} ({res['provider']})")
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

            if prompt_input.lower() in ["/version", "version"]:
                from prubeth.cli.version import render_version_info
                render_version_info(console)
                continue

            if prompt_input.lower() in ["/help", "help", "/?"]:
                from prubeth.cli.help import render_tier1_help
                render_tier1_help(console)
                continue

            # Conversational Chat vs. Autonomous Engineering Task
            if not is_engineering_task(prompt_input):
                res = cfg_mgr.resolve_model_and_provider(current_model)
                with console.status(f"[dim cyan]Thinking with {res['model']}...[/dim cyan]", spinner="dots"):
                    chat_resp = controller.chat(prompt_input, model_override=current_model)
                console.print()
                console.print(Markdown(chat_resp.text))
                continue

            # Run autonomous goal
            goal = prompt_input[5:].strip() if prompt_input.startswith("/auto") else prompt_input
            res = cfg_mgr.resolve_model_and_provider(current_model)
            console.print(f"\n[bold cyan]Working on task using {res['model']} ({res['provider']}):[/bold cyan] {goal}\n")
            result = controller.run_task(goal, model_override=current_model)

            if result.get("success"):
                console.print("\n[bold green]✅ Task Completed & Verified![/bold green]")
            else:
                console.print(f"\n[bold yellow]⚠️ Task ended with state: {result.get('state')}[/bold yellow]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user. Type /exit to quit.[/yellow]")
        except EOFError:
            break

if __name__ == "__main__":
    main()
