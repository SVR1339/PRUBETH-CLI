"""PRUBETH Multi-Model Consensus & LLM Arena Matrix Tests.

Validates multi-model voting, Jaccard/SequenceMatcher consensus algorithms,
anomaly isolation, Elo rating updates, and leaderboard rankings.
"""

from __future__ import annotations

import math
import pytest
from unittest.mock import MagicMock, patch

from prubeth.models.consensus import MultiModelConsensus, ModelVote, ConsensusResult
from prubeth.models.arena import LLMArena, ArenaMatch, ModelLeaderboardEntry


# =========================================================================
# 1. Multi-Model Consensus Tests
# =========================================================================

@pytest.fixture
def consensus_engine():
    return MultiModelConsensus()


def test_consensus_single_vote(consensus_engine):
    votes = [ModelVote(model_name="gemini-2.5-pro", proposal_text="def add(a, b): return a + b")]
    res = consensus_engine.evaluate_proposals(votes)
    assert res.winning_proposal == "def add(a, b): return a + b"
    assert res.consensus_score == 1.0
    assert res.agreement_ratio == 1.0


def test_consensus_unanimous_agreement(consensus_engine):
    code = "def solve(): return 42"
    votes = [
        ModelVote(model_name="claude-3.7-sonnet", proposal_text=code),
        ModelVote(model_name="gemini-2.5-pro", proposal_text=code),
        ModelVote(model_name="deepseek-r1", proposal_text=code),
    ]
    res = consensus_engine.evaluate_proposals(votes)
    assert res.winning_proposal == code
    assert res.consensus_score == 1.0
    assert res.agreement_ratio == 1.0
    assert len(res.divergence_notes) == 0


def test_consensus_majority_2_to_1(consensus_engine):
    majority_code = "def get_user(id: str) -> dict:\n    return db.query(id)\n"
    minority_code = "def get_user_legacy(id):\n    # Completely different implementation\n    return None\n"
    votes = [
        ModelVote(model_name="model_a", proposal_text=majority_code),
        ModelVote(model_name="model_b", proposal_text=majority_code),
        ModelVote(model_name="model_c", proposal_text=minority_code),
    ]
    res = consensus_engine.evaluate_proposals(votes, similarity_threshold=0.7)
    assert res.winning_proposal == majority_code
    assert res.agreement_ratio == 2 / 3
    assert any("model_c" in d for d in res.divergence_notes)


def test_consensus_empty_votes_safe_return(consensus_engine):
    res = consensus_engine.evaluate_proposals([])
    assert res.winning_proposal == ""
    assert res.consensus_score == 0.0


# =========================================================================
# 2. LLM Arena Elo Engine Tests
# =========================================================================

@pytest.fixture
def arena():
    return LLMArena(default_rating=1500.0, k_factor=32.0)


def test_arena_initial_ratings(arena):
    assert arena.get_rating("gemini-2.5-flash") == 1500.0
    assert arena.get_rating("claude-3.7-sonnet") == 1500.0


def test_arena_expected_score_symmetry(arena):
    # Equal ratings -> 50% probability
    exp = arena.calculate_expected_score(1500.0, 1500.0)
    assert exp == pytest.approx(0.5, abs=1e-4)

    # 400 point advantage -> ~91% expected score
    exp_high = arena.calculate_expected_score(1900.0, 1500.0)
    assert exp_high == pytest.approx(0.9091, abs=1e-3)

    exp_low = arena.calculate_expected_score(1500.0, 1900.0)
    assert exp_low == pytest.approx(0.0909, abs=1e-3)
    assert exp_high + exp_low == pytest.approx(1.0, abs=1e-4)


def test_arena_win_updates_ratings_conservatively(arena):
    match = arena.record_match("gemini-flash", "llama-3.1", winner="model_a")
    # Gemini gained 16 Elo, LLaMA lost 16 Elo
    assert arena.get_rating("gemini-flash") == 1516.0
    assert arena.get_rating("llama-3.1") == 1484.0
    assert match.winner == "model_a"


def test_arena_tie_preserves_equal_ratings(arena):
    arena.record_match("model_x", "model_y", winner="tie")
    assert arena.get_rating("model_x") == 1500.0
    assert arena.get_rating("model_y") == 1500.0


def test_arena_leaderboard_sorting(arena):
    arena.record_match("model_champion", "model_underdog", winner="model_a")
    arena.record_match("model_champion", "model_underdog", winner="model_a")

    lb = arena.get_leaderboard()
    assert len(lb) == 2
    assert lb[0].model_name == "model_champion"
    assert lb[0].rating > lb[1].rating
    assert lb[0].wins == 2
    assert lb[0].win_rate == 100.0
    assert lb[1].losses == 2
    assert lb[1].win_rate == 0.0


@pytest.mark.parametrize("sim_step", [0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
def test_consensus_similarity_calibration(consensus_engine, sim_step):
    base_text = "def calculate_hash(data: bytes) -> str:\n    return sha256(data)\n"
    # Create slightly modified text
    mutated = base_text + ("# extra commentary\n" * int(sim_step * 5))
    sim = consensus_engine.calculate_similarity(base_text, mutated)
    assert 0.0 < sim <= 1.0
