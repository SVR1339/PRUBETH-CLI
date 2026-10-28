"""PRUBETH Multi-Model Consensus & Architectural Voting Engine.

Queries multiple diverse models (personal API keys, open-source endpoints,
or local engines), calculates structural consensus, filters anomalies, and synthesizes
high-confidence architectural decisions.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from prubeth.models.gateway import UniversalModelGateway, GenerationResponse


@dataclass
class ModelVote:
    model_name: str
    proposal_text: str
    confidence: float = 1.0
    latency_ms: float = 0.0


@dataclass
class ConsensusResult:
    winning_proposal: str
    consensus_score: float         # 0.0 to 1.0
    agreement_ratio: float         # e.g. 0.67 for 2 out of 3
    participating_models: List[str]
    divergence_notes: List[str] = field(default_factory=list)
    votes: List[ModelVote] = field(default_factory=list)


class MultiModelConsensus:
    """Orchestrates multi-model deliberation and voting."""

    def __init__(self, gateway: Optional[UniversalModelGateway] = None):
        self.gateway = gateway or UniversalModelGateway()

    def calculate_similarity(self, text_a: str, text_b: str) -> float:
        """Calculates normalized textual similarity ratio between two model outputs."""
        matcher = difflib.SequenceMatcher(None, text_a.strip(), text_b.strip())
        return matcher.ratio()

    def evaluate_proposals(self, votes: List[ModelVote], similarity_threshold: float = 0.65) -> ConsensusResult:
        """Determines the consensus choice among pre-generated model outputs."""
        if not votes:
            return ConsensusResult(
                winning_proposal="",
                consensus_score=0.0,
                agreement_ratio=0.0,
                participating_models=[]
            )

        if len(votes) == 1:
            return ConsensusResult(
                winning_proposal=votes[0].proposal_text,
                consensus_score=1.0,
                agreement_ratio=1.0,
                participating_models=[votes[0].model_name],
                votes=votes
            )

        n = len(votes)
        similarity_scores = [0.0] * n

        # Pairwise similarity accumulation
        for i in range(n):
            for j in range(i + 1, n):
                sim = self.calculate_similarity(votes[i].proposal_text, votes[j].proposal_text)
                similarity_scores[i] += sim
                similarity_scores[j] += sim

        # Identify winning candidate with highest pairwise alignment
        best_idx = similarity_scores.index(max(similarity_scores))
        winner_proposal = votes[best_idx].proposal_text

        # Calculate agreement ratio (models agreeing within threshold)
        agreed_count = 0
        divergences = []
        for i, vote in enumerate(votes):
            sim = self.calculate_similarity(winner_proposal, vote.proposal_text)
            if sim >= similarity_threshold:
                agreed_count += 1
            else:
                divergences.append(
                    f"Model '{vote.model_name}' diverged (similarity {sim:.2f} < {similarity_threshold})."
                )

        agreement_ratio = agreed_count / n
        avg_sim = (similarity_scores[best_idx] / max(1, n - 1)) if n > 1 else 1.0

        return ConsensusResult(
            winning_proposal=winner_proposal,
            consensus_score=avg_sim,
            agreement_ratio=agreement_ratio,
            participating_models=[v.model_name for v in votes],
            divergence_notes=divergences,
            votes=votes
        )

    def query_consensus(
        self,
        prompt: str,
        models: List[str],
        system_instruction: Optional[str] = None
    ) -> ConsensusResult:
        """Executes deliberation across specified models and computes consensus."""
        votes = []
        for m in models:
            try:
                resp = self.gateway.generate(
                    prompt,
                    system_instruction=system_instruction,
                    model_name=m,
                    model_tier="fast"
                )
                text = getattr(resp, "text", "") or ""
                votes.append(ModelVote(model_name=m, proposal_text=text))
            except Exception as e:
                # Log model failure without halting consensus
                votes.append(ModelVote(model_name=m, proposal_text=f"[Error: {e}]", confidence=0.0))

        return self.evaluate_proposals(votes)
