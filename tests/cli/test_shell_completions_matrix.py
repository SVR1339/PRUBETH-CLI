"""PRUBETH Shell Tab Completion Matrix Tests.

Exhaustively verifies tab completion generators for PowerShell, Bash, and Zsh,
profile discovery, idempotent script injection, and cross-platform installation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from prubeth.cli.completions import (
    generate_powershell_completion,
    generate_bash_completion,
    generate_zsh_completion,
    install_shell_completion,
)


CORE_COMMANDS = [
    "run", "settings", "status", "tune", "models", "setup",
    "doctor", "version", "help", "completion", "eval", "swarm"
]


# ============================================================================
# 1. PowerShell Script Generation Invariants
# ============================================================================

def test_powershell_completion_structure():
    script = generate_powershell_completion()
    assert "Register-ArgumentCompleter" in script
    assert "-CommandName prubeth" in script
    assert "CompletionResult" in script
    for cmd in ["run", "settings", "status", "doctor", "profile", "toggle"]:
        assert f"'{cmd}'" in script


def test_powershell_completion_profiles_and_settings():
    script = generate_powershell_completion()
    assert "'builder'" in script
    assert "'deep-reasoning'" in script
    assert "'local-airgap'" in script
    assert "'default_model'" in script
    assert "'default_provider'" in script


# ============================================================================
# 2. Bash Script Generation Invariants
# ============================================================================

def test_bash_completion_structure():
    script = generate_bash_completion()
    assert "_prubeth_completions()" in script
    assert "COMPREPLY=" in script
    assert "compgen -W" in script
    assert "complete -F _prubeth_completions prubeth" in script
    for cmd in ["run", "settings", "status", "doctor"]:
        assert cmd in script


# ============================================================================
# 3. Zsh Script Generation Invariants
# ============================================================================

def test_zsh_completion_structure():
    script = generate_zsh_completion()
    assert "#compdef prubeth" in script
    assert "_describe 'command' commands" in script
    assert "'run:Execute autonomous coding goal'" in script
    assert "'doctor:Run system qualification diagnostic'" in script


# ============================================================================
# 4. Installation & Idempotency Testing
# ============================================================================

@pytest.mark.parametrize("shell_name", ["powershell", "bash", "zsh"])
def test_install_completion_creates_profile_if_missing(shell_name: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir).resolve()
        with patch("pathlib.Path.home", return_value=home):
            ok, msg = install_shell_completion(shell_name)
            assert ok is True
            assert "Successfully installed" in msg

            # Re-running must be completely idempotent
            ok_again, msg_again = install_shell_completion(shell_name)
            assert ok_again is True
            assert "already installed" in msg_again


def test_install_completion_unsupported_shell():
    ok, msg = install_shell_completion("unknown_shell_fish_xyz")
    assert ok is False
    assert "Unsupported shell" in msg
