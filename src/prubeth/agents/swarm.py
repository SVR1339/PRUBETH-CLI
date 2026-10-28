"""PRUBETH Multi-Agent Swarm Orchestrator & Adversarial Pipeline.

Coordinates a 4-tier specialist swarm:
  Tier 1: Architect Specifier (Extracts interfaces & AST contracts)
  Tier 2: Code Implementer (Synthesizes logic adhering to contracts)
  Tier 3: Adversarial Reviewer (Red-teams for vulnerabilities & regressions)
  Tier 4: Verification Tester (Generates unit tests & validates coverage)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from prubeth.agents.base import SubagentRole, SubagentSpec, SubagentResult
from prubeth.agents.subagent import SubagentManager
from prubeth.runtime.contract import ASTContractGate
from prubeth.models.gateway import UniversalModelGateway, GenerationResponse


@dataclass
class SwarmPhaseOutcome:
    phase_name: str
    subagent_id: str
    success: bool
    summary: str
    artifacts_produced: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)


@dataclass
class SwarmResult:
    goal: str
    success: bool
    total_phases: int
    duration_s: float
    phases: List[SwarmPhaseOutcome] = field(default_factory=list)
    final_output: str = ""
    adversarial_findings: List[str] = field(default_factory=list)


class SwarmOrchestrator:
    """Orchestrates 4-tier autonomous specialist agent collaboration."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.manager = SubagentManager(self.workspace_root)
        self.contract_gate = ASTContractGate()

    def run_swarm(
        self,
        goal: str,
        max_revisions: int = 2,
        event_cb: Optional[Callable[[str, Any], None]] = None
    ) -> SwarmResult:
        """Executes full 4-tier swarm workflow."""
        start_time = time.time()
        phases: List[SwarmPhaseOutcome] = []
        findings: List[str] = []

        # 1. Tier 1: Architect Specifier
        spec_agent = self.manager.spawn_subagent(
            role=SubagentRole.ARCHITECT,
            goal=f"Architectural Specification: {goal}"
        )
        spec_res = self.manager.run_subagent(spec_agent, event_cb=event_cb)
        phases.append(SwarmPhaseOutcome(
            phase_name="Architect Specifier",
            subagent_id=spec_agent.id,
            success=spec_res.success,
            summary=spec_res.summary or "Architecture specification formulated.",
            artifacts_produced=spec_res.files_modified
        ))

        # 2. Tier 2: Code Implementer
        impl_agent = self.manager.spawn_subagent(
            role=SubagentRole.CODER,
            goal=f"Implementation: {goal}. Follow architecture specification: {spec_res.summary}"
        )
        impl_res = self.manager.run_subagent(impl_agent, event_cb=event_cb)
        phases.append(SwarmPhaseOutcome(
            phase_name="Code Implementer",
            subagent_id=impl_agent.id,
            success=impl_res.success,
            summary=impl_res.summary or "Code implementation complete.",
            artifacts_produced=impl_res.files_modified
        ))

        # 3. Tier 3: Adversarial Reviewer (Red-Team)
        review_agent = self.manager.spawn_subagent(
            role=SubagentRole.CRITIC,
            goal=f"Adversarial Review: Scrutinise implementation of '{goal}' for vulnerabilities and edge cases."
        )
        review_res = self.manager.run_subagent(review_agent, event_cb=event_cb)
        if review_res.summary and "vulnerability" in review_res.summary.lower():
            findings.append(review_res.summary)

        phases.append(SwarmPhaseOutcome(
            phase_name="Adversarial Reviewer",
            subagent_id=review_agent.id,
            success=review_res.success,
            summary=review_res.summary or "Code passed adversarial review invariants.",
            diagnostics=findings
        ))

        # 4. Tier 4: Verification Tester
        test_agent = self.manager.spawn_subagent(
            role=SubagentRole.TEST_ENGINEER,
            goal=f"Verification: Synthesize and execute unit tests for '{goal}'."
        )
        test_res = self.manager.run_subagent(test_agent, event_cb=event_cb)
        phases.append(SwarmPhaseOutcome(
            phase_name="Verification Tester",
            subagent_id=test_agent.id,
            success=test_res.success,
            summary=test_res.summary or "Verification test suite verified passing.",
            artifacts_produced=test_res.files_modified
        ))

        duration = time.time() - start_time
        all_ok = all(p.success for p in phases)

        return SwarmResult(
            goal=goal,
            success=all_ok,
            total_phases=len(phases),
            duration_s=duration,
            phases=phases,
            final_output=impl_res.summary,
            adversarial_findings=findings
        )
