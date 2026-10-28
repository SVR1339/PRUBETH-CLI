"""PRUBETH Prompt Engine — Frontier-Grade Interactive Prompt with prompt_toolkit.

Provides a polished Claude Code / Gemini CLI-style interactive prompt line that:
  - Displays active model, provider, git branch, RAM, session spend, and mode badge
  - Uses prompt_toolkit for rich autocomplete, syntax highlighting, and history
  - Falls back gracefully to stdlib ``input()`` when prompt_toolkit is absent
  - Colour-codes model badges by provider family
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Provider colour palette (ANSI 256 / prompt_toolkit style names)
# ---------------------------------------------------------------------------

_PROVIDER_COLOUR: dict[str, str] = {
    "google":      "#00C853",   # bright green   – Google / Gemini
    "gemini":      "#00C853",   # bright green   – Google / Gemini
    "anthropic":   "#5C9EF0",   # steel blue     – Anthropic / Claude
    "claude":      "#5C9EF0",   # steel blue     – Anthropic / Claude
    "openai":      "#FACC15",   # amber           – OpenAI / o3
    "openrouter":  "#F97316",   # orange          – OpenRouter
    "open_router": "#F97316",   # orange          – OpenRouter
    "deepseek":    "#22D3EE",   # cyan            – DeepSeek
    "groq":        "#A78BFA",   # purple          – Groq
    "ollama":      "#94A3B8",   # slate           – local Ollama
    "lm_studio":   "#94A3B8",   # slate           – local LM Studio
}

_MODE_COLOUR: dict[str, str] = {
    "default":      "#94A3B8",
    "developermode":"#F43F5E",
    "plan":         "#FACC15",
    "builder":      "#00C853",
}

_MODE_ICON: dict[str, str] = {
    "default":      "◆",
    "developermode":"⚡",
    "plan":         "📐",
    "builder":      "🔨",
}


def _provider_colour(provider: str) -> str:
    """Return the hex colour for *provider*, falling back to white."""
    key = provider.lower().replace("-", "_").replace(" ", "_")
    for k, v in _PROVIDER_COLOUR.items():
        if k in key:
            return v
    return "#FFFFFF"


def _detect_branch() -> str:
    """Return the current git branch name, or ``'main'`` if indeterminate."""
    try:
        head = Path(".git/HEAD")
        if head.exists():
            ref = head.read_text(encoding="utf-8").strip()
            if ref.startswith("ref: refs/heads/"):
                return ref.replace("ref: refs/heads/", "")
    except Exception:
        pass
    return "main"


# ---------------------------------------------------------------------------
# prompt_toolkit helpers — lazily imported so the fallback path is clean
# ---------------------------------------------------------------------------

def _build_pt_completer(slash_cmds: List[str], ws_root: Path):
    """Build a prompt_toolkit NestedCompleter for slash-commands, @files, and !shell."""
    try:
        from prompt_toolkit.completion import Completer, Completion
        from pathlib import Path as P

        class _PrubethCompleter(Completer):
            def get_completions(self, document, complete_event):  # type: ignore[override]
                text = document.text_before_cursor
                word = document.get_word_before_cursor(WORD=True)

                if text.lstrip().startswith("/"):
                    for cmd in slash_cmds:
                        if cmd.startswith(text.lstrip()):
                            yield Completion(cmd[len(text.lstrip()):], start_position=0, display=cmd)
                    return

                if word.startswith("@"):
                    prefix = word[1:].replace("file:", "")
                    try:
                        for p in ws_root.rglob("*"):
                            if any(ign in p.parts for ign in [".git", "dist", "build", "__pycache__", ".venv", "venv"]):
                                continue
                            rel = str(p.relative_to(ws_root)).replace("\\", "/")
                            if rel.lower().startswith(prefix.lower()):
                                yield Completion(rel[len(prefix):], start_position=0, display=f"@{rel}")
                    except Exception:
                        pass
                    return

                if word.startswith("!"):
                    sh = ["!git status", "!git diff", "!git log", "!pytest", "!python", "!ls", "!dir"]
                    for cmd in sh:
                        if cmd.startswith(word):
                            yield Completion(cmd[len(word):], start_position=0, display=cmd)

        return _PrubethCompleter()
    except ImportError:
        return None


def _build_pt_style(provider: str, mode: str):
    """Build a prompt_toolkit Style object encoding provider/mode colours."""
    try:
        from prompt_toolkit.styles import Style
        prov_col = _provider_colour(provider)
        mode_col = _MODE_COLOUR.get(mode, "#94A3B8")
        return Style.from_dict({
            "model":    f"bold {prov_col}",
            "sep":      "ansidarkgray",
            "branch":   "ansigreen bold",
            "ram":      "ansidarkgray",
            "spend":    "ansidarkgray",
            "mode":     f"bold {mode_col}",
            "arrow":    "bold #22D3EE",
            "prompt":   "",
        })
    except ImportError:
        return None


def _build_pt_toolbar(model: str, provider: str, ram_mb: float, spend_str: str, mode: str):
    """Return the bottom-toolbar callable for prompt_toolkit."""
    def _toolbar():
        mode_icon = _MODE_ICON.get(mode, "◆")
        return (
            f" PRUBETH  ·  {model}  ·  {provider}  ·  "
            f"RAM {ram_mb} MB  ·  {spend_str}  ·  {mode_icon} {mode}"
        )
    return _toolbar


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class PrubethPromptEngine:
    """Manages the interactive prompt for the PRUBETH REPL cockpit.

    On instantiation the engine checks whether ``prompt_toolkit`` is available
    and sets up persistent history and rich autocompletion.  If prompt_toolkit
    is absent it falls back silently to stdlib ``input()``.

    Args:
        slash_cmds: List of slash-command strings used for tab-completion.
        ws_root:    Workspace root ``Path`` for ``@file:`` expansion.
    """

    def __init__(self, slash_cmds: List[str], ws_root: Optional[Path] = None) -> None:
        self._ws_root = ws_root or Path.cwd().resolve()
        self._slash_cmds = slash_cmds
        self._pt_session = None
        self._has_pt = False
        self._setup_prompt_toolkit()

    # ------------------------------------------------------------------
    # Internal setup
    # ------------------------------------------------------------------

    def _setup_prompt_toolkit(self) -> None:
        """Attempt to initialise a prompt_toolkit ``PromptSession``."""
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import FileHistory

            h_dir = Path.home() / ".prubeth"
            h_dir.mkdir(parents=True, exist_ok=True)
            h_file = h_dir / "pt_history.txt"

            completer = _build_pt_completer(self._slash_cmds, self._ws_root)
            self._pt_session = PromptSession(
                history=FileHistory(str(h_file)),
                completer=completer,
                complete_while_typing=True,
                mouse_support=False,
                enable_history_search=True,
            )
            self._has_pt = True
        except ImportError:
            self._has_pt = False
        except Exception:
            self._has_pt = False

    # ------------------------------------------------------------------
    # Prompt construction helpers
    # ------------------------------------------------------------------

    def _build_pt_prompt_tokens(
        self,
        model: str,
        provider: str,
        branch: str,
        ram_mb: float,
        spend_str: str,
        mode: str,
    ):
        """Return a list of ``(style_class, text)`` tuples for prompt_toolkit."""
        mode_icon = _MODE_ICON.get(mode, "◆")
        return [
            ("class:sep",    "╭─ "),
            ("class:model",  model),
            ("class:sep",    " · "),
            ("class:branch", branch),
            ("class:sep",    " · "),
            ("class:ram",    f"{ram_mb} MB"),
            ("class:sep",    " · "),
            ("class:spend",  spend_str),
            ("class:sep",    " · "),
            ("class:mode",   f"{mode_icon} {mode}"),
            ("class:sep",    "\n╰─ "),
            ("class:arrow",  "❯ "),
        ]

    @staticmethod
    def _build_plain_prompt(
        model: str,
        provider: str,
        branch: str,
        ram_mb: float,
        spend_str: str,
        mode: str,
    ) -> str:
        """Return a plain ANSI-escaped prompt string for the ``input()`` fallback."""
        mode_icon = _MODE_ICON.get(mode, "◆")
        cyan    = "\x1b[1;36m"
        green   = "\x1b[1;32m"
        dim     = "\x1b[2m"
        reset   = "\x1b[0m"
        bold    = "\x1b[1m"
        return (
            f"\n{dim}prubeth {bold}[{cyan}{model}{reset}{dim} · "
            f"{green}{branch}{reset}{dim} · "
            f"{ram_mb} MB · {spend_str} · {mode_icon} {mode}]{reset}\n"
            f"{cyan}❯{reset} "
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_input(
        self,
        model: str,
        provider: str,
        ram_mb: float,
        spend_str: str,
        mode: str = "default",
    ) -> str:
        """Display the PRUBETH prompt and return the user's input string.

        Raises ``EOFError`` on Ctrl-D / end-of-file.

        Args:
            model:     Active model name (e.g. ``'gemini-2.5-pro'``).
            provider:  Active provider name (e.g. ``'google'``).
            ram_mb:    Current process RAM in megabytes.
            spend_str: Formatted session spend string (e.g. ``'$0.0042'``).
            mode:      Current execution mode string (e.g. ``'default'``).

        Returns:
            Stripped input string from the user.
        """
        branch = _detect_branch()

        if self._has_pt and self._pt_session is not None:
            try:
                style  = _build_pt_style(provider, mode)
                tokens = self._build_pt_prompt_tokens(model, provider, branch, ram_mb, spend_str, mode)
                toolbar = _build_pt_toolbar(model, provider, ram_mb, spend_str, mode)
                result = self._pt_session.prompt(
                    tokens,           # type: ignore[arg-type]
                    style=style,
                    bottom_toolbar=toolbar,
                    refresh_interval=0.5,
                )
                return result.strip()
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except EOFError:
                raise EOFError
            except Exception:
                # Degrade gracefully to plain input on any prompt_toolkit error
                pass

        # ---------- Fallback: plain ANSI input() ----------
        plain = self._build_plain_prompt(model, provider, branch, ram_mb, spend_str, mode)
        try:
            return input(plain).strip()
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except EOFError:
            raise EOFError
