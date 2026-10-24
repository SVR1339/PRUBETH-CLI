"""PRUBETH Phase 2 CLI Command Handlers.

Implements multi-agent swarm inspection, shadow worktree management,
continuous memory vault review, and PRUBETH IDE bridge diagnostics.
Enforces PRINCE3 Zero Font Blur standard and SE 3.0 deterministic invariants.
"""

import sys
import os
import socket
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

from prubeth.agents.base import SubagentRole, SubagentState
from prubeth.agents.subagent import SubagentManager
from prubeth.agents.worktree import WorktreeManager
from prubeth.persistence.memory import MemoryVault
from prubeth.integrations.ide_bridge import IDEBridgeServer
from prubeth.config.manager import ConfigManager

console = Console(legacy_windows=False)

def handle_swarm_command(args: List[str], controller: Any = None):
    """Handles 'prubeth swarm' or '/swarm' commands."""
    subagent_mgr: SubagentManager = (
        controller.subagent_mgr if controller and hasattr(controller, "subagent_mgr")
        else SubagentManager()
    )

    action = args[0].lower() if args else "list"

    if action in ["list", "status"]:
        agents = subagent_mgr.list_subagents()
        if not agents:
            console.print(Panel(
                "[dim]No subagents have executed in this session yet.[/dim]\n"
                "[cyan]Spawn a subagent with:[/cyan] /swarm spawn <architect|coder|critic|test_engineer|docs> <goal>",
                title="🐝 PRUBETH Multi-Agent Swarm Status",
                border_style="cyan",
                box=box.ROUNDED
            ))
            return

        table = Table(title="🐝 Active & Historical Multi-Agent Swarm Telemetry", box=box.ROUNDED)
        table.add_column("Subagent ID", style="bold cyan")
        table.add_column("Role", style="magenta")
        table.add_column("State", style="yellow")
        table.add_column("AST / Critic", style="green")
        table.add_column("Turns", justify="right", style="cyan")
        table.add_column("Modified Files", style="dim")

        for a in agents:
            critic_badge = "[bold green]APPROVED[/bold green]" if a.get("critic_approved") else "[bold red]REJECTED[/bold red]"
            state_color = "green" if a.get("state") == "MERGED" else ("yellow" if a.get("state") == "RUNNING" else "red")
            state_str = f"[{state_color}]{a.get('state')}[/{state_color}]"
            files_str = ", ".join(a.get("modified_files", [])) or "None"
            table.add_row(
                a["id"],
                a["role"].upper(),
                state_str,
                critic_badge,
                str(a.get("turns", 0)),
                files_str
            )
        console.print(table)

    elif action == "roles":
        table = Table(title="Available Multi-Agent Swarm Roles (AGENTIC SDLC)", box=box.ROUNDED)
        table.add_column("Role Identifier", style="bold cyan")
        table.add_column("Mandate", style="white")
        table.add_column("Isolation Sandbox", style="yellow")

        table.add_row("architect", "Decompose complex user goals into invariant-driven micro-tasks", "Read-only Workspace")
        table.add_row("coder", "Implement code changes inside isolated shadow worktree", "Isolated Shadow Worktree")
        table.add_row("critic", "Adversarial red-team auditor: checks security, anti-patterns, regressions", "Diff Analysis Gate")
        table.add_row("test_engineer", "Write & execute invariant unit tests before root merge", "Isolated Shadow Worktree")
        table.add_row("docs", "Generate technical Markdown specifications and docstrings", "Workspace Root")
        console.print(table)

    elif action == "spawn":
        if len(args) < 3:
            console.print("[yellow]Usage: /swarm spawn <role> <goal>[/yellow]")
            console.print("[dim]Example: /swarm spawn coder 'Add health check endpoint to server.py'[/dim]")
            return

        role_str = args[1].lower()
        goal = " ".join(args[2:])

        try:
            role = SubagentRole(role_str)
        except ValueError:
            valid_roles = ", ".join(r.value for r in SubagentRole)
            console.print(f"[bold red]Invalid Role:[/bold red] '{role_str}'. Choose from: {valid_roles}")
            return

        console.print(f"\n[bold cyan]🐝 Spawning Worker:[/bold cyan] [{role.value.upper()}] | [dim]Task:[/dim] {goal}")
        spec = subagent_mgr.spawn_subagent(role=role, goal=goal)
        console.print(f"  [dim cyan]-> Worktree Sandboxed at:[/dim cyan] {spec.worktree_path}")

        result = subagent_mgr.run_subagent(spec)

        if result.success:
            console.print(Panel(
                f"[bold green]Subagent Completed & Merged Successfully![/bold green]\n"
                f"- **Subagent ID**: {result.subagent_id}\n"
                f"- **Role**: {result.role.value}\n"
                f"- **Critic Verdict**: {'Approved' if result.critic_approved else 'Bypassed'}\n"
                f"- **Modified Files**: {', '.join(result.modified_files) if result.modified_files else 'None'}\n"
                f"- **Output**: {result.output}",
                title="🐝 Subagent Consensus Pass",
                border_style="green",
                box=box.ROUNDED
            ))
        else:
            console.print(Panel(
                f"[bold red]Subagent Execution Failed / Critic Blocked:[/bold red]\n"
                f"- **Subagent ID**: {result.subagent_id}\n"
                f"- **Critic Notes**: {result.critic_notes}\n"
                f"- **Output**: {result.output}",
                title="❌ Subagent Consensus Rejection",
                border_style="red",
                box=box.ROUNDED
            ))
    else:
        console.print("[yellow]Usage: /swarm [list | roles | spawn <role> <goal>][/yellow]")

