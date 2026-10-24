import os
import unittest
import tempfile
from pathlib import Path
from prubeth.config.manager import ConfigManager
from prubeth.persistence.database import TaskDatabase
from prubeth.persistence.checkpoints import SnapshotManager
from prubeth.persistence.memory import MemoryVault
from prubeth.runtime.state_machine import TaskStateMachine, TaskState
from prubeth.tools.execution import ToolExecutionEngine

class TestBDDBehavioralScenarios(unittest.TestCase):
    """Behavior-Driven Development (BDD): Executable Given-When-Then Acceptance Scenarios."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_bdd_scenario_project_initialization(self):
        """Scenario: Initializing a brand-new workspace repository.
        Given an uninitialized project directory
        When the configuration manager initializes the workspace
        Then .prubeth/config.json exists with valid defaults
        And the configuration is marked as active.
        """
        # Given
        config_dir = self.workspace / ".prubeth"
        self.assertFalse((config_dir / "config.json").exists())

        # When
        config_mgr = ConfigManager(config_dir=config_dir)
        cfg = config_mgr.load_config()

        # Then
        self.assertTrue((config_dir / "config.json").exists())
        self.assertEqual(cfg.get("active_profile"), "builder")
        self.assertEqual(cfg.get("max_execution_turns"), 10)
        self.assertTrue(cfg.get("enable_prompt_caching"))

    def test_bdd_scenario_fsm_autonomous_lifecycle(self):
        """Scenario: Standard autonomous task progression.
        Given a task in the CREATED state
        When the controller advances through CONTEXTUALIZING, PLANNING, READY, EXECUTING, and VERIFYING
        Then the state transitions succeed without invariant violations
        And finally reaches COMPLETED.
        """
        # Given
        fsm = TaskStateMachine(task_id="bdd-task-fsm-1")
        self.assertEqual(fsm.current_state, TaskState.CREATED)

        # When & Then
        fsm.transition_to(TaskState.CONTEXTUALIZING, "Inspecting repository context")
        self.assertEqual(fsm.current_state, TaskState.CONTEXTUALIZING)

        fsm.transition_to(TaskState.PLANNING, "Decomposing prompt into execution steps")
        self.assertEqual(fsm.current_state, TaskState.PLANNING)

        fsm.transition_to(TaskState.READY, "Plan finalized and validated")
        self.assertEqual(fsm.current_state, TaskState.READY)

        fsm.transition_to(TaskState.EXECUTING, "Applying code generation tool")
        self.assertEqual(fsm.current_state, TaskState.EXECUTING)

        fsm.transition_to(TaskState.VERIFYING, "Running polyglot AST and test gates")
        self.assertEqual(fsm.current_state, TaskState.VERIFYING)

        fsm.transition_to(TaskState.COMPLETED, "Task verified successfully")
        self.assertEqual(fsm.current_state, TaskState.COMPLETED)
        self.assertEqual(len(fsm.history), 7)

    def test_bdd_scenario_speculative_plan_b_recovery(self):
        """Scenario: Autonomous recovery from verification failure.
        Given a task undergoing verification that fails
        When the system detects the failure and transitions to RECOVERING
        Then it can re-enter VERIFYING or EXECUTING to apply repairs
        And successfully finish in COMPLETED once repairs pass.
        """
        # Given
        fsm = TaskStateMachine(task_id="bdd-task-fsm-2")
        fsm.transition_to(TaskState.CONTEXTUALIZING)
        fsm.transition_to(TaskState.PLANNING)
        fsm.transition_to(TaskState.READY)
        fsm.transition_to(TaskState.EXECUTING)
        fsm.transition_to(TaskState.VERIFYING)

        # When (Verification fails -> Plan B trigger)
        fsm.transition_to(TaskState.RECOVERING, "SyntaxError in line 4")
        self.assertEqual(fsm.current_state, TaskState.RECOVERING)

        # Then (Self-healing repair)
        fsm.transition_to(TaskState.VERIFYING, "Retrying verification after AST fix")
        self.assertEqual(fsm.current_state, TaskState.VERIFYING)

        fsm.transition_to(TaskState.COMPLETED, "Self-healing succeeded")
        self.assertEqual(fsm.current_state, TaskState.COMPLETED)

    def test_bdd_scenario_deterministic_rollback(self):
        """Scenario: Instantaneous rollback on unwanted changes.
        Given a file with original content and a snapshot taken
        When a destructive or unintended edit occurs
        And a rollback is triggered
        Then the file is restored to its exact original state.
        """
        # Given
        source_file = self.workspace / "service.py"
        source_file.write_text("def run():\n    return 'original'\n", encoding="utf-8")
        engine = SnapshotManager(workspace_root=self.workspace)
        msg = engine.create_snapshot("pre-edit")

        # When (Unintended edit)
        source_file.write_text("def run():\n    return 'corrupted_state'\n", encoding="utf-8")
        self.assertIn("corrupted_state", source_file.read_text(encoding="utf-8"))

        # And Rollback
        success = engine.rollback_to_snapshot("pre-edit")

        # Then
        self.assertTrue(success)
        restored = source_file.read_text(encoding="utf-8")
        self.assertEqual(restored, "def run():\n    return 'original'\n")

    def test_bdd_scenario_continuous_memory_accumulation(self):
        """Scenario: Accumulating organizational memory across sessions.
        Given an initialized Memory Vault
        When decisions and anti-patterns are recorded
        Then they persist in markdown artifacts and can be queried.
        """
        # Given
        vault = MemoryVault(memory_dir=self.workspace / ".prubeth" / "memory")

        # When
        vault.record_decision(
            decision_title="Use SQLite WAL Mode",
            rationale="Eliminates lock contention between CLI reader and background agents",
            affected_modules=["persistence", "runtime"]
        )
        vault.record_anti_pattern(
            failing_component="CheckpointEngine",
            error_symptom="FileNotFoundError",
            root_cause="Missing git in path",
            prevention_rule="Use pure-Python snapshots with SHA256 hashes"
        )

        # Then
        memory_ctx = vault.get_memory_context()
        self.assertIn("Use SQLite WAL Mode", memory_ctx)
        self.assertIn("CheckpointEngine", memory_ctx)

if __name__ == "__main__":
    unittest.main()
