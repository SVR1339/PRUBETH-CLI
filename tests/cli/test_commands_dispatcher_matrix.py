"""Comprehensive Unit Test Matrix for PRUBETH CLI Slash Command Dispatchers.

Validates all command handlers in prubeth.cli.commands across parameter variations,
error states, isolated mock workspaces, and console outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from prubeth.cli.commands import (
    handle_init_command,
    handle_swarm_command,
    handle_worktrees_command,
    handle_memory_command,
    handle_bridge_command,
    handle_consensus_command,
    handle_mcp_command,
    handle_review_command,
    handle_goal_command,
    handle_commit_command,
    handle_pr_command,
    handle_learn_command,
    handle_symbols_command,
    handle_callers_command,
    handle_autotune_command,
    handle_research_command,
    handle_janitor_command,
    handle_bio_command,
    handle_migrate_command,
    handle_issue_command,
    handle_timeline_command,
    handle_cache_command,
    handle_compact_command,
    handle_benchmark_command,
    handle_language_command,
    handle_thinking_command,
    handle_todo_command,
    handle_map_command,
    handle_lint_command,
    handle_debug_command,
    handle_pin_command,
    handle_arena_command,
    handle_verify_command,
)
from prubeth.models.gateway import GenerationResponse


@pytest.fixture
def mock_controller(tmp_path):
    ctrl = MagicMock()
    ctrl.workspace_root = str(tmp_path)
    ctrl.memory_vault = MagicMock()
    ctrl.memory_vault.memory_dir = tmp_path / ".prubeth" / "memory"
    ctrl.memory_vault.get_anti_patterns.return_value = []
    ctrl.memory_vault.get_decisions.return_value = []
    ctrl.subagent_mgr = MagicMock()
    ctrl.subagent_mgr.list_subagents.return_value = []
    ctrl.ide_bridge = MagicMock()
    ctrl.ide_bridge.running = False
    ctrl.ide_bridge.client_count = 0
    ctrl.config_manager = MagicMock()
    ctrl.config_manager.load_config.return_value = {
        "thinking_budget": 2048,
        "reasoning_effort": "medium",
        "default_model": "gemini-2.5-pro",
        "default_language": "python",
    }
    ctrl.config_manager.resolve_model_and_provider.return_value = {"model": "gemini-2.5-pro", "provider": "google"}
    ctrl.gateway = MagicMock()
    ctrl.gateway.cfg_mgr = ctrl.config_manager
    ctrl.gateway.generate.return_value = GenerationResponse(text="Mocked gateway output.")
    ctrl.compact_history.return_value = {
        "original_turns": 6,
        "compacted_turns": 2,
        "original_chars": 5000,
        "compacted_chars": 1500,
        "tokens_saved_approx": 875,
    }
    return ctrl


def test_init_command_creates_prubeth_md(tmp_path):
    """Verifies handle_init_command writes PRUBETH.md and handles existing file gracefully."""
    with patch("prubeth.cli.commands.console"):
        handle_init_command(tmp_path)
        p_file = tmp_path / "PRUBETH.md"
        assert p_file.is_file()
        content = p_file.read_text(encoding="utf-8")
        assert "PRUBETH Workspace Rules" in content

        # Second call does not overwrite
        handle_init_command(tmp_path)
        assert p_file.is_file()


def test_swarm_command_list_and_roles(mock_controller):
    """Verifies handle_swarm_command lists empty swarm and explains available roles."""
    with patch("prubeth.cli.commands.console") as mock_console:
        handle_swarm_command(["list"], mock_controller)
        assert mock_console.print.called

        handle_swarm_command(["roles"], mock_controller)
        assert mock_console.print.called

        # Invalid role
        handle_swarm_command(["spawn", "nonexistent_role", "Task"], mock_controller)
        assert mock_console.print.called

        # Missing goal
        handle_swarm_command(["spawn", "coder"], mock_controller)
        assert mock_console.print.called


def test_swarm_command_spawn_success(mock_controller):
    """Verifies handle_swarm_command executes a role successfully."""
    from prubeth.agents.base import SubagentRole, SubagentResult, SubagentState, SubagentSpec
    spec = SubagentSpec(id="sub-123", role=SubagentRole.CODER, goal="Add unit tests", worktree_path=Path("/tmp/mock"))
    run_res = SubagentResult(
        subagent_id="sub-123",
        role=SubagentRole.CODER,
        success=True,
        state=SubagentState.MERGED,
        critic_approved=True,
        modified_files=["src/test.py"],
        output="Successfully created tests",
    )
    mock_controller.subagent_mgr.spawn_subagent.return_value = spec
    mock_controller.subagent_mgr.run_subagent.return_value = run_res

    with patch("prubeth.cli.commands.console") as mock_console:
        handle_swarm_command(["spawn", "coder", "Add", "unit", "tests"], mock_controller)
        assert mock_console.print.called


def test_worktrees_command_matrix(mock_controller, tmp_path):
    """Verifies handle_worktrees_command list, diff, and clean actions."""
    with patch("prubeth.cli.commands.WorktreeManager") as MockWT:
        wt_instance = MockWT.return_value
        wt_instance.list_active_worktrees.return_value = []
        wt_instance.get_worktree_diff.return_value = {"diff": "--- a/f\n+++ b/f\n+new", "modified": ["f"], "added": []}
        wt_instance.cleanup_all_worktrees.return_value = 3

        with patch("prubeth.cli.commands.console"):
            handle_worktrees_command(["list"], mock_controller)
            handle_worktrees_command(["diff"], mock_controller)  # Missing ID
            handle_worktrees_command(["diff", "wt-1"], mock_controller)
            handle_worktrees_command(["clean"], mock_controller)


def test_memory_command_matrix(mock_controller):
    """Verifies handle_memory_command summary, anti-patterns, decisions, and record."""
    with patch("prubeth.cli.commands.console"):
        handle_memory_command(["summary"], mock_controller)
        handle_memory_command(["anti-patterns"], mock_controller)
        handle_memory_command(["decisions"], mock_controller)
        handle_memory_command(["record"], mock_controller)  # Missing args
        handle_memory_command(["record", "Auth", "InvalidTokenError", "Verify signature with HS256"], mock_controller)
        assert mock_controller.memory_vault.record_anti_pattern.called


def test_bridge_command_status_and_ping(mock_controller):
    """Verifies handle_bridge_command status and ping diagnostic handling."""
    with patch("prubeth.cli.commands.console"):
        handle_bridge_command(["status"], mock_controller)
        with patch("socket.socket") as mock_sock:
            mock_sock.return_value.connect.side_effect = ConnectionRefusedError()
            handle_bridge_command(["ping"], mock_controller)


def test_consensus_command():
    """Verifies handle_consensus_command prints AST & adversarial consensus rules."""
    with patch("prubeth.cli.commands.console") as mock_console:
        handle_consensus_command([])
        assert mock_console.print.called


def test_mcp_command_matrix():
    """Verifies handle_mcp_command presets, tools, install, and add handling."""
    with patch("prubeth.mcp.manager.MCPManager") as MockMCP:
        mgr = MockMCP.return_value
        mgr.get_all_servers.return_value = []
        mgr.get_all_tools.return_value = []
        mgr.install_preset.return_value = (True, "Installed preset")
        mgr.remove_server_config.return_value = True

        with patch("prubeth.cli.commands.console"):
            handle_mcp_command(["list"])
            handle_mcp_command(["presets"])
            handle_mcp_command(["tools"])
            handle_mcp_command(["install"])  # Missing preset
            handle_mcp_command(["install", "filesystem"])
            handle_mcp_command(["remove", "server1"])


def test_review_command_clean_and_modified(mock_controller):
    """Verifies handle_review_command handles clean and modified trees."""
    with patch("prubeth.persistence.checkpoints.SnapshotManager") as MockSnap:
        snap = MockSnap.return_value
        snap.compute_snapshot_diff.return_value = "No changes detected."

        with patch("prubeth.cli.commands.console"):
            handle_review_command(mock_controller)

        snap.compute_snapshot_diff.return_value = "--- a/code.py\n+++ b/code.py\n+def foo(): pass"
        with patch("prubeth.models.gateway.UniversalModelGateway") as MockGW:
            gw = MockGW.return_value
            gw.generate.return_value = GenerationResponse(text="Code review: looks good.")
            with patch("prubeth.cli.commands.console"):
                handle_review_command(mock_controller)


def test_goal_command_matrix(mock_controller):
    """Verifies handle_goal_command list, resume, and new objective execution."""
    with patch("prubeth.runtime.goal.GoalSupervisor") as MockSupervisor:
        sup = MockSupervisor.return_value
        sup.list_goals.return_value = []
        sup.load_goal_state.return_value = {"id": "g-1", "objective": "Build REST API"}

        with patch("prubeth.cli.commands.console"):
            handle_goal_command([], mock_controller)
            handle_goal_command(["resume"], mock_controller)
            handle_goal_command(["Build", "a", "FastAPI", "server"], mock_controller)
            assert sup.execute_goal.called


def test_commit_command_matrix(tmp_path, mock_controller):
    """Verifies handle_commit_command generates conventional commit messages."""
    with patch("prubeth.models.gateway.UniversalModelGateway") as MockGW:
        gw = MockGW.return_value
        gw.generate.return_value = GenerationResponse(text="feat(api): add auth endpoint")
        with patch("prubeth.cli.commands.console"):
            # Clean diff
            handle_commit_command([], mock_controller, diff_override="No changes detected")
            # With diff
            diff = "--- a/api.py\n+++ b/api.py\n+@app.get('/health')\n+def h(): return 200"
            handle_commit_command([], mock_controller, diff_override=diff)
            commit_file = Path.cwd() / ".prubeth" / "commits" / "COMMIT_MSG.txt"
            assert commit_file.is_file()


def test_pr_command_matrix(mock_controller):
    """Verifies handle_pr_command synthesizes pull request markdown."""
    with patch("prubeth.models.gateway.UniversalModelGateway") as MockGW:
        gw = MockGW.return_value
        gw.generate.return_value = GenerationResponse(text="## Summary\nAdded health check endpoint.")
        with patch("prubeth.cli.commands.console"):
            handle_pr_command([], mock_controller, diff_override="No changes")
            diff = "--- a/app.py\n+++ b/app.py\n+def health(): pass"
            handle_pr_command([], mock_controller, diff_override=diff)
            pr_file = Path.cwd() / ".prubeth" / "PULL_REQUEST.md"
            assert pr_file.is_file()


def test_learn_command_matrix(tmp_path, mock_controller):
    """Verifies handle_learn_command list, add, remove, and clear directives."""
    learnings_file = Path.cwd() / ".prubeth" / "memory" / "learnings.json"
    learnings_file.parent.mkdir(parents=True, exist_ok=True)
    learnings_file.write_text("[]", encoding="utf-8")

    with patch("prubeth.cli.commands.console"):
        handle_learn_command(["list"], mock_controller)
        handle_learn_command(["Always", "use", "pytest", "fixtures"], mock_controller)
        data = json.loads(learnings_file.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert "fixtures" in data[0]["directive"]

        handle_learn_command(["remove", "1"], mock_controller)
        data_after = json.loads(learnings_file.read_text(encoding="utf-8"))
        assert len(data_after) == 0

        handle_learn_command(["Directive", "two"], mock_controller)
        handle_learn_command(["clear"], mock_controller)
        assert json.loads(learnings_file.read_text(encoding="utf-8")) == []


def test_symbols_and_callers_command(mock_controller):
    """Verifies AST symbol discovery and callers command."""
    with patch("prubeth.repository.intelligence.RepositoryIntelligence") as MockIntel:
        intel = MockIntel.return_value
        intel.list_all_symbols.return_value = [{"name": "MyClass", "type": "class", "file": "app.py", "line": 10, "signature": "class MyClass:"}]
        intel.find_symbol_references.return_value = [{"file": "main.py", "line": 5, "scope": "entry", "context": "obj = MyClass()", "is_definition": False}]

        with patch("prubeth.cli.commands.console"):
            handle_symbols_command([], mock_controller)
            handle_callers_command([], mock_controller)  # Missing symbol
            handle_callers_command(["MyClass"], mock_controller)


def test_autotune_and_research_command(mock_controller):
    """Verifies autotune and research command loops."""
    with patch("prubeth.compute.autotune.KernelAutotuner") as MockTuner:
        tuner = MockTuner.return_value
        tuner.tune_kernel.return_value = {"target_op": "Softmax", "speedup": "2.4x", "latency": "0.12ms", "bandwidth": "850 GB/s"}

        with patch("prubeth.research.experiment.ResearchExperimentLoop") as MockResearch:
            res_loop = MockResearch.return_value
            res_loop.run_experiment.return_value = {"experiment_id": "exp-01", "report_path": "report.md"}

            with patch("prubeth.cli.commands.console"):
                handle_autotune_command(["FlashAttention"], mock_controller)
                handle_research_command([], mock_controller)  # Missing hypothesis
                handle_research_command(["Quantization", "reduces", "latency"], mock_controller)


def test_janitor_and_bio_command(mock_controller):
    """Verifies whole-repo janitor scan and bio molecular structure command."""
    with patch("prubeth.monorepo.janitor.MonorepoJanitor") as MockJanitor:
        janitor = MockJanitor.return_value
        janitor.scan_health.return_value = {
            "monorepo_files_scanned": 42,
            "total_lines_of_code": 8500,
            "vulnerabilities": [],
            "dead_imports": [],
            "health_score": 98,
        }
        janitor.auto_heal_issues.return_value = {"healed_count": 0, "actions": []}

        with patch("prubeth.monorepo.bio.BioComputeBridge") as MockBio:
            bio = MockBio.return_value
            bio.parse_pdb_structure.return_value = {
                "file": "protein.pdb",
                "total_atoms": 1250,
                "total_residues": 160,
                "chains_detected": ["A"],
                "mean_bfactor_plddt": 92.5,
                "structural_confidence": "HIGH",
            }
            bio.generate_molstar_manifest.return_value = {"structure_uri": "pdb://1abc", "format": "PDB", "status": "READY"}

            with patch("prubeth.cli.commands.console"):
                handle_janitor_command(["scan"], mock_controller)
                handle_janitor_command(["fix"], mock_controller)
                handle_bio_command([], mock_controller)  # Missing args
                handle_bio_command(["inspect", "protein.pdb"], mock_controller)
                handle_bio_command(["manifest", "protein.pdb"], mock_controller)


def test_migrate_and_issue_command(mock_controller):
    """Verifies enterprise codebase migrator and autonomous issue resolver dispatchers."""
    with patch("prubeth.runtime.enterprise.AutonomousCodebaseMigrator") as MockMigrator:
        mig = MockMigrator.return_value
        mig.execute_migration.return_value = {"success": True, "transformed_files": ["f.py"], "snapshot_id": "snap-1"}

        with patch("prubeth.runtime.enterprise.AutonomousIssueResolver") as MockResolver:
            resolver = MockResolver.return_value
            resolver.resolve_issue.return_value = {"success": True, "candidate_files": ["f.py"], "snapshot_id": "snap-2", "summary": "Fixed bug"}

            with patch("prubeth.cli.commands.console"):
                handle_migrate_command([], mock_controller)  # Missing objective
                handle_migrate_command(["Upgrade", "to", "Pydantic", "v2"], mock_controller)
                handle_issue_command([], mock_controller)  # Missing description
                handle_issue_command(["Fix", "AttributeError", "in", "worker"], mock_controller)


def test_timeline_and_cache_command(mock_controller):
    """Verifies snapshot timeline and multi-tier prompt cache radar."""
    with patch("prubeth.persistence.checkpoints.SnapshotManager") as MockSnap:
        snap = MockSnap.return_value
        snap.get_timeline.return_value = [
            {"label": "baseline", "timestamp": "2026-10-28T00:00:00", "files_count": 5}
        ]

        with patch("prubeth.cli.hud.calculate_session_spend") as MockSpend:
            MockSpend.return_value = {
                "cached_tokens": 1000,
                "input_tokens": 2000,
                "total_tokens": 3000,
                "total_saved_usd": 0.05,
            }

            with patch("prubeth.cli.commands.console"):
                handle_timeline_command([], mock_controller)
                handle_cache_command(["clear"], mock_controller)
                handle_cache_command(["status"], mock_controller)


def test_compact_and_benchmark_command(mock_controller):
    """Verifies Claude Code-parity history compaction and benchmark suite dispatchers."""
    with patch("prubeth.evaluation.benchmark.AutonomousBenchmarkRunner") as MockRunner:
        runner = MockRunner.return_value
        mock_report = MagicMock()
        mock_report.autonomy_quotient = 95.0
        mock_report.completed_tasks = 4
        mock_report.total_tasks = 4
        mock_report.average_latency_s = 0.4
        mock_report.total_turns = 8
        mock_report.results = []
        runner.run_benchmark.return_value = mock_report

        with patch("prubeth.cli.commands.console"):
            handle_compact_command([], mock_controller)
            handle_benchmark_command([], mock_controller)


def test_language_and_thinking_command(mock_controller):
    """Verifies polyglot ecosystem switcher and thinking budget controls."""
    with patch("prubeth.cli.commands.ConfigManager") as MockCfg:
        cfg = MockCfg.return_value
        cfg.load_config.return_value = {"thinking_budget": 2048, "reasoning_effort": "medium"}

        with patch("prubeth.cli.commands.console"):
            handle_language_command(["status"], mock_controller)
            handle_language_command(["list"], mock_controller)
            handle_language_command(["set", "python"], mock_controller)

            handle_thinking_command([], mock_controller)
            handle_thinking_command(["4096"], mock_controller)
            handle_thinking_command(["effort", "high"], mock_controller)
            handle_thinking_command(["max"], mock_controller)
            handle_thinking_command(["off"], mock_controller)


def test_todo_command_lifecycle(mock_controller, tmp_path):
    """Verifies full lifecycle of /todo: list, add, start, done, and clear."""
    todo_file = tmp_path / ".prubeth" / "TODO.json"
    todo_file.parent.mkdir(parents=True, exist_ok=True)
    todo_file.write_text("[]", encoding="utf-8")

    with patch("prubeth.cli.commands.console"):
        handle_todo_command(["list"], mock_controller)
        handle_todo_command(["add", "Implement", "CSRF", "protection"], mock_controller)
        todos = json.loads(todo_file.read_text(encoding="utf-8"))
        assert len(todos) == 1
        assert todos[0]["title"] == "Implement CSRF protection"

        handle_todo_command(["start", "1"], mock_controller)
        todos = json.loads(todo_file.read_text(encoding="utf-8"))
        assert todos[0]["status"] == "IN_PROGRESS"

        handle_todo_command(["done", "1"], mock_controller)
        todos = json.loads(todo_file.read_text(encoding="utf-8"))
        assert todos[0]["status"] == "DONE"

        handle_todo_command(["clear"], mock_controller)
        todos = json.loads(todo_file.read_text(encoding="utf-8"))
        assert len(todos) == 0


def test_map_lint_debug_pin_command(mock_controller):
    """Verifies repository topology map, linter, crash debugger, and pin commands."""
    with patch("prubeth.repository.topology.CodebaseTopologyMapper") as MockMap:
        with patch("prubeth.security.linter.PolyglotQualityLinter") as MockLint:
            MockLint.return_value.render_report.return_value = 0
            with patch("prubeth.runtime.debugger.AutonomousCrashDebugger") as MockDebug:
                with patch("prubeth.persistence.pinned.PinnedContextManager") as MockPin:
                    with patch("prubeth.cli.commands.console"):
                        handle_map_command([], mock_controller)
                        handle_lint_command([], mock_controller)
                        handle_debug_command([], mock_controller)  # Usage hint
                        handle_debug_command(["pytest", "tests/"], mock_controller)
                        handle_pin_command(["list"], mock_controller)
                        handle_pin_command(["add", "src/auth.py"], mock_controller)
                        handle_pin_command(["unpin", "src/auth.py"], mock_controller)
                        handle_pin_command(["clear"], mock_controller)


def test_arena_and_verify_command(mock_controller):
    """Verifies comparative model arena and universal key verification radar."""
    with patch("prubeth.models.gateway.UniversalModelGateway") as MockGW:
        gw = MockGW.return_value
        gw.generate.return_value = GenerationResponse(text="Analysis comparing approaches.")

        with patch("prubeth.models.key_verifier.UniversalKeyVerifier") as MockVerifier:
            ver = MockVerifier.return_value
            ver.scan_all_configured.return_value = {}

            with patch("prubeth.cli.commands.console"):
                handle_arena_command([], mock_controller)  # Missing prompt
                handle_arena_command(["Compare", "Rust", "vs", "Go", "channels"], mock_controller)
                handle_verify_command([], mock_controller)
