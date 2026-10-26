import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from prubeth.cli.version import PRUBETH_VERSION

def render_tier1_help(console: Console):
    """Renders Google/Anthropic-standard comprehensive CLI documentation."""
    console.print(Panel(
        f"[bold cyan]PRUBETH Autonomous Developer CLI[/bold cyan] — [bold white]v{PRUBETH_VERSION}[/bold white] [bold green](FRONTIER PARITY Edition)[/bold green]\n"
        "[dim]Silicon Valley Production Autonomous Engineering Engine & Pair-Programming Runtime (Apache-2.0)[/dim]",
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
    cmds_table.add_row("Code Intelligence", "search <query>", "Pure-Python BM25 semantic codebase search and AST symbol indexer.")
    cmds_table.add_row("", "symbols", "List all workspace class and function definitions with signatures.")
    cmds_table.add_row("", "callers <symbol>", "DeepMind Monorepo AST reference tracker: find all callers and usages.")
    cmds_table.add_row("", "heal \"<command>\"", "Autonomous Auto-TDD self-healing loop: intercepts errors, applies patch, auto-rolls back on failure.")
    cmds_table.add_row("", "cost / spend", "Real-time token expenditure, latency percentiles, and LLMOps radar.")
    cmds_table.add_row("", "cache / kvcache", "Multi-Tier Prompt KV & Context Cache Radar HUD (TTL, dollar savings).")
    cmds_table.add_row("", "compact", "Claude Code parity: compress multi-turn history into pinned prefix scratchpad.")
    cmds_table.add_row("", "timeline / snaps", "Zero-git snapshot rollback with visual time-travel DAG.")
    cmds_table.add_row("", "history / tree", "Display visual conversation decision tree, branches, and checkpoint nodes.")
    cmds_table.add_row("", "memory [anti-patterns]", "Inspect continuous intelligence, learned anti-patterns, and design decisions.")
    cmds_table.add_row("", "learn <directive>", "Persist user directives & architectural invariants permanently into Memory Vault.")
    cmds_table.add_row("", "rollback", "Instantly revert workspace to the latest clean snapshot checkpoint.")
    cmds_table.add_row("", "diff", "View pure-Python working tree code modifications and deltas.")

    # Autonomous Engineering & Git
    cmds_table.add_row("Autonomous Workflows", "goal <objective>", "Anthropic Claude Code target: long-horizon milestone decomposition & execution loop.")
    cmds_table.add_row("", "commit [-y]", "Synthesize conventional semantic commit message from uncommitted working tree diff.")
    cmds_table.add_row("", "pr", "Synthesize GitHub Pull Request description with test evidence into .prubeth/PULL_REQUEST.md.")
    cmds_table.add_row("", "issue <ticket>", "Autonomous zero-babysitting GitHub issue resolver with auto-TDD verification.")
    cmds_table.add_row("", "migrate <objective>", "Monorepo-scale migration runner with topological file order & interface protection.")

    # Frontier Superintelligence & Research
    cmds_table.add_row("Frontier AI & Monorepo", "autotune <kernel>", "OpenAI target: autonomous Triton/CUDA GPU kernel synthesis & autotuning.")
    cmds_table.add_row("", "research <hypothesis>", "OpenAI/DeepMind target: closed-loop AI research & empirical ablation studies.")
    cmds_table.add_row("", "janitor [scan|fix]", "DeepMind monorepo target: SRE security vulnerability audit & automated healing.")
    cmds_table.add_row("", "bio [inspect|manifest]", "Computational biology bridge: parse PDB/mmCIF & AlphaFold pLDDT metrics.")

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
