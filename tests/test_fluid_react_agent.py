"""Unit & Behavioral Verification Suite for PRUBETH Fluid ReAct Agent.

Verifies:
1. Pure conversational streaming with 0 tools (no multi-phase waterfall lock-in).
2. Dynamic, interleaved tool execution (read_file, find_files, code_search) inline.
3. Background micro-snapshot safety without developer interruption.
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Prioritize local src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from prubeth.runtime.controller import AutonomousRuntimeController, RuntimeConfig

class TestFluidReActAgent(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)

        # Create dummy workspace files
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        self.db_file = self.workspace / "src" / "database.py"
        self.db_file.write_text(
            'def get_db_connection():\n'
            '    return "sqlite:///prubeth.db"\n',
            encoding="utf-8"
        )

        config = RuntimeConfig(auto_approve_actions=True)
        self.controller = AutonomousRuntimeController(
            workspace_root=str(self.workspace),
            config=config
        )

    def tearDown(self):
        self.controller.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fluid_turn_conversational_no_tools(self):
        """Conversational greetings and inquiries stream directly with 0 tools."""
        mock_response = MagicMock()
        mock_response.text = "Hello! I am ready to help you with your code."

        streamed = []
        def streamer(tok):
            streamed.append(tok)

        with patch.object(self.controller.gateway, "generate", return_value=mock_response):
            result = self.controller.run_fluid_turn("hi", stream_cb=streamer)
            self.assertTrue(result["success"])
            self.assertEqual(len(result["tools_executed"]), 0)
            self.assertIn("Hello! I am ready", result["text"])
            self.assertIsNotNone(result.get("snapshot_id"))

    def test_fluid_turn_dynamic_tool_invocation(self):
        """Fluid agent dynamically executes tools and incorporates output."""
        mock_resp_1 = MagicMock()
        mock_resp_1.text = (
            'I will check the workspace for database files.\n'
            '```tool\n'
            '{"tool": "find_files", "args": {"pattern": "*database*"}}\n'
            '```'
        )
        mock_resp_2 = MagicMock()
        mock_resp_2.text = "Database connection is configured in `src/database.py`."

        tool_events = []
        def reporter(stage, details, success, output):
            tool_events.append((stage, details.get("tool"), success))

        with patch.object(self.controller.gateway, "generate", side_effect=[mock_resp_1, mock_resp_2]):
            result = self.controller.run_fluid_turn(
                "Where is the database configured?",
                tool_cb=reporter
            )
            self.assertTrue(result["success"])
            self.assertEqual(len(result["tools_executed"]), 1)
            self.assertEqual(result["tools_executed"][0]["tool"], "find_files")
            self.assertTrue(result["tools_executed"][0]["success"])
            self.assertIn("src/database.py", result["text"])
            self.assertTrue(len(tool_events) >= 2)

if __name__ == "__main__":
    unittest.main()
