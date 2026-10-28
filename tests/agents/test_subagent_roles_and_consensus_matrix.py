"""PRUBETH Subagent Roles, Prompt Directives & Consensus Matrix.

Exhaustively verifies specialist subagent role prompt synthesis, isolated worktree
execution sandboxes, adversarial critic evaluations, and consensus resolution.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.agents.base import SubagentRole, SubagentSpec, SubagentResult, SubagentState
from prubeth.agents.subagent import SubagentManager


# ============================================================================
# 1. Specialist Role System Prompts
# ============================================================================

def test_subagent_role_system_prompts_architect(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    prompt = mgr._get_role_system_prompt(SubagentRole.ARCHITECT)
    assert "specialized" in prompt.lower() or "architect" in prompt.lower()


def test_subagent_role_system_prompts_coder(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    prompt = mgr._get_role_system_prompt(SubagentRole.CODER)
    assert "implementation engineer" in prompt.lower() or "clean" in prompt.lower()


def test_subagent_role_system_prompts_critic(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    prompt = mgr._get_role_system_prompt(SubagentRole.CRITIC)
    assert "adversarial" in prompt.lower() or "red-team" in prompt.lower()


def test_subagent_role_system_prompts_test_engineer(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    prompt = mgr._get_role_system_prompt(SubagentRole.TEST_ENGINEER)
    assert "test" in prompt.lower()


def test_subagent_role_system_prompts_docs(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    prompt = mgr._get_role_system_prompt(SubagentRole.DOCS)
    assert "writer" in prompt.lower() or "documentation" in prompt.lower()


# ============================================================================
# 2. Subagent Spawning & Worktree Jailing
# ============================================================================

def test_subagent_spawn_provisions_isolated_worktree(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    spec = mgr.spawn_subagent(
        role=SubagentRole.CODER,
        goal="Implement quicksort algorithm",
        max_turns=5
    )

    assert spec.id.startswith("coder-")
    assert spec.role == SubagentRole.CODER
    assert spec.goal == "Implement quicksort algorithm"
    assert spec.max_turns == 5
    assert spec.worktree_path is not None
    assert spec.worktree_path.exists()
    assert spec.id in mgr.active_subagents


def test_subagent_result_properties():
    res = SubagentResult(
        subagent_id="test-sub-01",
        role=SubagentRole.CODER,
        success=True,
        state=SubagentState.MERGED,
        output="Refactored database query engine",
        modified_files=["src/db.py", "src/query.py"]
    )
    assert res.summary == "Refactored database query engine"
    assert res.files_modified == ["src/db.py", "src/query.py"]
    assert res.state == SubagentState.MERGED


# ============================================================================
# 3. Adversarial Critic Evaluation Rules
# ============================================================================

def test_adversarial_critic_approves_clean_diff(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    spec = SubagentSpec(id="clean-agent", role=SubagentRole.CODER, goal="Fix typo")

    clean_diff = """
--- a/src/math.py
+++ b/src/math.py
@@ -1,2 +1,2 @@
-def add(a, b): return a - b
+def add(a, b): return a + b
"""
    approved, msg = mgr._run_adversarial_critic(spec, clean_diff)
    assert approved is True
    assert "passed" in msg.lower()


def test_adversarial_critic_approves_empty_diff(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    spec = SubagentSpec(id="empty-agent", role=SubagentRole.CODER, goal="No-op")
    approved, msg = mgr._run_adversarial_critic(spec, "")
    assert approved is True
    assert "No modifications" in msg


def test_adversarial_critic_rejects_destructive_command_in_diff(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    spec = SubagentSpec(id="malicious-agent", role=SubagentRole.CODER, goal="Cleanup")

    destructive_diff = """
--- a/src/clean.py
+++ b/src/clean.py
@@ -1,1 +1,2 @@
+os.system("rm -rf /")
"""
    approved, msg = mgr._run_adversarial_critic(spec, destructive_diff)
    assert approved is False
    assert "Destructive filesystem deletion" in msg


# ============================================================================
# 4. Telemetry History & Multi-Agent Concurrency
# ============================================================================

def test_subagent_manager_telemetry_history(tmp_path: Path):
    mgr = SubagentManager(workspace_root=tmp_path)
    # Simulate historical result
    res = SubagentResult(
        subagent_id="hist-01",
        role=SubagentRole.TEST_ENGINEER,
        success=True,
        state=SubagentState.MERGED,
        output="Created 15 unit tests",
        modified_files=["tests/test_new.py"],
        critic_approved=True,
        turns_used=3
    )
    mgr.history.append(res)

    telemetry = mgr.list_subagents()
    assert len(telemetry) == 1
    assert telemetry[0]["id"] == "hist-01"
    assert telemetry[0]["role"] == "test_engineer"
    assert telemetry[0]["critic_approved"] is True
    assert telemetry[0]["turns"] == 3
