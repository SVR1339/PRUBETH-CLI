"""Tests for PRUBETH Frontier Parity Features:
1. Long-Horizon Autonomous Goal Mode (GoalSupervisor) [Anthropic Target]
2. Test-Time Compute Self-Verification (TestTimeVerifier) [OpenAI Target]
3. Cross-File AST Symbol Dependency Graph (RepositoryIntelligence) [DeepMind Target]
4. Git-Native Commit & PR Synthesis (handle_commit_command, handle_pr_command) [Anthropic Target]
5. Persistent Invariant Learning (handle_learn_command) [OpenAI/DeepMind Target]
"""

import unittest
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from prubeth.runtime.goal import GoalSupervisor, GoalMilestone
from prubeth.runtime.verification import TestTimeVerifier
from prubeth.repository.intelligence import RepositoryIntelligence
from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.cli.commands import (
    handle_goal_command,
    handle_commit_command,
    handle_pr_command,
    handle_learn_command,
    handle_symbols_command,
    handle_callers_command
)

class TestFrontierParities(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace = Path(self.test_dir)

        # Create sample workspace python files
        self.src_dir = self.workspace / "src"
        self.src_dir.mkdir(parents=True, exist_ok=True)

        self.service_file = self.src_dir / "service.py"
        self.service_file.write_text(
            "class AuthService:\n"
            "    def authenticate(self, username, password):\n"
            "        return username == 'admin'\n\n"
            "def verify_token(token):\n"
            "    return len(token) > 10\n",
            encoding="utf-8"
        )

        self.client_file = self.src_dir / "client.py"
        self.client_file.write_text(
            "from src.service import AuthService, verify_token\n\n"
            "def run_client():\n"
            "    auth = AuthService()\n"
            "    auth.authenticate('admin', 'secret')\n"
            "    return verify_token('valid_token_123')\n",
            encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_repository_intelligence_symbol_references(self):
        """Tests that AST reference engine accurately locates callers across files."""
        intel = RepositoryIntelligence(str(self.workspace))
        
        # Look for AuthService callers
        refs = intel.find_symbol_references("AuthService")
        self.assertGreaterEqual(len(refs), 2)
        # One is class definition in service.py, one is call in client.py
        files = [r["file"] for r in refs]
        self.assertTrue(any("service.py" in f for f in files))
        self.assertTrue(any("client.py" in f for f in files))

        # Look for verify_token callers
        v_refs = intel.find_symbol_references("verify_token")
        self.assertGreaterEqual(len(v_refs), 2)

    def test_repository_intelligence_list_all_symbols(self):
        """Tests that list_all_symbols extracts classes and methods."""
        intel = RepositoryIntelligence(str(self.workspace))
        symbols = intel.list_all_symbols()
        sym_names = [s["name"] for s in symbols]
        self.assertIn("AuthService", sym_names)
        self.assertIn("AuthService.authenticate", sym_names)
        self.assertIn("verify_token", sym_names)
        self.assertIn("run_client", sym_names)

    def test_find_symbol_references_tool_execution(self):
        """Tests tool execution of find_symbol_references through ToolExecutionEngine."""
        sec = SecurityEngine(workspace_root=str(self.workspace), auto_approve_all=True)
        db = TaskDatabase(str(self.workspace / "test.db"))
        try:
            engine = ToolExecutionEngine(sec, db, "test_task")
            success, output = engine.execute_tool("find_symbol_references", {"name": "verify_token"})
            self.assertTrue(success)
            self.assertIn("Found", output)
            self.assertIn("verify_token", output)
        finally:
            engine.subshell.close()
            db.close()

    def test_test_time_verifier_syntax_and_contract(self):
        """Tests that TestTimeVerifier catches invalid syntax and parameter drops."""
        verifier = TestTimeVerifier(self.workspace)
        
        # Valid patch
        ok, msg = verifier.verify_patch_safety(
            "test.py",
            "def foo(a, b): return a + b",
            "def foo(a, b, c=1): return a + b + c"
        )
        self.assertTrue(ok)

        # Invalid syntax patch
        bad_syntax_ok, bad_msg = verifier.verify_patch_safety(
            "test.py",
            "def foo(a, b): return a + b",
            "def foo(a, b: return a +"
        )
        self.assertFalse(bad_syntax_ok)
        self.assertIn("Syntax", bad_msg)

        # Breaking parameter drop
        drop_ok, drop_msg = verifier.verify_patch_safety(
            "test.py",
            "def authenticate(username, password, realm): pass",
            "def authenticate(username): pass"
        )
        self.assertFalse(drop_ok)
        self.assertIn("dropped parameters", drop_msg)

    def test_goal_supervisor_decomposition_and_persistence(self):
        """Tests GoalSupervisor milestone checklist and state management."""
        sup = GoalSupervisor(console=MagicMock())
        sup.workspace_root = self.workspace
        sup.goals_dir = self.workspace / ".prubeth" / "goals"
        sup.goals_dir.mkdir(parents=True, exist_ok=True)

        mock_resp = MagicMock()
        mock_resp.text = json.dumps([
            {"id": 1, "title": "Design JWT Schema", "description": "Create jwt.py", "verification_target": "syntax check"},
            {"id": 2, "title": "Implement JWT Auth", "description": "Integrate into service", "verification_target": "pytest"}
        ])

        with patch.object(sup.model_gw, "generate", return_value=mock_resp):
            milestones = sup.decompose_goal("Refactor auth system to use JWT tokens")
            self.assertEqual(len(milestones), 2)
            self.assertIsInstance(milestones[0], GoalMilestone)
            self.assertEqual(milestones[0].title, "Design JWT Schema")

        goal_data = {
            "id": "goal_test_001",
            "objective": "Refactor auth system to use JWT tokens",
            "status": "IN_PROGRESS",
            "milestones": [
                {"id": 1, "title": "M1", "description": "D1", "verification_target": "pytest", "status": "PENDING"},
                {"id": 2, "title": "M2", "description": "D2", "verification_target": "pytest", "status": "PENDING"}
            ]
        }
        sup.save_goal_state(goal_data)
        loaded = sup.load_goal_state("goal_test_001")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["objective"], "Refactor auth system to use JWT tokens")

        goals = sup.list_goals()
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["id"], "goal_test_001")

    def test_handle_learn_command(self):
        """Tests /learn command recording, listing, removing, and injecting."""
        # Use workspace directory
        with patch("pathlib.Path.cwd", return_value=self.workspace):
            # 1. Add directive
            handle_learn_command(["Always use snake_case for Python variables"])
            
            # Verify file exists
            learnings_file = self.workspace / ".prubeth" / "memory" / "learnings.json"
            self.assertTrue(learnings_file.exists())
            data = json.loads(learnings_file.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertIn("snake_case", data[0]["directive"])

            # 2. Add second directive
            handle_learn_command(["Never use bare except clauses"])
            data = json.loads(learnings_file.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 2)

            # 3. List
            handle_learn_command(["list"])

            # 4. Remove directive 1
            handle_learn_command(["remove", "1"])
            data = json.loads(learnings_file.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["id"], 2)

            # 5. Check RepositoryIntelligence picks up learnings
            intel = RepositoryIntelligence(str(self.workspace))
            instr = intel.load_project_instructions()
            self.assertIn("Never use bare except clauses", instr)

    def test_handle_commit_and_pr_commands(self):
        """Tests /commit and /pr command synthesis and artifact generation."""
        with patch("pathlib.Path.cwd", return_value=self.workspace):
            # Modify a file to create a diff
            self.service_file.write_text(
                "class AuthService:\n"
                "    def authenticate(self, username, password):\n"
                "        return username == 'admin' and password == 'secret'\n",
                encoding="utf-8"
            )

            # Mock gateway to avoid external API calls during unit test
            mock_resp = MagicMock()
            mock_resp.text = "feat(auth): enhance AuthService authentication logic\n\n- Validate password against secret."
            
            sample_diff = "--- a/src/service.py\n+++ b/src/service.py\n@@ -2,2 +2,2 @@\n- return username == 'admin'\n+ return username == 'admin' and password == 'secret'\n"
            with patch("prubeth.models.gateway.UniversalModelGateway.generate", return_value=mock_resp):
                handle_commit_command([], diff_override=sample_diff)
                commit_file = self.workspace / ".prubeth" / "commits" / "COMMIT_MSG.txt"
                self.assertTrue(commit_file.exists())
                self.assertIn("feat(auth)", commit_file.read_text(encoding="utf-8"))

                handle_pr_command([], diff_override=sample_diff)
                pr_file = self.workspace / ".prubeth" / "PULL_REQUEST.md"
                self.assertTrue(pr_file.exists())
                self.assertIn("feat(auth)", pr_file.read_text(encoding="utf-8"))

    def test_handle_symbols_and_callers_commands(self):
        """Tests /symbols and /callers command output handling."""
        mock_controller = MagicMock()
        mock_controller.workspace_root = self.workspace

        # Should execute without errors
        handle_symbols_command([], mock_controller)
        handle_callers_command(["AuthService"], mock_controller)
        handle_callers_command([], mock_controller)

if __name__ == "__main__":
    unittest.main()
