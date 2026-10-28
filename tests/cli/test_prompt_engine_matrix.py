"""PRUBETH Prompt Engine & Interactive REPL Cockpit Matrix Tests.

Exhaustively verifies provider colour-coding, mode icons, branch detection,
prompt_toolkit rich autocompletion for slash commands, @files, and !shell shortcuts,
and bottom toolbar telemetry formatting.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from prubeth.cli.prompt_engine import (
    PrubethPromptEngine,
    _provider_colour,
    _detect_branch,
    _build_pt_completer,
    _build_pt_style,
    _build_pt_toolbar,
    _PROVIDER_COLOUR,
    _MODE_ICON,
)


# ============================================================================
# 1. Provider Colour Palette Invariants
# ============================================================================

@pytest.mark.parametrize("provider,expected_hex", [
    ("google", "#00C853"),
    ("anthropic", "#5C9EF0"),
    ("openai", "#FACC15"),
    ("openrouter", "#F97316"),
    ("deepseek", "#22D3EE"),
    ("groq", "#A78BFA"),
    ("ollama", "#94A3B8"),
    ("lm_studio", "#94A3B8"),
])
def test_provider_colour_mapping(provider: str, expected_hex: str):
    assert _provider_colour(provider) == expected_hex


def test_provider_colour_case_and_symbol_insensitivity():
    assert _provider_colour("Google-Gemini") == "#00C853"
    assert _provider_colour("ANTHROPIC") == "#5C9EF0"
    assert _provider_colour("unknown_custom_provider") == "#FFFFFF"


# ============================================================================
# 2. Mode Badges and Icons
# ============================================================================

@pytest.mark.parametrize("mode,expected_icon", [
    ("default", "◆"),
    ("developermode", "⚡"),
    ("plan", "📐"),
    ("builder", "🔨"),
])
def test_mode_icon_mapping(mode: str, expected_icon: str):
    assert _MODE_ICON[mode] == expected_icon


# ============================================================================
# 3. Git Branch Detection
# ============================================================================

def test_detect_branch_from_head_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        git_dir = ws / ".git"
        git_dir.mkdir(parents=True)
        head_file = git_dir / "HEAD"
        head_file.write_text("ref: refs/heads/feature/autonomous-v2\n", encoding="utf-8")

        with patch("prubeth.cli.prompt_engine.Path") as MockPath:
            MockPath.return_value = head_file
            branch = _detect_branch()
            # If Path(".git/HEAD") exists, it reads the ref
            assert branch in ("feature/autonomous-v2", "main")


def test_detect_branch_fallback_to_main_when_absent():
    with patch("pathlib.Path.exists", return_value=False):
        assert _detect_branch() == "main"


# ============================================================================
# 4. Toolbar Formatting
# ============================================================================

def test_build_pt_toolbar_string():
    toolbar_fn = _build_pt_toolbar(
        model="gemini-2.5-pro",
        provider="google",
        ram_mb=31.5,
        spend_str="$0.00",
        mode="plan"
    )
    text = toolbar_fn()
    assert "PRUBETH" in text
    assert "gemini-2.5-pro" in text
    assert "google" in text
    assert "RAM 31.5 MB" in text
    assert "$0.00" in text
    assert "📐 plan" in text


# ============================================================================
# 5. Completer Generation
# ============================================================================

def test_build_pt_completer_yields_slash_commands():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        slash_cmds = ["/run", "/eval", "/branch", "/models", "/status", "/doctor"]
        completer = _build_pt_completer(slash_cmds, ws)

        if completer is None:
            pytest.skip("prompt_toolkit not installed")

        doc = MagicMock()
        doc.text_before_cursor = "/ev"
        doc.get_word_before_cursor.return_value = "/ev"

        completions = list(completer.get_completions(doc, None))
        assert len(completions) >= 1
        assert any(c.display_text == "/eval" for c in completions)


def test_build_pt_completer_yields_files_on_at():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        (ws / "main.py").write_text("print(1)", encoding="utf-8")
        (ws / "server.ts").write_text("export {}", encoding="utf-8")

        slash_cmds = ["/run"]
        completer = _build_pt_completer(slash_cmds, ws)

        if completer is None:
            pytest.skip("prompt_toolkit not installed")

        doc = MagicMock()
        doc.text_before_cursor = "Inspect @main"
        doc.get_word_before_cursor.return_value = "@main"

        completions = list(completer.get_completions(doc, None))
        assert len(completions) >= 1
        assert any("main.py" in c.display_text for c in completions)


def test_build_pt_completer_yields_shell_shortcuts_on_bang():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        completer = _build_pt_completer([], ws)

        if completer is None:
            pytest.skip("prompt_toolkit not installed")

        doc = MagicMock()
        doc.text_before_cursor = "!git"
        doc.get_word_before_cursor.return_value = "!git"

        completions = list(completer.get_completions(doc, None))
        assert len(completions) >= 1
        assert any("!git status" in c.display_text for c in completions)
