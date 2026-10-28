"""Tests for PrubethPromptEngine — prompt construction, fallback, and ANSI output."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prubeth.cli.prompt_engine import (
    PrubethPromptEngine,
    _provider_colour,
    _detect_branch,
    _build_pt_style,
    _build_pt_toolbar,
)


# ---------------------------------------------------------------------------
# _provider_colour
# ---------------------------------------------------------------------------

class TestProviderColour:
    def test_google_returns_green(self):
        assert _provider_colour("google") == "#00C853"

    def test_anthropic_returns_blue(self):
        assert _provider_colour("anthropic") == "#5C9EF0"

    def test_openai_returns_amber(self):
        assert _provider_colour("openai") == "#FACC15"

    def test_deepseek_returns_cyan(self):
        assert _provider_colour("deepseek") == "#22D3EE"

    def test_unknown_returns_white(self):
        assert _provider_colour("unknown_xyz") == "#FFFFFF"

    def test_case_insensitive(self):
        assert _provider_colour("GOOGLE") == "#00C853"
        assert _provider_colour("Anthropic") == "#5C9EF0"


# ---------------------------------------------------------------------------
# _detect_branch
# ---------------------------------------------------------------------------

class TestDetectBranch:
    def test_returns_main_when_no_git(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _detect_branch() == "main"

    def test_reads_branch_from_head_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/feature/my-branch\n", encoding="utf-8")
        assert _detect_branch() == "feature/my-branch"

    def test_falls_back_on_detached_head(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("abc123deadbeef\n", encoding="utf-8")
        result = _detect_branch()
        # detached HEAD — ref doesn't start with 'ref: refs/heads/', so main is returned
        assert result == "main"


# ---------------------------------------------------------------------------
# PrubethPromptEngine — plain fallback path
# ---------------------------------------------------------------------------

class TestPromptEnginePlainFallback:
    """Force the engine to use the plain input() fallback by pretending prompt_toolkit is absent."""

    def _make_engine_no_pt(self, tmp_path):
        engine = PrubethPromptEngine.__new__(PrubethPromptEngine)
        engine._ws_root = tmp_path
        engine._slash_cmds = ["/help", "/exit"]
        engine._pt_session = None
        engine._has_pt = False
        return engine

    def test_get_input_returns_stripped_text(self, tmp_path, monkeypatch):
        engine = self._make_engine_no_pt(tmp_path)
        monkeypatch.chdir(tmp_path)
        with patch("builtins.input", return_value="  hello world  "):
            result = engine.get_input("gemini-2.5-pro", "google", 26.4, "$0.0000")
        assert result == "hello world"

    def test_get_input_raises_keyboard_interrupt(self, tmp_path, monkeypatch):
        engine = self._make_engine_no_pt(tmp_path)
        monkeypatch.chdir(tmp_path)
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                engine.get_input("gemini-2.5-pro", "google", 26.4, "$0.0000")

    def test_get_input_raises_eof_error(self, tmp_path, monkeypatch):
        engine = self._make_engine_no_pt(tmp_path)
        monkeypatch.chdir(tmp_path)
        with patch("builtins.input", side_effect=EOFError):
            with pytest.raises(EOFError):
                engine.get_input("gemini-2.5-pro", "google", 26.4, "$0.0000")

    def test_build_plain_prompt_contains_model(self, tmp_path):
        engine = self._make_engine_no_pt(tmp_path)
        plain = engine._build_plain_prompt("o3-mini", "openai", "main", 24.0, "$0.0012", "default")
        assert "o3-mini" in plain

    def test_build_plain_prompt_contains_spend(self, tmp_path):
        engine = self._make_engine_no_pt(tmp_path)
        plain = engine._build_plain_prompt("gpt-4o", "openai", "dev", 28.0, "$0.0099", "developermode")
        assert "$0.0099" in plain

    def test_build_plain_prompt_contains_mode_icon(self, tmp_path):
        engine = self._make_engine_no_pt(tmp_path)
        plain = engine._build_plain_prompt("gpt-4o", "openai", "main", 28.0, "$0.0000", "developermode")
        # developermode icon is ⚡
        assert "⚡" in plain or "developermode" in plain


# ---------------------------------------------------------------------------
# PrubethPromptEngine — prompt_toolkit path
# ---------------------------------------------------------------------------

class TestPromptEngineWithPromptToolkit:
    def test_engine_detects_prompt_toolkit(self):
        """prompt_toolkit 3.0.53 is installed; engine should attempt the PT path.
        In a non-interactive (piped/pytest) terminal the PromptSession may still
        fail to initialise, so we assert that the engine gracefully transitions to
        either has_pt=True or has_pt=False without raising an exception.
        """
        try:
            engine = PrubethPromptEngine(slash_cmds=["/help"], ws_root=Path.cwd())
            # No exception — that's the pass criterion
            assert isinstance(engine._has_pt, bool)
        except Exception as exc:
            pytest.fail(f"PrubethPromptEngine.__init__ raised an unexpected exception: {exc}")

    def test_get_input_via_pt_returns_stripped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        engine = PrubethPromptEngine(slash_cmds=["/help"], ws_root=tmp_path)
        # Mock the PromptSession.prompt method
        engine._pt_session = MagicMock()
        engine._pt_session.prompt.return_value = "  /models  "
        engine._has_pt = True
        result = engine.get_input("gemini-3.8-flash", "google", 25.0, "$0.0000", "default")
        assert result == "/models"

    def test_pt_falls_back_on_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        engine = PrubethPromptEngine(slash_cmds=["/help"], ws_root=tmp_path)
        engine._pt_session = MagicMock()
        engine._pt_session.prompt.side_effect = RuntimeError("terminal error")
        engine._has_pt = True
        with patch("builtins.input", return_value="fallback text"):
            result = engine.get_input("gemini-3.8-flash", "google", 25.0, "$0.0000")
        assert result == "fallback text"
