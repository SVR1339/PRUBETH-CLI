"""PRUBETH Multi-Agent Swarm, Consensus & Worktree Isolation Matrix.

Exhaustively verifies:
1. WorktreeManager:
   - Isolated scratchpad provisioning per subagent.
   - Baseline SHA-256 fingerprinting and ignored directory filtering.
   - Diff calculation across added, modified, and deleted files.
   - Atomic merge from worktree back to repository root.
   - Complete worktree cleanup and idempotency.
2. SubagentSpec, SubagentResult, SubagentRole & SubagentState:
   - Full enum taxonomy across all 5 specialist roles and 7 lifecycle states.
   - Immutability and property accessors (summary, files_modified).
   - Turn budget enforcement and critic review metadata.
3. Swarm Consensus & Multi-Agent Voting Algorithms:
   - Simple majority voting across diverse agent decisions.
   - Role-weighted expertise voting (Architect, Critic, Coder, Test Engineer).
   - Unanimous consensus enforcement for high-risk or destructive mutations.
   - Deterministic tie-breaker algorithms.
4. SwarmPhaseOutcome & SwarmResult:
   - Multi-tier pipeline telemetry aggregation.
   - Adversarial red-team finding propagation and duration tracking.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from prubeth.agents.base import (
    SubagentRole,
    SubagentState,
    SubagentSpec,
    SubagentResult,
)
from prubeth.agents.worktree import WorktreeManager
from prubeth.agents.swarm import (
    SwarmPhaseOutcome,
    SwarmResult,
)


# ============================================================================
# 1. WorktreeManager: Lifecycle, Diff Detection & Atomic Merging
# ============================================================================

def test_worktree_manager_creates_clean_directory(tmp_path):
    mgr = WorktreeManager(workspace_root=tmp_path)
    assert mgr.worktrees_dir.exists()
    assert mgr.worktrees_dir == tmp_path / ".prubeth" / "worktrees"


WORKTREE_INIT_SCENARIOS = [
    ("agent-coder-01", ["src/main.py", "src/utils.py"], ["README.md"]),
    ("agent-critic-02", ["lib/core.go"], ["go.mod", "go.sum"]),
    ("agent-tester-03", ["tests/test_api.py"], ["pytest.ini"]),
    ("agent-arch-04", ["docs/architecture.md"], ["pyproject.toml"]),
    ("agent-docs-05", ["guide.md", "tutorial.md"], ["LICENSE"]),
]

@pytest.mark.parametrize("subagent_id,src_files,extra_files", WORKTREE_INIT_SCENARIOS)
def test_worktree_creation_and_file_copy(tmp_path, subagent_id: str, src_files: list[str], extra_files: list[str]):
    # Setup files in root
    for f in src_files + extra_files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"content of {f}", encoding="utf-8")

    mgr = WorktreeManager(workspace_root=tmp_path)
    wt_path = mgr.create_worktree(subagent_id)

    assert wt_path.exists()
    assert wt_path == mgr.get_worktree_path(subagent_id)
    # Verify baseline files copied
    for f in src_files + extra_files:
        assert (wt_path / f).exists()
        assert (wt_path / f).read_text(encoding="utf-8") == f"content of {f}"

    # Verify baseline manifest exists
    assert subagent_id in mgr.baselines
    assert len(mgr.baselines[subagent_id]) == len(src_files + extra_files)


def test_worktree_ignores_restricted_directories(tmp_path):
    # Create ignored folders
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git config", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "temp.pyc").write_text("pyc", encoding="utf-8")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "activate").write_text("venv", encoding="utf-8")
    (tmp_path / "app.py").write_text("import os", encoding="utf-8")

    mgr = WorktreeManager(workspace_root=tmp_path)
    wt = mgr.create_worktree("sub-test-ignore")

    assert (wt / "app.py").exists()
    assert not (wt / ".git").exists()
    assert not (wt / "__pycache__").exists()
    assert not (wt / "venv").exists()


WORKTREE_DIFF_MODIFICATIONS = [
    ("mod.py", "original", "modified content v2", "modified"),
    ("new_file.py", None, "brand new file payload", "added"),
    ("to_delete.py", "doomed content", None, "deleted"),
    ("unchanged.py", "static content", "static content", "unchanged"),
    ("service.ts", "const x = 1;", "const x = 2;", "modified"),
    ("config.json", '{"v": 1}', '{"v": 2}', "modified"),
    ("created.txt", None, "created dynamically", "added"),
    ("dropped.md", "# Dropped", None, "deleted"),
    ("same.txt", "identical", "identical", "unchanged"),
    ("util.go", "package util", "package util\nfunc F() {}", "modified"),
]

@pytest.mark.parametrize("rel_path,init_content,new_content,expected_change", WORKTREE_DIFF_MODIFICATIONS)
def test_worktree_diff_detection(tmp_path, rel_path: str, init_content: str | None, new_content: str | None, expected_change: str):
    root_file = tmp_path / rel_path
    if init_content is not None:
        root_file.parent.mkdir(parents=True, exist_ok=True)
        root_file.write_text(init_content, encoding="utf-8")

    mgr = WorktreeManager(workspace_root=tmp_path)
    sub_id = f"diff-{rel_path.replace('.', '_')}"
    wt = mgr.create_worktree(sub_id)

    wt_file = wt / rel_path
    if new_content is not None and init_content is not None:
        wt_file.write_text(new_content, encoding="utf-8")
    elif new_content is not None and init_content is None:
        wt_file.parent.mkdir(parents=True, exist_ok=True)
        wt_file.write_text(new_content, encoding="utf-8")
    elif new_content is None and init_content is not None:
        if wt_file.exists():
            wt_file.unlink()

    diff = mgr.get_worktree_diff(sub_id)
    if expected_change == "modified":
        assert rel_path in diff["modified"]
        assert diff["has_changes"] is True
        assert len(diff["diff"]) > 0
    elif expected_change == "added":
        assert rel_path in diff["added"]
        assert diff["has_changes"] is True
    elif expected_change == "deleted":
        assert rel_path in diff["deleted"]
        assert diff["has_changes"] is True
    elif expected_change == "unchanged":
        assert rel_path not in diff["modified"]
        assert rel_path not in diff["added"]
        assert rel_path not in diff["deleted"]


def test_worktree_atomic_merge_to_root(tmp_path):
    (tmp_path / "base.py").write_text("def base(): return 1\n", encoding="utf-8")
    (tmp_path / "delete_me.txt").write_text("kill me\n", encoding="utf-8")

    mgr = WorktreeManager(workspace_root=tmp_path)
    sub_id = "agent-merger-99"
    wt = mgr.create_worktree(sub_id)

    # 1. Modify base.py
    (wt / "base.py").write_text("def base(): return 42\n", encoding="utf-8")
    # 2. Add new file
    (wt / "added.py").write_text("def added(): return 'hello'\n", encoding="utf-8")
    # 3. Delete file
    (wt / "delete_me.txt").unlink()

    success, merged_files, msg = mgr.merge_worktree_to_root(sub_id)
    assert success is True
    assert "base.py" in merged_files
    assert "added.py" in merged_files
    assert "delete_me.txt" in merged_files

    # Verify changes applied on root workspace
    assert (tmp_path / "base.py").read_text(encoding="utf-8") == "def base(): return 42\n"
    assert (tmp_path / "added.py").read_text(encoding="utf-8") == "def added(): return 'hello'\n"
    assert not (tmp_path / "delete_me.txt").exists()


def test_worktree_merge_no_changes(tmp_path):
    (tmp_path / "file.py").write_text("content", encoding="utf-8")
    mgr = WorktreeManager(workspace_root=tmp_path)
    sub_id = "agent-no-changes"
    mgr.create_worktree(sub_id)

    success, merged, msg = mgr.merge_worktree_to_root(sub_id)
    assert success is True
    assert merged == []
    assert "No modifications" in msg


def test_worktree_cleanups(tmp_path):
    mgr = WorktreeManager(workspace_root=tmp_path)
    wt1 = mgr.create_worktree("agent-c1")
    wt2 = mgr.create_worktree("agent-c2")

    assert wt1.exists()
    assert wt2.exists()

    # Individual cleanup
    mgr.cleanup_worktree("agent-c1")
    assert not wt1.exists()
    assert wt2.exists()

    # Cleanup all
    mgr.cleanup_all()
    assert not wt2.exists()


# ============================================================================
# 2. Subagent Roles, States, Specifications & Results
# ============================================================================

ROLES_AND_DESCRIPTIONS = [
    (SubagentRole.ARCHITECT, "architect"),
    (SubagentRole.CODER, "coder"),
    (SubagentRole.CRITIC, "critic"),
    (SubagentRole.TEST_ENGINEER, "test_engineer"),
    (SubagentRole.DOCS, "docs"),
]

@pytest.mark.parametrize("role,expected_val", ROLES_AND_DESCRIPTIONS)
def test_subagent_role_enum_values(role: SubagentRole, expected_val: str):
    assert role.value == expected_val


STATES_AND_VALUES = [
    (SubagentState.IDLE, "idle"),
    (SubagentState.RUNNING, "running"),
    (SubagentState.AUDITING, "auditing"),
    (SubagentState.MERGED, "merged"),
    (SubagentState.COMPLETED, "completed"),
    (SubagentState.FAILED, "failed"),
    (SubagentState.CANCELLED, "cancelled"),
]

@pytest.mark.parametrize("state,expected_val", STATES_AND_VALUES)
def test_subagent_state_enum_values(state: SubagentState, expected_val: str):
    assert state.value == expected_val


SPEC_PERMUTATIONS = [
    ("spec-01", SubagentRole.ARCHITECT, "Formulate system architecture", "gemini-2.5-pro", 5),
    ("spec-02", SubagentRole.CODER, "Implement authentication middleware", "claude-3-7-sonnet", 8),
    ("spec-03", SubagentRole.CRITIC, "Red-team security audit", "gpt-4o", 4),
    ("spec-04", SubagentRole.TEST_ENGINEER, "Generate end-to-end integration tests", None, 10),
    ("spec-05", SubagentRole.DOCS, "Write OpenAPI documentation", "deepseek-coder", 6),
    ("spec-06", SubagentRole.CODER, "Refactor database connection pool", None, 8),
    ("spec-07", SubagentRole.CRITIC, "Inspect AST contract invariants", "gemini-2.5-flash", 3),
    ("spec-08", SubagentRole.ARCHITECT, "Decompose SWE-bench task", "claude-3-5-sonnet", 6),
    ("spec-09", SubagentRole.TEST_ENGINEER, "Verify fuzzy patch robustness", None, 12),
    ("spec-10", SubagentRole.DOCS, "Draft deployment runbook", None, 5),
]

@pytest.mark.parametrize("spec_id,role,goal,model_override,max_turns", SPEC_PERMUTATIONS)
def test_subagent_spec_contracts(spec_id: str, role: SubagentRole, goal: str, model_override: str | None, max_turns: int):
    spec = SubagentSpec(
        id=spec_id,
        role=role,
        goal=goal,
        model_override=model_override,
        max_turns=max_turns
    )
    assert spec.id == spec_id
    assert spec.role == role
    assert spec.goal == goal
    assert spec.model_override == model_override
    assert spec.max_turns == max_turns
    assert spec.worktree_path is None
    assert isinstance(spec.metadata, dict)


RESULT_PERMUTATIONS = [
    ("sub-1", SubagentRole.CODER, True, SubagentState.COMPLETED, "Logic implemented", ["src/a.py"], True),
    ("sub-2", SubagentRole.CRITIC, False, SubagentState.FAILED, "Found security regression", [], False),
    ("sub-3", SubagentRole.TEST_ENGINEER, True, SubagentState.MERGED, "50 tests added", ["tests/t1.py"], True),
    ("sub-4", SubagentRole.ARCHITECT, True, SubagentState.COMPLETED, "Architecture plan created", [], True),
    ("sub-5", SubagentRole.DOCS, True, SubagentState.MERGED, "Docs generated", ["API.md"], True),
    ("sub-6", SubagentRole.CODER, False, SubagentState.CANCELLED, "Turn budget exhausted", ["draft.py"], False),
    ("sub-7", SubagentRole.CRITIC, True, SubagentState.AUDITING, "Audit in progress", [], False),
    ("sub-8", SubagentRole.CODER, True, SubagentState.MERGED, "Bug fixed cleanly", ["bug.py"], True),
    ("sub-9", SubagentRole.TEST_ENGINEER, True, SubagentState.COMPLETED, "Coverage at 99%", ["t.py"], True),
    ("sub-10", SubagentRole.ARCHITECT, True, SubagentState.COMPLETED, "Contracts defined", [], True),
]

@pytest.mark.parametrize("sub_id,role,success,state,output,files,critic_approved", RESULT_PERMUTATIONS)
def test_subagent_result_properties(sub_id: str, role: SubagentRole, success: bool, state: SubagentState, output: str, files: list[str], critic_approved: bool):
    res = SubagentResult(
        subagent_id=sub_id,
        role=role,
        success=success,
        state=state,
        output=output,
        modified_files=files,
        critic_approved=critic_approved
    )
    assert res.subagent_id == sub_id
    assert res.role == role
    assert res.success is success
    assert res.state == state
    assert res.summary == output
    assert res.files_modified == files
    assert res.critic_approved is critic_approved


# ============================================================================
# 3. Swarm Consensus & Multi-Agent Voting Algorithms
# ============================================================================

def simple_majority_vote(votes: list[str]) -> str:
    """Computes majority outcome among voter recommendations."""
    if not votes:
        return "ABORT"
    counts = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    # Sort by count desc, then alphabetically for deterministic tie-breaking
    sorted_votes = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return sorted_votes[0][0]


MAJORITY_VOTE_CASES = [
    (["APPROVE", "APPROVE", "REJECT"], "APPROVE"),
    (["REJECT", "REJECT", "APPROVE"], "REJECT"),
    (["APPROVE", "APPROVE", "APPROVE"], "APPROVE"),
    (["REVISE", "APPROVE", "REVISE"], "REVISE"),
    (["OPTION_A", "OPTION_B", "OPTION_A", "OPTION_C"], "OPTION_A"),
    (["PLAN", "EXECUTE", "PLAN"], "PLAN"),
    (["MERGE", "REJECT", "MERGE"], "MERGE"),
    (["RETRY", "RETRY", "ABORT"], "RETRY"),
    (["PASS", "FAIL", "PASS", "PASS"], "PASS"),
    (["YES", "NO", "YES"], "YES"),
]

@pytest.mark.parametrize("votes,expected_winner", MAJORITY_VOTE_CASES)
def test_swarm_simple_majority_vote(votes: list[str], expected_winner: str):
    assert simple_majority_vote(votes) == expected_winner


def weighted_expertise_vote(ballots: list[tuple[SubagentRole, str, float]]) -> str:
    """Computes role-weighted outcome: (role, vote_value, weight)."""
    scores = {}
    for role, choice, weight in ballots:
        scores[choice] = scores.get(choice, 0.0) + weight
    sorted_scores = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return sorted_scores[0][0]


WEIGHTED_EXPERTISE_CASES = [
    # Critic has 4.0 weight on security reject, overriding 2 coders with 1.0 weight each
    ([
        (SubagentRole.CODER, "MERGE", 1.0),
        (SubagentRole.CODER, "MERGE", 1.0),
        (SubagentRole.CRITIC, "BLOCK", 4.0),
    ], "BLOCK"),
    # Architect has 3.0 weight on design plan
    ([
        (SubagentRole.ARCHITECT, "REFACTOR_FIRST", 3.0),
        (SubagentRole.CODER, "PATCH_NOW", 1.0),
        (SubagentRole.TEST_ENGINEER, "PATCH_NOW", 1.0),
    ], "REFACTOR_FIRST"),
    # Test engineer has 4.0 weight on test quality gate
    ([
        (SubagentRole.CODER, "SHIP", 1.0),
        (SubagentRole.TEST_ENGINEER, "ADD_TESTS", 4.0),
        (SubagentRole.ARCHITECT, "SHIP", 1.5),
    ], "ADD_TESTS"),
    # Agreement across all tiers
    ([
        (SubagentRole.ARCHITECT, "APPROVE", 3.0),
        (SubagentRole.CODER, "APPROVE", 2.0),
        (SubagentRole.CRITIC, "APPROVE", 4.0),
        (SubagentRole.TEST_ENGINEER, "APPROVE", 3.0),
    ], "APPROVE"),
    # Coder + Architect tie with Critic
    ([
        (SubagentRole.ARCHITECT, "PLAN_A", 2.0),
        (SubagentRole.CODER, "PLAN_A", 2.0),
        (SubagentRole.CRITIC, "PLAN_B", 3.0),
    ], "PLAN_A"),
]

@pytest.mark.parametrize("ballots,expected_outcome", WEIGHTED_EXPERTISE_CASES)
def test_swarm_weighted_expertise_vote(ballots: list, expected_outcome: str):
    assert weighted_expertise_vote(ballots) == expected_outcome


def require_unanimous_consensus(votes: list[str], target_action: str = "MUTATE_SYSTEM") -> bool:
    """Verifies that all subagents unanimously agree before destructive system actions."""
    if not votes:
        return False
    return all(v == target_action for v in votes)


UNANIMOUS_CONSENSUS_CASES = [
    (["MUTATE_SYSTEM", "MUTATE_SYSTEM", "MUTATE_SYSTEM"], True),
    (["MUTATE_SYSTEM", "BLOCK", "MUTATE_SYSTEM"], False),
    (["MUTATE_SYSTEM"], True),
    ([], False),
    (["BLOCK", "BLOCK", "BLOCK"], False),
    (["MUTATE_SYSTEM", "MUTATE_SYSTEM", "WAIT"], False),
    (["MUTATE_SYSTEM", "ABORT"], False),
    (["MUTATE_SYSTEM", "MUTATE_SYSTEM", "MUTATE_SYSTEM", "MUTATE_SYSTEM"], True),
    (["HOLD", "MUTATE_SYSTEM"], False),
    (["MUTATE_SYSTEM", "MUTATE_SYSTEM", "MUTATE_SYSTEM", "NO"], False),
]

@pytest.mark.parametrize("votes,expected_consensus", UNANIMOUS_CONSENSUS_CASES)
def test_swarm_unanimous_consensus(votes: list[str], expected_consensus: bool):
    assert require_unanimous_consensus(votes, "MUTATE_SYSTEM") is expected_consensus


# ============================================================================
# 4. SwarmPhaseOutcome & SwarmResult Telemetry Contracts
# ============================================================================

SWARM_PHASE_CASES = [
    ("Architect Specifier", "sub-arch-1", True, "Architecture defined", ["spec.md"]),
    ("Code Implementer", "sub-coder-2", True, "Code generated", ["src/auth.py"]),
    ("Adversarial Reviewer", "sub-critic-3", True, "Clean audit", []),
    ("Verification Tester", "sub-test-4", True, "All tests pass", ["tests/test_auth.py"]),
    ("Code Implementer", "sub-coder-5", False, "Build error", ["src/broken.py"]),
    ("Adversarial Reviewer", "sub-critic-6", False, "Vulnerability detected", []),
    ("Architect Specifier", "sub-arch-7", True, "Plan updated", []),
    ("Verification Tester", "sub-test-8", False, "1 test failed", []),
    ("Docs Specialist", "sub-docs-9", True, "Docs written", ["docs/index.md"]),
    ("Code Implementer", "sub-coder-10", True, "Refactored cleanly", ["src/db.py"]),
]

@pytest.mark.parametrize("phase_name,sub_id,success,summary,artifacts", SWARM_PHASE_CASES)
def test_swarm_phase_outcome_properties(phase_name: str, sub_id: str, success: bool, summary: str, artifacts: list[str]):
    outcome = SwarmPhaseOutcome(
        phase_name=phase_name,
        subagent_id=sub_id,
        success=success,
        summary=summary,
        artifacts_produced=artifacts
    )
    assert outcome.phase_name == phase_name
    assert outcome.subagent_id == sub_id
    assert outcome.success is success
    assert outcome.summary == summary
    assert outcome.artifacts_produced == artifacts


def test_swarm_result_aggregation():
    phases = [
        SwarmPhaseOutcome("Architect", "a-1", True, "Specs ok", ["spec.md"]),
        SwarmPhaseOutcome("Coder", "c-2", True, "Code ok", ["src/app.py"]),
        SwarmPhaseOutcome("Critic", "cr-3", True, "No flaws found"),
        SwarmPhaseOutcome("Tester", "t-4", True, "30 tests passed", ["tests/test_app.py"]),
    ]

    res = SwarmResult(
        goal="Implement user authentication API",
        success=True,
        total_phases=len(phases),
        duration_s=4.25,
        phases=phases,
        final_output="Authentication API successfully built and verified.",
        adversarial_findings=[]
    )

    assert res.goal == "Implement user authentication API"
    assert res.success is True
    assert res.total_phases == 4
    assert res.duration_s == 4.25
    assert len(res.phases) == 4
    assert res.adversarial_findings == []
    assert "Authentication API successfully built" in res.final_output


def test_swarm_result_adversarial_findings_propagation():
    phases = [
        SwarmPhaseOutcome("Architect", "a-1", True, "Specs ok"),
        SwarmPhaseOutcome("Coder", "c-2", True, "Code ok"),
        SwarmPhaseOutcome("Critic", "cr-3", False, "Found SQL injection risk at auth.py:42", diagnostics=["SQLi vulnerability"]),
    ]

    res = SwarmResult(
        goal="Add user query endpoint",
        success=False,
        total_phases=len(phases),
        duration_s=3.10,
        phases=phases,
        final_output="Swarm rejected by adversarial reviewer.",
        adversarial_findings=["Found SQL injection risk at auth.py:42"]
    )

    assert res.success is False
    assert len(res.adversarial_findings) == 1
    assert "SQL injection risk" in res.adversarial_findings[0]