def handle_worktrees_command(args: List[str], controller: Any = None):
    """Handles 'prubeth worktrees' or '/worktrees' commands."""
    workspace_root = controller.workspace_root if controller else Path.cwd()
    wt_mgr = WorktreeManager(workspace_root)

    action = args[0].lower() if args else "list"

    if action in ["list", "status"]:
        active = wt_mgr.list_active_worktrees()
        if not active:
            console.print(Panel(
                "[dim]No shadow worktrees currently active in .prubeth/worktrees/[/dim]",
                title="📂 PRUBETH Shadow Worktree Subsystem",
                border_style="cyan",
                box=box.ROUNDED
            ))
            return

        table = Table(title="📂 Active Shadow Worktree Sandboxes", box=box.ROUNDED)
        table.add_column("Subagent / Worktree ID", style="bold cyan")
        table.add_column("Path", style="dim")
        table.add_column("Modified Files", style="yellow")
        table.add_column("Status", style="green")

        for wt in active:
            wt_id = wt["subagent_id"] if isinstance(wt, dict) else str(wt)
            wt_path = wt["path"] if isinstance(wt, dict) and "path" in wt else str(wt_mgr.get_worktree_path(wt_id))
            diff_info = wt_mgr.get_worktree_diff(wt_id)
            mod_count = len(diff_info["modified"]) + len(diff_info["added"])
            table.add_row(
                wt_id,
                wt_path,
                f"{mod_count} files changed",
                "[green]ISOLATED[/green]"
            )
        console.print(table)

    elif action == "diff":
        if len(args) < 2:
            console.print("[yellow]Usage: /worktrees diff <subagent_id>[/yellow]")
            return
        wt_id = args[1]
        try:
            diff_info = wt_mgr.get_worktree_diff(wt_id)
            if diff_info["diff"]:
                console.print(Panel(
                    diff_info["diff"],
                    title=f"Unified Diff: Worktree '{wt_id}' vs Root",
                    border_style="blue",
                    box=box.ROUNDED
                ))
            else:
                console.print(f"[dim]No modifications detected in worktree '{wt_id}'.[/dim]")
        except Exception as e:
            console.print(f"[bold red]Worktree Diff Error:[/bold red] {e}")

    elif action == "clean":
        count = wt_mgr.cleanup_all_worktrees()
        console.print(f"[bold green]Cleaned up {count} shadow worktree sandboxes.[/bold green]")
    else:
        console.print("[yellow]Usage: /worktrees [list | diff <subagent_id> | clean][/yellow]")

