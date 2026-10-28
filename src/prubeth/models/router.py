"""PRUBETH Model Auto-Router — Smart Task-Complexity-Based Model Selection.

Analyses incoming prompt text using heuristic signals (token length, keyword
vocabulary, code complexity markers, and conversational tone) to recommend an
appropriate model tier without user intervention.

The router operates in three tiers:
  - ``fast``     — High-velocity, cost-efficient models (Flash / Haiku / gpt-4o-mini)
  - ``balanced`` — Default general-purpose models (Flash-Pro / Sonnet / gpt-4o)
  - ``deep``     — Frontier reasoning models (Pro / Sonnet-3.7 / o3-mini / DeepSeek-R1)

The router never overrides an explicit ``/model`` selection — it only suggests.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

_FAST_MODELS: dict[str, str] = {
    "google":      "gemini-3.8-flash",
    "anthropic":   "claude-3-5-haiku-20241022",
    "openai":      "gpt-4o-mini",
    "openrouter":  "gpt-4o-mini",
    "deepseek":    "deepseek-v3",
    "groq":        "gemini-3.8-flash",
    "ollama":      "ollama",
    "lm_studio":   "lm_studio",
}

_BALANCED_MODELS: dict[str, str] = {
    "google":      "gemini-2.5-flash",
    "anthropic":   "claude-3-5-sonnet-20241022",
    "openai":      "gpt-4o",
    "openrouter":  "gpt-4o",
    "deepseek":    "deepseek-v3",
    "groq":        "gemini-2.5-flash",
    "ollama":      "ollama",
    "lm_studio":   "lm_studio",
}

_DEEP_MODELS: dict[str, str] = {
    "google":      "gemini-2.5-pro",
    "anthropic":   "claude-3-7-sonnet-20250219",
    "openai":      "o3-mini",
    "openrouter":  "o3-mini",
    "deepseek":    "deepseek-r1",
    "groq":        "gemini-2.5-pro",
    "ollama":      "ollama",
    "lm_studio":   "lm_studio",
}

# ---------------------------------------------------------------------------
# Keyword signal sets
# ---------------------------------------------------------------------------

_DEEP_KEYWORDS: frozenset[str] = frozenset({
    "architect", "architecture", "refactor", "redesign", "migrate", "migration",
    "analyse", "analyze", "design", "implement", "integration", "security",
    "audit", "research", "compare", "optimise", "optimize", "performance",
    "benchmark", "system", "pipeline", "orchestrat", "algorithm", "complex",
    "deep", "advanced", "critical", "production", "enterprise", "scalab",
    "concurren", "thread", "async", "multi-agent", "agent", "framework",
    "vulnerability", "cve", "exploit", "reverse", "decompil",
})

_FAST_KEYWORDS: frozenset[str] = frozenset({
    "hello", "hi", "hey", "what is", "what's", "explain", "summarise",
    "summarize", "translate", "spell", "grammar", "fix typo", "format",
    "list", "simple", "quick", "short", "brief", "one-liner", "rename",
    "tell me", "how do i", "what does", "definition", "meaning",
})

# Length thresholds (word count)
_FAST_WORD_LIMIT    = 20
_DEEP_WORD_MINIMUM  = 80
_DEEP_LINE_MINIMUM  = 8   # multiline code pastes → deep


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

class RoutingDecision(NamedTuple):
    """Result of an auto-routing analysis."""
    tier: str            # ``'fast'`` | ``'balanced'`` | ``'deep'``
    suggested_model: str # Fully qualified model name
    reason: str          # Human-readable rationale


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class ModelAutoRouter:
    """Analyses prompt complexity and suggests the optimal model tier.

    Args:
        provider:       The active provider name (e.g. ``'openrouter'``).
        default_model:  The currently active model — returned unchanged for
                        ``balanced`` tier so the user's choice is honoured.
        enabled:        Whether auto-routing is active; if ``False``,
                        ``route()`` always returns the current model as-is.
    """

    def __init__(
        self,
        provider: str = "openrouter",
        default_model: str = "",
        enabled: bool = False,
    ) -> None:
        self.provider      = provider.lower()
        self.default_model = default_model
        self.enabled       = enabled

    # ------------------------------------------------------------------
    # Internal scoring
    # ------------------------------------------------------------------

    def _score(self, text: str) -> tuple[str, str]:
        """Return ``(tier, reason)`` for *text*."""
        words     = text.split()
        wc        = len(words)
        line_count = text.count("\n")
        lower     = text.lower()

        # 1. Multiline code paste → deep
        if line_count >= _DEEP_LINE_MINIMUM:
            return "deep", f"Multi-line input detected ({line_count} lines) — applying deep reasoning."

        # 2. Explicit deep keyword
        for kw in _DEEP_KEYWORDS:
            if kw in lower:
                return "deep", f"Complexity keyword '{kw}' detected — routing to frontier reasoning model."

        # 3. Long prompt → deep
        if wc >= _DEEP_WORD_MINIMUM:
            return "deep", f"Long prompt ({wc} words) — routing to frontier reasoning model."

        # 4. Very short / conversational → fast
        if wc <= _FAST_WORD_LIMIT:
            for kw in _FAST_KEYWORDS:
                if kw in lower:
                    return "fast", f"Conversational / lookup query — routing to fast model."
            if wc <= 10:
                return "fast", f"Short prompt ({wc} words) — routing to fast model for low latency."

        return "balanced", "General-purpose query — using balanced model."

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, prompt_text: str) -> RoutingDecision:
        """Return a ``RoutingDecision`` for *prompt_text*.

        When ``enabled`` is ``False``, returns the current default model with
        tier ``'balanced'`` and a disabled message.

        Args:
            prompt_text: The raw user prompt string.

        Returns:
            A :class:`RoutingDecision` named-tuple.
        """
        if not self.enabled:
            return RoutingDecision(
                tier="balanced",
                suggested_model=self.default_model,
                reason="Auto-routing disabled — using configured model.",
            )

        tier, reason = self._score(prompt_text)

        prov = self.provider
        if tier == "fast":
            model = _FAST_MODELS.get(prov, self.default_model) or self.default_model
        elif tier == "deep":
            model = _DEEP_MODELS.get(prov, self.default_model) or self.default_model
        else:
            model = _BALANCED_MODELS.get(prov, self.default_model) or self.default_model

        # Never suggest an empty string
        if not model:
            model = self.default_model

        return RoutingDecision(tier=tier, suggested_model=model, reason=reason)

    def toggle(self) -> bool:
        """Toggle auto-routing on or off and return the new state."""
        self.enabled = not self.enabled
        return self.enabled
