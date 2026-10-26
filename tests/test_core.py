import unittest
import os
import tempfile
from pathlib import Path

from prubeth.runtime.state_machine import TaskStateMachine, TaskState, StateMachineError
from prubeth.persistence.database import TaskDatabase
from prubeth.security.permissions import SecurityEngine, PermissionLevel
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.verification.verifier import IndependentVerifier
from prubeth.runtime.controller import extract_json_object
from prubeth.config.manager import ConfigManager

class TestPrubethCore(unittest.TestCase):

    def test_config_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = ConfigManager(config_dir=Path(tmpdir))
            # Test default get (Highest Flagship Pro Model with native Context Caching)
            self.assertEqual(cfg.get("default_model"), "gemini-2.5-pro")
            
            # Test set and persistence
            cfg.set("default_model", "claude-3-7-sonnet")
            self.assertEqual(cfg.get("default_model"), "claude-3-7-sonnet")

            # Test provider resolution
            resolved = cfg.resolve_model_and_provider("deepseek-chat")
            self.assertEqual(resolved["provider"], "deepseek")
            self.assertEqual(resolved["model"], "deepseek-chat")

            # Test local model resolution
            resolved_local = cfg.resolve_model_and_provider("qwen2.5-coder:7b")
            self.assertEqual(resolved_local["provider"], "lm_studio")

    def test_json_extractor_variants(self):
        # Case 1: Plain JSON
        plain = '{"tool": "read_file", "args": {"path": "a.txt"}}'
        self.assertEqual(extract_json_object(plain)["tool"], "read_file")

        # Case 2: Markdown fenced block
        fenced = 'Here is the tool invocation:\n```json\n{"tool": "write_file", "args": {"path": "b.py"}}\n```'
        self.assertEqual(extract_json_object(fenced)["tool"], "write_file")

        # Case 3: Embedded with conversational prefix and suffix
        conversational = 'I will now inspect the files.\n{"tool": "grep_search", "args": {"query": "def foo"}}\nPlease wait.'
        self.assertEqual(extract_json_object(conversational)["tool"], "grep_search")

    def test_state_machine_valid_flow(self):
        sm = TaskStateMachine("test_task_1")
        self.assertEqual(sm.current_state, TaskState.CREATED)

        sm.transition_to(TaskState.CONTEXTUALIZING)
        self.assertEqual(sm.current_state, TaskState.CONTEXTUALIZING)

        sm.transition_to(TaskState.PLANNING)
        sm.transition_to(TaskState.READY)
        sm.transition_to(TaskState.EXECUTING)
        sm.transition_to(TaskState.VERIFYING)
        sm.transition_to(TaskState.COMPLETED)
        self.assertTrue(sm.is_terminal())

    def test_state_machine_illegal_transition(self):
        sm = TaskStateMachine("test_task_2")
        with self.assertRaises(StateMachineError):
            sm.transition_to(TaskState.COMPLETED) # Cannot jump directly to completed

    def test_sqlite_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "test.db"
            db = TaskDatabase(str(db_file))
            try:
                task = db.create_task("t1", "Fix bug in auth")
                self.assertEqual(task.state, "CREATED")

                db.update_task_state("t1", "CREATED", "PLANNING", "Generated plan")
                updated = db.get_task("t1")
                self.assertEqual(updated.state, "PLANNING")
            finally:
                db.close()

    def test_security_jail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sec = SecurityEngine(workspace_root=tmpdir)
            
            # File inside jail
            safe_file = Path(tmpdir) / "app.py"
            is_safe, _, _ = sec.validate_path(str(safe_file))
            self.assertTrue(is_safe)

            # File outside jail
            is_safe, _, err = sec.validate_path("../../outside.txt")
            self.assertFalse(is_safe)
            self.assertIn("Security Violation", err)

            # Dangerous command blocked
            is_permitted, err = sec.check_tool_permission("run_command", {"command": "rm -rf /"})
            self.assertFalse(is_permitted)
            self.assertIn("SECURITY DENIAL", err)

    def test_verifier_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = IndependentVerifier(workspace_root=tmpdir)
            framework = verifier.detect_test_framework()
            self.assertIn(framework, ["python_unittest", "pytest"])

    def test_snapshot_and_rollback(self):
        from prubeth.persistence.checkpoints import SnapshotManager
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            orig_file = ws / "main.py"
            orig_file.write_text("print('original')", encoding="utf-8")

            snap_mgr = SnapshotManager(workspace_root=ws, task_id="test_task")
            msg = snap_mgr.create_snapshot("step_1")
            self.assertIn("created", msg)

            # Modify original file and create a new dirty file
            orig_file.write_text("print('corrupted')", encoding="utf-8")
            dirty_file = ws / "broken.py"
            dirty_file.write_text("syntax error !!!", encoding="utf-8")

            # Rollback
            success = snap_mgr.rollback_to_snapshot("step_1")
            self.assertTrue(success)

            # Assert original restored and dirty file removed
            self.assertEqual(orig_file.read_text(encoding="utf-8"), "print('original')")
            self.assertFalse(dirty_file.exists())

    def test_settings_toggle_functionality(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = ConfigManager(config_dir=Path(tmpdir))
            # Test toggling developer_mode
            val1 = cfg.toggle("developer_mode")
            self.assertFalse(val1)
            val2 = cfg.toggle("developer_mode")
            self.assertTrue(val2)

            # Test organized settings dictionary
            organized = cfg.get_organized_settings()
            self.assertTrue(any("Performance" in k for k in organized))
            self.assertTrue(any("Cognitive" in k for k in organized))
            self.assertTrue(any("Resilience" in k for k in organized))

            # Test profile application
            profile_deep = cfg.apply_profile("deep-reasoning")
            self.assertEqual(profile_deep["badge"], "🧠 DEEP-REASONING")
            self.assertEqual(cfg.get("max_execution_turns"), 15)
            self.assertEqual(cfg.get("self_healing_retries"), 5)

            # Test builder profile
            profile_builder = cfg.apply_profile("builder")
            self.assertEqual(profile_builder["badge"], "⚡ BUILDER")
            self.assertTrue(cfg.get("enable_prompt_caching"))

    def test_tool_argument_aliases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            sec = SecurityEngine(workspace_root=str(ws), auto_approve_all=True)
            db = TaskDatabase(str(ws / "test.db"))
            try:
                engine = ToolExecutionEngine(sec, db, "test_aliases")

                # Write file using file_path instead of path
                ok, out = engine.execute_tool("write_file", {"file_path": "alias_test.py", "content": "x = 42\n"})
                self.assertTrue(ok)
                self.assertTrue((ws / "alias_test.py").exists())

                # Read file using filepath
                ok, content = engine.execute_tool("read_file", {"filepath": "alias_test.py"})
                self.assertTrue(ok)
                self.assertIn("x = 42", content)

                # Grep search using pattern
                ok, search_out = engine.execute_tool("grep_search", {"pattern": "42", "path": "."})
                self.assertTrue(ok)
                self.assertIn("alias_test.py", search_out)
            finally:
                db.close()

if __name__ == "__main__":
    unittest.main()
