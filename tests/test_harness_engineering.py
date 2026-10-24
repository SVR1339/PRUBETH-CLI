import os
import unittest
import tempfile
from pathlib import Path
from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.runtime.controller import RuntimeConfig, AutonomousRuntimeController

class TestHarnessEngineering(unittest.TestCase):
    """Harness Engineering: Verifying the Deterministic Control System Enclosing Non-Deterministic Models."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        self.db = TaskDatabase(str(self.workspace / ".prubeth" / "harness.db"))
        self.sec = SecurityEngine(workspace_root=str(self.workspace), auto_approve_all=True)
        self.engine = ToolExecutionEngine(self.sec, self.db, "harness-task-1")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_harness_parameter_normalization(self):
        """Harness: Models alternate between 'path', 'file_path', and 'filepath'. Harness must normalize."""
        # 1. Write file with 'path'
        ok1, res1 = self.engine.execute_tool("write_file", {"path": "a.txt", "content": "alpha"})
        self.assertTrue(ok1)
        self.assertTrue((self.workspace / "a.txt").exists())

        # 2. Read file with 'file_path'
        ok2, res2 = self.engine.execute_tool("read_file", {"file_path": "a.txt"})
        self.assertTrue(ok2)
        self.assertIn("alpha", res2)

        # 3. Read file with 'filepath'
        ok3, res3 = self.engine.execute_tool("read_file", {"filepath": "a.txt"})
        self.assertTrue(ok3)
        self.assertIn("alpha", res3)

    def test_harness_large_output_truncation_safety(self):
        """Harness: Vast terminal outputs must be bounded to avoid blowing model context window."""
        huge_content = "X" * 100000
        ok, res = self.engine.execute_tool("write_file", {"path": "huge.txt", "content": huge_content})
        self.assertTrue(ok)

        # Reading with limit
        ok_read, read_res = self.engine.execute_tool("read_file", {"path": "huge.txt", "limit": 1000})
        self.assertTrue(ok_read)
        self.assertLessEqual(len(read_res), 1500)

    def test_harness_structured_edits_support(self):
        """Harness: Supports structured edits array format from modern reasoning models."""
        target_file = self.workspace / "script.py"
        target_file.write_text("print('hello')\n", encoding="utf-8")

        # Structured append edit
        ok, res = self.engine.execute_tool("edit_file", {
            "path": "script.py",
            "edits": [{"action": "append", "content": "print('world')\n"}]
        })
        self.assertTrue(ok)
        updated = target_file.read_text(encoding="utf-8")
        self.assertIn("print('hello')", updated)
        self.assertIn("print('world')", updated)

if __name__ == "__main__":
    unittest.main()
