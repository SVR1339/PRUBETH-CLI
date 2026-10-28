"""PRUBETH CLI Specification & Dispatcher Permutations Matrix.

Exhaustively verifies CLI_SPEC_REGISTRY command specs, option flag schemas,
choices validation, exit codes, subcommand inventories, and dispatcher routing.
"""

from __future__ import annotations

import pytest

from prubeth.cli.spec import (
    CLI_SPEC_REGISTRY,
    CommandSpec,
    CommandOptionSpec,
    validate_cli_command_spec,
)

ALL_CLI_COMMANDS = list(CLI_SPEC_REGISTRY.keys())


# ============================================================================
# 1. CLI Command Specification Invariants Matrix
# ============================================================================

@pytest.mark.parametrize("cmd_name", ALL_CLI_COMMANDS)
def test_cli_command_spec_invariants(cmd_name: str):
    spec = CLI_SPEC_REGISTRY[cmd_name]
    assert spec.name == cmd_name
    assert spec.description and len(spec.description) > 5
    assert spec.usage and spec.usage.startswith("prubeth")
    assert 0 in spec.expected_exit_codes
    assert spec.expected_exit_codes[0] == "SUCCESS"
    assert 1 in spec.expected_exit_codes
    assert 2 in spec.expected_exit_codes


@pytest.mark.parametrize("cmd_name", ALL_CLI_COMMANDS)
def test_cli_command_options_integrity(cmd_name: str):
    spec = CLI_SPEC_REGISTRY[cmd_name]
    for opt in spec.options:
        assert isinstance(opt, CommandOptionSpec)
        assert opt.name and len(opt.name) > 0
        assert opt.flags and len(opt.flags) >= 1
        for f in opt.flags:
            assert f.startswith("-") or f.startswith("--")
        assert opt.type_name in {"bool", "str", "int", "float"}
        if opt.choices:
            assert isinstance(opt.choices, list)
            assert len(opt.choices) >= 2


# ============================================================================
# 2. Command Validation Function Matrix
# ============================================================================

@pytest.mark.parametrize("cmd_name", [
    "run", "settings", "config", "swarm", "worktrees",
    "memory", "mcp", "consensus", "rollback", "diff", "benchmark"
])
def test_validate_cli_command_spec_valid(cmd_name: str):
    assert validate_cli_command_spec(cmd_name) is True


@pytest.mark.parametrize("invalid_cmd", [
    "ghost_command", "deploy", "kubernetes_orchestrate",
    "telemetry_phone_home", "", "   ", "sudo", "eval"
])
def test_validate_cli_command_spec_invalid(invalid_cmd: str):
    assert validate_cli_command_spec(invalid_cmd) is False


# ============================================================================
# 3. Subcommands Inventory Matrix
# ============================================================================

@pytest.mark.parametrize("cmd_name,expected_subcommands", [
    ("settings", ["inspect", "tune", "builder", "perf"]),
    ("config", ["list", "get", "set"]),
    ("swarm", ["list", "roles", "spawn", "status"]),
    ("worktrees", ["list", "diff", "clean"]),
    ("memory", ["decisions", "anti-patterns", "clear"]),
    ("mcp", ["list", "tools", "add", "call"]),
    ("benchmark", ["run", "report"]),
])
def test_cli_command_subcommands_inventory(cmd_name: str, expected_subcommands: list[str]):
    spec = CLI_SPEC_REGISTRY[cmd_name]
    for sub in expected_subcommands:
        assert sub in spec.subcommands, f"Subcommand '{sub}' missing from command '{cmd_name}'"


# ============================================================================
# 4. Command Option Choices & Defaults Matrix
# ============================================================================

def test_run_command_options_detail():
    run_spec = CLI_SPEC_REGISTRY["run"]
    opt_map = {opt.name: opt for opt in run_spec.options}

    # --auto
    assert "auto" in opt_map
    assert "-a" in opt_map["auto"].flags
    assert "--auto" in opt_map["auto"].flags
    assert opt_map["auto"].type_name == "bool"
    assert opt_map["auto"].default is False

    # --profile
    assert "profile" in opt_map
    assert "--profile" in opt_map["profile"].flags
    assert "builder" in opt_map["profile"].choices
    assert "local-airgap" in opt_map["profile"].choices
    assert "deep-reasoning" in opt_map["profile"].choices
    assert "safe-audit" in opt_map["profile"].choices

    # --output-format
    assert "output_format" in opt_map
    assert "--output-format" in opt_map["output_format"].flags
    assert "text" in opt_map["output_format"].choices
    assert "stream-json" in opt_map["output_format"].choices
    assert opt_map["output_format"].default == "text"
