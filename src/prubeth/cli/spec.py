"""PRUBETH Specification-Driven Development (SDD) Contract.

Formally defines the complete CLI command syntax, option arguments,
validation schemas, and return exit codes before execution.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass(frozen=True)
class CommandOptionSpec:
    name: str
    flags: List[str]
    type_name: str
    default: Any
    description: str
    choices: Optional[List[str]] = None

@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    usage: str
    options: List[CommandOptionSpec] = field(default_factory=list)
    subcommands: List[str] = field(default_factory=list)
    expected_exit_codes: Dict[int, str] = field(default_factory=lambda: {
        0: "SUCCESS",
        1: "GENERAL_ERROR",
        2: "SYNTAX_OR_CLI_ARGUMENT_ERROR",
        130: "INTERRUPTED_BY_USER_SIGINT"
    })

# Formal Specification Registry for all PRUBETH CLI Commands
CLI_SPEC_REGISTRY: Dict[str, CommandSpec] = {
    "run": CommandSpec(
        name="run",
        description="Execute an autonomous software engineering goal.",
        usage="prubeth [goal...] [options]",
        options=[
            CommandOptionSpec("auto", ["-a", "--auto"], "bool", False, "Auto-approve tool actions."),
            CommandOptionSpec("model", ["-m", "--model"], "str", None, "Override active AI model."),
            CommandOptionSpec("profile", ["--profile"], "str", None, "Temporarily apply preset profile.", choices=["builder", "deep-reasoning", "local-airgap", "safe-audit"]),
            CommandOptionSpec("local", ["--local"], "bool", False, "Prefer local offline Ollama / LM Studio models."),
            CommandOptionSpec("output_format", ["--output-format"], "str", "text", "CLI output format.", choices=["text", "json", "stream-json"]),
        ]
    ),
    "settings": CommandSpec(
        name="settings",
        description="Display visual Performance Builder & Master Settings HUD.",
        usage="prubeth settings [inspect <key> | tune]",
        subcommands=["inspect", "tune", "builder", "perf"]
    ),
    "config": CommandSpec(
        name="config",
        description="Inspect or manipulate configuration entries.",
        usage="prubeth config [list | get <key> | set <key> <value>]",
        subcommands=["list", "get", "set"]
    ),
    "swarm": CommandSpec(
        name="swarm",
        description="Orchestrate and inspect Multi-Agent Swarm subagents.",
        usage="prubeth swarm [list | roles | spawn <role> <goal>]",
        subcommands=["list", "roles", "spawn", "status"]
    ),
    "worktrees": CommandSpec(
        name="worktrees",
        description="Inspect and manage isolated pure-Python shadow worktrees.",
        usage="prubeth worktrees [list | diff <id> | clean]",
        subcommands=["list", "diff", "clean"]
    ),
    "memory": CommandSpec(
        name="memory",
        description="Review continuous organizational intelligence and anti-patterns.",
        usage="prubeth memory [decisions | anti-patterns | clear]",
        subcommands=["decisions", "anti-patterns", "clear"]
    ),
    "mcp": CommandSpec(
        name="mcp",
        description="Model Context Protocol (MCP) server management.",
        usage="prubeth mcp [list | tools <name> | add <name> <cmd...> | call <server> <tool> <json>]",
        subcommands=["list", "tools", "add", "call"]
    ),
    "consensus": CommandSpec(
        name="consensus",
        description="Display multi-agent consensus and pre-flight AST compiler gates.",
        usage="prubeth consensus"
    ),
    "rollback": CommandSpec(
        name="rollback",
        description="Revert workspace state instantaneously to the last snapshot.",
        usage="prubeth rollback"
    ),
    "diff": CommandSpec(
        name="diff",
        description="Display working tree unified diff against initial snapshot.",
        usage="prubeth diff"
    ),
    "benchmark": CommandSpec(
        name="benchmark",
        description="Run evaluation benchmarks against autonomous tasks.",
        usage="prubeth benchmark [run | report]",
        subcommands=["run", "report"]
    ),
}

def validate_cli_command_spec(cmd_name: str) -> bool:
    """Verifies that a command conforms to the formal SDD registry."""
    return cmd_name in CLI_SPEC_REGISTRY