def handle_memory_command(args: List[str], controller: Any = None):
    """Handles 'prubeth memory' or '/memory' commands."""
    mem_vault = controller.memory_vault if controller and hasattr(controller, "memory_vault") else MemoryVault()

    action = args[0].lower() if args else "summary"

    if action in ["summary", "status", "list"]:
        anti_pats = mem_vault.get_anti_patterns()
        decisions = mem_vault.get_decisions()

        console.print(Panel(
            f"🧠 **Continuous Intelligence Vault Metrics**\n"
            f"- **Learned Anti-Patterns**: {len(anti_pats)} failure rules registered\n"
            f"- **Architectural Decisions (ADRs)**: {len(decisions)} invariant records\n"
            f"- **Storage Path**: `{mem_vault.memory_dir}`\n\n"
            f"[dim]Run `/memory anti-patterns` or `/memory decisions` to inspect full records.[/dim]",
            title="🧠 PRUBETH Continuous Memory Vault (SE 3.0)",
            border_style="cyan",
            box=box.ROUNDED
        ))

    elif action in ["anti-patterns", "antipatterns", "rules"]:
        anti_pats = mem_vault.get_anti_patterns()
        if not anti_pats:
            console.print("[dim]No anti-patterns recorded yet. Memory ledger is clean.[/dim]")
            return

        table = Table(title="⚠️ Learned Project Anti-Patterns (Regression Prevention)", box=box.ROUNDED)
        table.add_column("Component", style="bold cyan")
        table.add_column("Error Symptom", style="red")
        table.add_column("Root Cause", style="yellow")
        table.add_column("Rule to Prevent Recurrence", style="bold green")

        for ap in anti_pats:
            table.add_row(
                ap.get("component", "General"),
                ap.get("symptom", "N/A"),
                ap.get("root_cause", "N/A"),
                ap.get("prevention_rule", "N/A")
            )
        console.print(table)

    elif action in ["decisions", "adrs"]:
        decisions = mem_vault.get_decisions()
        if not decisions:
            console.print("[dim]No architectural decisions recorded yet.[/dim]")
            return

        table = Table(title="📐 Architectural Decision Records (ADRs)", box=box.ROUNDED)
        table.add_column("Decision Title", style="bold cyan")
        table.add_column("Affected Modules", style="magenta")
        table.add_column("Rationale", style="white")

        for d in decisions:
            table.add_row(
                d.get("title", "Invariant"),
                d.get("affected_modules", "Core"),
                d.get("rationale", "N/A")
            )
        console.print(table)

    elif action == "record":
        if len(args) < 4:
            console.print("[yellow]Usage: /memory record <component> <error_symptom> <prevention_rule>[/yellow]")
            return
        comp = args[1]
        symptom = args[2]
        rule = " ".join(args[3:])
        mem_vault.record_anti_pattern(
            failing_component=comp,
            error_symptom=symptom,
            root_cause="Manual developer injection",
            prevention_rule=rule
        )
        console.print(f"[bold green]Successfully recorded anti-pattern rule for '{comp}'.[/bold green]")
    else:
        console.print("[yellow]Usage: /memory [summary | anti-patterns | decisions | record <comp> <symptom> <rule>][/yellow]")

def handle_bridge_command(args: List[str], controller: Any = None):
    """Handles 'prubeth bridge' or '/bridge' commands."""
    action = args[0].lower() if args else "status"

    if action in ["status", "info"]:
        bridge = controller.ide_bridge if controller and hasattr(controller, "ide_bridge") else None
        is_running = bridge.running if bridge else False
        clients = bridge.client_count if bridge else 0

        console.print(Panel(
            f"🔌 **PRUBETH IDE Bridge IPC Gateway**\n"
            f"- **Server Running**: [{'bold green' if is_running else 'bold yellow'}]{'YES (Active)' if is_running else 'STANDBY'}[/{'bold green' if is_running else 'bold yellow'}]\n"
            f"- **Socket Endpoint**: `127.0.0.1:{IDEBridgeServer.DEFAULT_PORT}`\n"
            f"- **Named Pipe Endpoint**: `{IDEBridgeServer.NAMED_PIPE_NAME}`\n"
            f"- **Connected GUI Clients**: [bold cyan]{clients}[/bold cyan]\n"
            f"- **Protocol**: `prubeth.ipc/v1` (NDJSON live telemetry)\n\n"
            f"[dim]Run `/bridge ping` to verify loopback socket responsiveness.[/dim]",
            title="🔌 PRUBETH IDE Named-Pipe & Socket IPC Bridge",
            border_style="magenta",
            box=box.ROUNDED
        ))

    elif action == "ping":
        # Test connection to port 28888
        t0 = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", IDEBridgeServer.DEFAULT_PORT))
            sock.sendall(json.dumps({"command": "ping"}).encode("utf-8") + b"\n")
            sock.close()
            latency = round((time.time() - t0) * 1000, 2)
            console.print(f"[bold green]✅ IPC Bridge Loopback Responded in {latency}ms[/bold green]")
        except Exception as e:
            console.print(f"[bold red]❌ Bridge Ping Failed:[/bold red] {e} (Ensure bridge server is active)")
    else:
        console.print("[yellow]Usage: /bridge [status | ping][/yellow]")

def handle_consensus_command(args: List[str], controller: Any = None):
    """Displays multi-agent consensus quorum and pre-flight gate invariants."""
    table = Table(title="🛡️ PRUBETH Pre-Flight AST & Adversarial Consensus Gates (SE 3.0)", box=box.ROUNDED)
    table.add_column("Verification Gate", style="bold cyan")
    table.add_column("Invariant / Rule", style="white")
    table.add_column("Execution Point", style="yellow")
    table.add_column("Action on Failure", style="red")

    table.add_row(
        "Gate 1: In-Memory AST Compiler",
        "Target .py file must parse into a valid Python Abstract Syntax Tree",
        "Pre-disk write / Pre-commit",
        "Immediate rejection; subagent halts before touching disk"
    )
    table.add_row(
        "Gate 2: Red-Team Adversarial Critic",
        "Diff must contain zero plaintext API secrets and zero destructive delete commands",
        "Post-tool modification in shadow worktree",
        "Subagent failure; diff discarded; memory anti-pattern logged"
    )
    table.add_row(
        "Gate 3: Independent Verifier",
        "Unit test suite and linters must exit code 0 inside the worktree",
        "Pre-root merge",
        "Auto-pivot to Plan B or rollback to snapshot"
    )
    table.add_row(
        "Gate 4: Continuous Memory Ingestion",
        "Root cause of any runtime failure is recorded to anti-patterns.md",
        "Post-recovery failure loop",
        "Rule injected into future planner system prompts"
    )

    console.print(table)

