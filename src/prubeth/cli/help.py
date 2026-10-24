import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

def render_tier1_help(console: Console):
    """Renders Google/Anthropic-standard comprehensive CLI documentation."""
    console.print(Panel(
        "[bold cyan]PRUBETH Autonomous Developer CLI[/bold cyan] — [bold white]v1.0.0[/bold white]\n"
        "[dim]Elite Multi-Model Autonomous Software Engineering Runtime (Apache-2.0)[/dim]",
        border_style="cyan"
    ))

    console.print("[bold yellow]USAGE:[/bold yellow]")
    console.print("  prubeth [bold white][OPTIONS][/bold white] [bold cyan][\"GOAL STATEMENT\"][/bold cyan]       Execute autonomous goal in single-shot mode")
    console.print("  prubeth [bold green]<COMMAND>[/bold green] [dim][ARGS...][/dim]                          Execute subcommands and workflows")
    console.print("  prubeth                                         Launch interactive PRINCE3 Terminal REPL Cockpit\n")

    # Options Table
    opts_table = Table(title="CORE CLI OPTIONS", border_style="cyan", show_header=True)
    opts_table.add_column("Flag / Option", style="bold cyan", width=28)
    opts_table.add_column("Description", style="white")
    opts_table.add_row("-a, --auto", "Auto-approve non-destructive actions (CI/headless mode).")
    opts_table.add_row("-m, --model <name>", "Override active AI model (e.g. gemini-3.1-pro-preview, qwen2.5-coder:7b).")
    opts_table.add_row("--profile <name>", "Apply operational profile: builder, deep-reasoning, local-airgap, safe-audit.")
    opts_table.add_row("--local", "Force execution through local offline engine (Ollama :11434 / LM Studio :1234).")
    opts_table.add_row("--output-format <fmt>", "Output mode: 'text' (Rich terminal ANSI) or 'stream-json' (NDJSON).")
    opts_table.add_row("-v, --version", "Display full version, OS architecture, and zero-telemetry certification.")
    opts_table.add_row("-h, --help", "Display this comprehensive command reference.")
    console.print(opts_table)
    console.print()

    # Commands Table
    cmds_table = Table(title="OPERATIONAL COMMANDS & WORKFLOWS", border_style="green", show_header=True)
    cmds_table.add_column("Command Category", style="bold yellow", width=22)
    cmds_table.add_column("Subcommand", style="bold green", width=24)
    cmds_table.add_column("Functionality & Enterprise Purpose", style="white")

    # Diagnostics
    cmds_table.add_row("System Diagnostics", "doctor / diagnose", "Run 8-pillar preflight qualification suite (memory, sandbox, providers).")
    cmds_table.add_row("", "version [--json]", "Display runtime architecture, encoding, license, and build signature.")
    cmds_table.add_row("", "settings / status", "Open visual Performance HUD and inspection of all 20+ runtime settings.")
    cmds_table.add_row("", "tune / builder", "Launch live Performance Builder & compute SPI benchmark.")

    # Setup
    cmds_table.add_row("Setup & Recovery", "setup / onboarding", "Launch interactive onboarding, API key wizard, and local Ollama guide.")
    cmds_table.add_row("", "therapy / heal", "Execute 7-pillar system therapy, config drift auto-remediation & WAL maintenance.")
    cmds_table.add_row("", "configure --deep", "Launch multi-step deep configuration wizard for fine-grained tuning.")
    cmds_table.add_row("", "reset", "Execute factory default reset to restore clean initial onboarding state.")

    # Multi-Agent Swarm
    cmds_table.add_row("Agentic Swarm", "swarm [roles|spawn]", "Orchestrate 5 specialized agents (Architect, Coder, Critic, Test, Docs).")
    cmds_table.add_row("", "worktrees [list|diff]", "Manage git-less shadow worktrees for zero-risk speculative execution.")
    cmds_table.add_row("", "consensus", "Enforce multi-agent AST & red-team safety consensus invariants.")

    # Intelligence & Memory
    cmds_table.add_row("Memory & Safety", "memory [anti-patterns]", "Inspect continuous intelligence, learned anti-patterns, and design decisions.")
    cmds_table.add_row("", "rollback", "Instantly revert workspace to the latest clean snapshot checkpoint.")
    cmds_table.add_row("", "diff", "View pure-Python working tree code modifications and deltas.")

    # Protocols & Shell
    cmds_table.add_row("Protocols & Shell", "mcp [list|tools|add]", "Manage Model Context Protocol (MCP) tool servers and JSON-RPC dispatch.")
    cmds_table.add_row("", "bridge [status|ping]", "Inspect IDE IPC Named Pipe (Windows) / Unix socket bridge.")
    cmds_table.add_row("", "completion <shell>", "Generate native tab completions for powershell, bash, or zsh.")
    cmds_table.add_row("", "models", "List all supported cloud and local models with prompt caching metadata.")

    console.print(cmds_table)
    console.print("\n [bold cyan]Examples:[/bold cyan]")
    console.print("  prubeth \"Build a FastAPI microservice with authentication and pytest suite\"")
    console.print("  prubeth -a --profile deep-reasoning \"Analyze codebase memory leaks and refactor\"")
    console.print("  prubeth doctor")
    console.print("  prubeth setup")
    console.print("  prubeth completion powershell >> $PROFILE\n")
