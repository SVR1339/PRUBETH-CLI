import unittest
import socket
import time
import tempfile
from pathlib import Path

from prubeth.agents.worktree import WorktreeManager
from prubeth.agents.base import SubagentRole, SubagentState, SubagentSpec
from prubeth.agents.subagent import SubagentManager
from prubeth.persistence.memory import MemoryVault
from prubeth.integrations.ide_bridge import IDEBridgeServer

class TestPhase2Subsystems(unittest.TestCase):

    def test_worktree_isolation_and_merge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_root = Path(tmpdir)
            (ws_root / "app.py").write_text("def hello(): return 'root'", encoding="utf-8")

            wt_mgr = WorktreeManager(ws_root)
            sub_id = "test-worker-1"
            wt_path = wt_mgr.create_worktree(sub_id)

            self.assertTrue(wt_path.exists())
            self.assertTrue((wt_path / "app.py").exists())

            # Modify file inside worktree ONLY
            (wt_path / "app.py").write_text("def hello(): return 'modified_in_worktree'", encoding="utf-8")
            (wt_path / "new_helper.py").write_text("def helper(): pass", encoding="utf-8")

            # Verify root remains untouched
            self.assertEqual((ws_root / "app.py").read_text(encoding="utf-8"), "def hello(): return 'root'")
            self.assertFalse((ws_root / "new_helper.py").exists())

            # Check diff calculation
            diff_data = wt_mgr.get_worktree_diff(sub_id)
            self.assertTrue(diff_data["has_changes"])
            self.assertIn("app.py", diff_data["modified"])
            self.assertIn("new_helper.py", diff_data["added"])

            # Merge to root
            success, merged, msg = wt_mgr.merge_worktree_to_root(sub_id)
            self.assertTrue(success)
            self.assertIn("app.py", merged)
            self.assertIn("new_helper.py", merged)

            # Verify root now has the changes
            self.assertEqual((ws_root / "app.py").read_text(encoding="utf-8"), "def hello(): return 'modified_in_worktree'")
            self.assertTrue((ws_root / "new_helper.py").exists())

            # Teardown
            wt_mgr.destroy_worktree(sub_id)
            self.assertFalse(wt_path.exists())

    def test_memory_vault_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = MemoryVault(Path(tmpdir))
            
            # Record anti-pattern
            mem.record_anti_pattern(
                failing_component="auth_service",
                error_symptom="KeyError: 'user_id'",
                root_cause="Missing session validation check",
                prevention_rule="Always check if user_id in session before querying database."
            )

            # Record decision
            mem.record_decision(
                decision_title="Use SQLite for persistence",
                rationale="Zero setup overhead and serverless local embedding",
                affected_modules=["persistence/database.py"]
            )

            # Context retrieval
            ctx = mem.get_memory_context()
            self.assertIn("KeyError: 'user_id'", ctx)
            self.assertIn("Always check if user_id in session", ctx)
            self.assertIn("Use SQLite for persistence", ctx)

            # Structured parsing
            anti_patterns = mem.list_anti_patterns()
            self.assertEqual(len(anti_patterns), 1)
            self.assertEqual(anti_patterns[0]["title"], "auth_service")

    def test_subagent_pre_flight_ast_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_root = Path(tmpdir)
            mgr = SubagentManager(ws_root)
            
            # Valid Python
            (ws_root / "valid.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
            clean, err = mgr._pre_flight_ast_check(ws_root, ["valid.py"])
            self.assertTrue(clean)
            self.assertEqual(err, "")

            # Invalid syntax Python
            (ws_root / "invalid.py").write_text("def broken(a, b): return a +\n", encoding="utf-8")
            clean, err = mgr._pre_flight_ast_check(ws_root, ["invalid.py"])
            self.assertFalse(clean)
            self.assertIn("SyntaxError", err)

    def test_subagent_adversarial_critic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SubagentManager(Path(tmpdir))
            spec = SubagentSpec(id="w1", role=SubagentRole.CODER, goal="test")

            # Clean diff
            approved, note = mgr._run_adversarial_critic(spec, "+ def safe(): pass")
            self.assertTrue(approved)

            # Leaked API Key
            approved_leak, note_leak = mgr._run_adversarial_critic(spec, "+ api_key = 'AI_zaSyD_SECRET_KEY'")
            self.assertFalse(approved_leak)
            self.assertIn("Security Violation", note_leak)

            # Destructive rm -rf
            approved_dest, note_dest = mgr._run_adversarial_critic(spec, "+ run_command('rm -rf /')")
            self.assertFalse(approved_dest)
            self.assertIn("Destructive", note_dest)

    def test_ide_bridge_server_events(self):
        bridge = IDEBridgeServer(port=29999)
        bridge.start()
        self.assertTrue(bridge.running)

        try:
            # Connect a mock IDE client
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connected = False
            for _ in range(25):
                try:
                    client.connect(("127.0.0.1", 29999))
                    connected = True
                    break
                except (ConnectionRefusedError, OSError):
                    time.sleep(0.05)
            self.assertTrue(connected, "Failed to connect to IDEBridgeServer")

            for _ in range(25):
                if bridge.client_count >= 1:
                    break
                time.sleep(0.05)
            self.assertEqual(bridge.client_count, 1)

            # Emit an event
            bridge.emit_event("test_event", {"status": "ok"})
            data = client.recv(1024).decode("utf-8")
            self.assertIn("test_event", data)
            self.assertIn("prubeth.ipc/v1", data)

            client.close()
        finally:
            bridge.stop()
            self.assertFalse(bridge.running)

if __name__ == "__main__":
    unittest.main()