def handle_mcp_command(args: List[str], controller: Any = None):
    """Handles 'prubeth mcp' or '/mcp' commands."""
    from prubeth.mcp.manager import MCPManager
    mcp_mgr: MCPManager = (
        controller.mcp if controller and hasattr(controller, "mcp")
        else MCPManager()
    )

    action = args[0].lower() if args else "list"

    if action in ["list", "status"]:
        servers = mcp_mgr.list_servers()
        if not servers:
            console.print(Panel(
                "[dim]No external Model Context Protocol (MCP) servers registered.[/dim]\n"
                "[cyan]Register an MCP server with:[/cyan] /mcp add <name> <command> [args...]\n"
                "[dim]Example: /mcp add sqlite uvx mcp-server-sqlite --db-path ./app.db[/dim]",
                title="🔌 Model Context Protocol (MCP) Registry",
                border_style="cyan",
                box=box.ROUNDED
            ))
            return

        table = Table(title="🔌 Registered MCP Servers & Tool Providers", box=box.ROUNDED)
        table.add_column("Server Name", style="bold cyan")
        table.add_column("Command", style="white")
        table.add_column("Connection Status", style="green")
        table.add_column("Discovered Tools", justify="right", style="yellow")
        table.add_column("Resources", justify="right", style="magenta")

        for s in servers:
            status = "[bold green]CONNECTED[/bold green]" if s["connected"] else "[dim yellow]STANDBY[/dim yellow]"
            cmd_str = f"{s['command']} {' '.join(s['args'])}".strip()
            table.add_row(
                s["name"],
                cmd_str,
                status,
                str(s["tools_count"]),
                str(s["resources_count"])
            )
        console.print(table)

    elif action == "tools":
        all_tools = mcp_mgr.get_all_tools()
        if not all_tools:
            console.print("[dim]No tools discovered from registered MCP servers. (Ensure servers are running)[/dim]")
            return

        table = Table(title="🛠️ Discovered MCP Tools (JSON-RPC 2.0)", box=box.ROUNDED)
        table.add_column("Tool Namespace", style="bold cyan")
        table.add_column("Origin Server", style="magenta")
        table.add_column("Description", style="white")

        for t in all_tools:
            table.add_row(
                t["name"],
                t["server"],
                t["description"]
            )
        console.print(table)

    elif action == "add":
        if len(args) < 3:
            console.print("[yellow]Usage: /mcp add <name> <command> [args...][/yellow]")
            return
        name = args[1]
        cmd = args[2]
        s_args = args[3:] if len(args) > 3 else []
        mcp_mgr.register_server(name, cmd, s_args)

        # Save to mcp.json
        cfg_path = mcp_mgr.config_path
        data = {"mcpServers": {}}
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        if "mcpServers" not in data:
            data["mcpServers"] = {}
        data["mcpServers"][name] = {"command": cmd, "args": s_args}
        cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        console.print(f"[bold green]Successfully registered MCP server '{name}'.[/bold green]")

    elif action == "remove":
        if len(args) < 2:
            console.print("[yellow]Usage: /mcp remove <name>[/yellow]")
            return
        name = args[1]
        mcp_mgr.unregister_server(name)

        cfg_path = mcp_mgr.config_path
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                if "mcpServers" in data and name in data["mcpServers"]:
                    del data["mcpServers"][name]
                    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass
        console.print(f"[bold green]Unregistered MCP server '{name}'.[/bold green]")

    elif action == "call":
        if len(args) < 3:
            console.print("[yellow]Usage: /mcp call <server> <tool> [arguments_json][/yellow]")
            return
        s_name = args[1]
        t_name = args[2]
        raw_args = args[3] if len(args) > 3 else "{}"
        try:
            parsed_args = json.loads(raw_args)
        except Exception:
            parsed_args = {"input": raw_args}

        success, res = mcp_mgr.call_mcp_tool(s_name, t_name, parsed_args)
        status_color = "green" if success else "red"
        console.print(Panel(res, title=f"MCP Result: {s_name}::{t_name}", border_style=status_color, box=box.ROUNDED))

    else:
        console.print("[yellow]Usage: /mcp [list | tools | add <name> <cmd> [args] | remove <name> | call <server> <tool> [args]][/yellow]")

