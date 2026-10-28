"""PRUBETH Local & Personal Key LLM Coding Arena Engine.

Tracks Elo skill ratings and head-to-head pairwise developer evaluations
for local models, open-source free endpoints, and personal developer keys.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class ArenaMatch:
    match_id: str
    model_a: str
    model_b: str
    winner: str        # "model_a", "model_b", or "tie"
    task_prompt: str
    rating_a_before: float
    rating_b_before: float
    rating_a_after: float
    rating_b_after: float
    timestamp: float = 0.0


@dataclass
class ModelLeaderboardEntry:
    model_name: str
    rating: float
    matches_played: int
    wins: int
    losses: int
    ties: int
    win_rate: float


class LLMArena:
    """Computes Elo ratings and manages blind pairwise model battle histories."""

    def __init__(self, default_rating: float = 1500.0, k_factor: float = 32.0):
        self.default_rating = default_rating
        self.k_factor = k_factor
        self.ratings: Dict[str, float] = {}
        self.match_history: List[ArenaMatch] = []
        self.stats: Dict[str, Dict[str, int]] = {}

    def get_rating(self, model_name: str) -> float:
        """Retrieves active Elo rating for a model, defaulting to 1500."""
        return self.ratings.get(model_name, self.default_rating)

    def calculate_expected_score(self, rating_a: float, rating_b: float) -> float:
        """Calculates expected score E_A = 1 / (1 + 10^((R_B - R_A) / 400))."""
        return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))

    def record_match(
        self,
        model_a: str,
        model_b: str,
        winner: str,  # "model_a", "model_b", "tie"
        task_prompt: str = "",
        match_id: str = ""
    ) -> ArenaMatch:
        """Updates Elo ratings based on battle outcome."""
        r_a = self.get_rating(model_a)
        r_b = self.get_rating(model_b)

        exp_a = self.calculate_expected_score(r_a, r_b)
        exp_b = self.calculate_expected_score(r_b, r_a)

        # Actual score: 1.0 = win, 0.5 = tie, 0.0 = loss
        if winner == "model_a":
            score_a, score_b = 1.0, 0.0
        elif winner == "model_b":
            score_a, score_b = 0.0, 1.0
        else:
            score_a, score_b = 0.5, 0.5

        # Elo update
        new_r_a = r_a + self.k_factor * (score_a - exp_a)
        new_r_b = r_b + self.k_factor * (score_b - exp_b)

        self.ratings[model_a] = round(new_r_a, 2)
        self.ratings[model_b] = round(new_r_b, 2)

        # Update statistics
        for m in (model_a, model_b):
            if m not in self.stats:
                self.stats[m] = {"matches": 0, "wins": 0, "losses": 0, "ties": 0}

        self.stats[model_a]["matches"] += 1
        self.stats[model_b]["matches"] += 1

        if winner == "model_a":
            self.stats[model_a]["wins"] += 1
            self.stats[model_b]["losses"] += 1
        elif winner == "model_b":
            self.stats[model_b]["wins"] += 1
            self.stats[model_a]["losses"] += 1
        else:
            self.stats[model_a]["ties"] += 1
            self.stats[model_b]["ties"] += 1

        match_record = ArenaMatch(
            match_id=match_id or f"match_{len(self.match_history)+1}",
            model_a=model_a,
            model_b=model_b,
            winner=winner,
            task_prompt=task_prompt,
            rating_a_before=r_a,
            rating_b_before=r_b,
            rating_a_after=self.ratings[model_a],
            rating_b_after=self.ratings[model_b]
        )
        self.match_history.append(match_record)
        return match_record

    def get_leaderboard(self) -> List[ModelLeaderboardEntry]:
        """Returns sorted leaderboard of evaluated models."""
        entries = []
        for model, r in self.ratings.items():
            s = self.stats.get(model, {"matches": 0, "wins": 0, "losses": 0, "ties": 0})
            total = s["matches"]
            win_rate = (s["wins"] / total * 100.0) if total else 0.0
            entries.append(ModelLeaderboardEntry(
                model_name=model,
                rating=r,
                matches_played=total,
                wins=s["wins"],
                losses=s["losses"],
                ties=s["ties"],
                win_rate=win_rate
            ))

        entries.sort(key=lambda x: x.rating, reverse=True)
        return entries
