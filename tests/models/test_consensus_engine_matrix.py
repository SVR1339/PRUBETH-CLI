"""PRUBETH Multi-Model Consensus Engine Matrix Tests.

Exhaustively verifies ModelVote & ConsensusResult data contracts,
calculate_similarity pairwise scoring, evaluate_proposals edge cases,
consensus score, agreement ratio, divergence notes, and 0/1/N-vote behaviours.
"""

from __future__ import annotations

import pytest

from prubeth.models.consensus import (
    ModelVote,
    ConsensusResult,
    MultiModelConsensus,
)


# ============================================================================
# 1. ModelVote & ConsensusResult Data Contracts
# ============================================================================

def test_model_vote_defaults():
    vote = ModelVote(model_name="gemini-flash", proposal_text="Use dependency injection.")
    assert vote.confidence == 1.0
    assert vote.latency_ms == 0.0
    assert vote.model_name == "gemini-flash"


def test_model_vote_custom_confidence():
    vote = ModelVote(model_name="claude", proposal_text="Abstract factory pattern.", confidence=0.85)
    assert vote.confidence == 0.85


def test_consensus_result_defaults():
    result = ConsensusResult(
        winning_proposal="Use repositories.",
        consensus_score=0.9,
        agreement_ratio=0.75,
        participating_models=["gemini", "claude", "llama"],
    )
    assert result.divergence_notes == []
    assert result.votes == []


def test_consensus_result_populated():
    votes = [
        ModelVote("m1", "Use event sourcing."),
        ModelVote("m2", "Use event sourcing."),
    ]
    result = ConsensusResult(
        winning_proposal="Use event sourcing.",
        consensus_score=1.0,
        agreement_ratio=1.0,
        participating_models=["m1", "m2"],
        votes=votes,
    )
    assert len(result.votes) == 2
    assert result.consensus_score == 1.0


# ============================================================================
# 2. calculate_similarity — Pairwise Text Scoring
# ============================================================================

def test_similarity_identical_texts():
    engine = MultiModelConsensus()
    score = engine.calculate_similarity("Use dependency injection.", "Use dependency injection.")
    assert score == 1.0


def test_similarity_completely_different():
    engine = MultiModelConsensus()
    score = engine.calculate_similarity("aaa", "zzz")
    assert score < 0.5


def test_similarity_partial_overlap():
    engine = MultiModelConsensus()
    score = engine.calculate_similarity("Use event sourcing in the service layer.", "Use event sourcing pattern.")
    assert 0.5 < score < 1.0


def test_similarity_empty_strings():
    engine = MultiModelConsensus()
    score = engine.calculate_similarity("", "")
    assert score == 1.0


def test_similarity_one_empty():
    engine = MultiModelConsensus()
    score = engine.calculate_similarity("some content here", "")
    assert score == 0.0


# ============================================================================
# 3. evaluate_proposals — Zero Votes
# ============================================================================

def test_evaluate_empty_votes_returns_empty_result():
    engine = MultiModelConsensus()
    result = engine.evaluate_proposals([])
    assert result.winning_proposal == ""
    assert result.consensus_score == 0.0
    assert result.agreement_ratio == 0.0
    assert result.participating_models == []


# ============================================================================
# 4. evaluate_proposals — Single Vote
# ============================================================================

def test_evaluate_single_vote_wins_with_full_score():
    engine = MultiModelConsensus()
    votes = [ModelVote("gemini", "Use CQRS pattern.")]
    result = engine.evaluate_proposals(votes)
    assert result.winning_proposal == "Use CQRS pattern."
    assert result.consensus_score == 1.0
    assert result.agreement_ratio == 1.0
    assert "gemini" in result.participating_models


# ============================================================================
# 5. evaluate_proposals — Multiple Votes, Full Agreement
# ============================================================================

def test_evaluate_three_identical_votes_full_consensus():
    engine = MultiModelConsensus()
    text = "Implement Repository pattern for data access."
    votes = [
        ModelVote("gemini", text),
        ModelVote("claude", text),
        ModelVote("llama", text),
    ]
    result = engine.evaluate_proposals(votes)
    assert result.winning_proposal == text
    assert result.agreement_ratio > 0.5
    assert len(result.participating_models) == 3


def test_evaluate_two_identical_one_divergent():
    engine = MultiModelConsensus()
    majority = "Use service mesh for microservices."
    minority = "Use monolith — microservices are premature optimization."
    votes = [
        ModelVote("gemini", majority),
        ModelVote("claude", majority),
        ModelVote("llama", minority),
    ]
    result = engine.evaluate_proposals(votes)
    assert result.winning_proposal == majority
    assert len(result.divergence_notes) > 0


def test_evaluate_divergence_notes_reference_minority_model():
    engine = MultiModelConsensus()
    votes = [
        ModelVote("m1", "Pattern A is best."),
        ModelVote("m2", "Pattern A is best."),
        ModelVote("m3", "zzzzzzzzz pattern Z"),
    ]
    result = engine.evaluate_proposals(votes, similarity_threshold=0.7)
    assert any("m3" in note for note in result.divergence_notes)


# ============================================================================
# 6. evaluate_proposals — Votes List Included in Result
# ============================================================================

def test_evaluate_result_includes_all_votes():
    engine = MultiModelConsensus()
    votes = [
        ModelVote("m1", "Use facade pattern."),
        ModelVote("m2", "Use facade pattern."),
    ]
    result = engine.evaluate_proposals(votes)
    assert len(result.votes) == 2
    assert all(v.model_name in ["m1", "m2"] for v in result.votes)


def test_evaluate_five_models_all_agreeing():
    engine = MultiModelConsensus()
    text = "Hexagonal architecture with ports and adapters."
    votes = [ModelVote(f"model_{i}", text) for i in range(5)]
    result = engine.evaluate_proposals(votes)
    assert result.winning_proposal == text
    assert result.agreement_ratio == 1.0


def test_evaluate_participating_models_all_present():
    engine = MultiModelConsensus()
    votes = [
        ModelVote("a", "Plan A"),
        ModelVote("b", "Plan B"),
        ModelVote("c", "Plan A"),
    ]
    result = engine.evaluate_proposals(votes)
    for name in ["a", "b", "c"]:
        assert name in result.participating_models
