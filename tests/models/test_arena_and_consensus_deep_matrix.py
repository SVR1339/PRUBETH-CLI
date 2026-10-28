"""PRUBETH LLM Arena Elo Mathematics & Multi-Model Consensus Deep Matrix.

Exhaustively verifies Elo rating mathematics (expected score symmetry, K-factor
scaling, ratings convergence), leaderboard generation, and multi-model consensus
similarity metrics, divergence detection, and outlier rejection.
"""

from __future__ import annotations

import math
import pytest

from prubeth.models.arena import LLMArena, ArenaMatch, ModelLeaderboardEntry
from prubeth.models.consensus import MultiModelConsensus, ModelVote, ConsensusResult


# ============================================================================
# 1. Elo Mathematics & Symmetries
# ============================================================================

@pytest.mark.parametrize("rating_a,rating_b", [
    (1500.0, 1500.0),
    (1600.0, 1400.0),
    (1800.0, 1200.0),
    (2000.0, 1000.0),
    (1350.5, 1550.5),
])
def test_arena_expected_score_symmetry(rating_a: float, rating_b: float):
    """The sum of expected scores for two players must always equal exactly 1.0."""
    arena = LLMArena()
    e_a = arena.calculate_expected_score(rating_a, rating_b)
    e_b = arena.calculate_expected_score(rating_b, rating_a)
    assert pytest.approx(e_a + e_b, rel=1e-6) == 1.0


def test_arena_equal_ratings_yield_half_probability():
    arena = LLMArena()
    assert arena.calculate_expected_score(1500.0, 1500.0) == 0.5


def test_arena_higher_rated_player_has_higher_expected_score():
    arena = LLMArena()
    e_strong = arena.calculate_expected_score(1700.0, 1400.0)
    e_weak = arena.calculate_expected_score(1400.0, 1700.0)
    assert e_strong > 0.5
    assert e_weak < 0.5
    assert e_strong > e_weak


# ============================================================================
# 2. Match Recording & Convergence Over Rounds
# ============================================================================

def test_arena_match_winner_gains_rating_loser_loses_rating():
    arena = LLMArena(default_rating=1500.0, k_factor=32.0)
    match = arena.record_match(
        model_a="gemini-2.5-pro",
        model_b="claude-3-5-haiku",
        winner="model_a",
        task_prompt="Implement red-black tree"
    )
    assert match.rating_a_after > 1500.0
    assert match.rating_b_after < 1500.0
    assert arena.get_rating("gemini-2.5-pro") == match.rating_a_after
    assert arena.get_rating("claude-3-5-haiku") == match.rating_b_after


def test_arena_tie_moves_ratings_towards_equality():
    arena = LLMArena(default_rating=1500.0, k_factor=32.0)
    # Set model_a higher initially
    arena.ratings["strong-model"] = 1700.0
    arena.ratings["weak-model"] = 1300.0

    match = arena.record_match(
        model_a="strong-model",
        model_b="weak-model",
        winner="tie",
        task_prompt="Simple task"
    )
    # Under a tie, the weaker model gains rating and the stronger model loses rating
    assert match.rating_b_after > 1300.0
    assert match.rating_a_after < 1700.0


def test_arena_repeated_wins_converge_leaderboard():
    arena = LLMArena(default_rating=1500.0, k_factor=32.0)
    for _ in range(15):
        arena.record_match("top-model", "mid-model", winner="model_a", task_prompt="p")
        arena.record_match("mid-model", "low-model", winner="model_a", task_prompt="p")

    lb = arena.get_leaderboard()
    assert len(lb) == 3
    assert lb[0].model_name == "top-model"
    assert lb[1].model_name == "mid-model"
    assert lb[2].model_name == "low-model"
    assert lb[0].rating > lb[1].rating > lb[2].rating


# ============================================================================
# 3. Multi-Model Consensus Deliberation
# ============================================================================

def test_consensus_unanimous_identical_votes():
    engine = MultiModelConsensus()
    votes = [
        ModelVote("model-1", "def solve(): return 42"),
        ModelVote("model-2", "def solve(): return 42"),
        ModelVote("model-3", "def solve(): return 42"),
    ]
    res = engine.evaluate_proposals(votes)
    assert res.winning_proposal == "def solve(): return 42"
    assert res.consensus_score == 1.0
    assert res.agreement_ratio == 1.0
    assert len(res.participating_models) == 3


def test_consensus_majority_with_outlier_filtered():
    engine = MultiModelConsensus()
    majority_text = "def calculate_tax(amount): return amount * 0.2"
    votes = [
        ModelVote("gemini", majority_text),
        ModelVote("claude", majority_text),
        ModelVote("unrelated-model", "import os; os.system('format c:')"),  # Outlier anomaly
    ]
    res = engine.evaluate_proposals(votes, similarity_threshold=0.7)
    assert res.winning_proposal == majority_text
    assert pytest.approx(res.agreement_ratio, rel=1e-2) == (2.0 / 3.0)
    assert len(res.divergence_notes) >= 1
    assert "unrelated-model" in res.divergence_notes[0]


def test_consensus_empty_votes_returns_graceful_empty():
    engine = MultiModelConsensus()
    res = engine.evaluate_proposals([])
    assert res.winning_proposal == ""
    assert res.consensus_score == 0.0
    assert res.agreement_ratio == 0.0


def test_consensus_single_vote():
    engine = MultiModelConsensus()
    res = engine.evaluate_proposals([ModelVote("only-model", "solution text")])
    assert res.winning_proposal == "solution text"
    assert res.consensus_score == 1.0
    assert res.agreement_ratio == 1.0
