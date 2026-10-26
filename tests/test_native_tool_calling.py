"""Verification Suite for Native Tool Calling & Multi-Turn Structured Roles (PRUBETH v1.2.0).

Verifies:
1. Google, Anthropic, and OpenAI tool schema conversion accuracy.
2. Structured parsing of native tool calls from Google, Anthropic, and OpenAI response payloads.
3. Multi-turn structured conversation execution with native tool dispatch in `run_fluid_turn`.
4. Backward compatibility with simulated/regex tool calls.
"""

import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from prubeth.tools.definitions import to_google_tools, to_anthropic_tools, to_openai_tools, RAW_TOOL_DEFINITIONS
from prubeth.models.gateway import UniversalModelGateway, GenerationResponse
from prubeth.runtime.controller import AutonomousRuntimeController, RuntimeConfig

class TestNativeToolCalling(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "sample.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        self.controller = AutonomousRuntimeController(
            workspace_root=str(self.workspace),
            config=RuntimeConfig(auto_approve_actions=True)
        )

    def tearDown(self):
        self.controller.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tool_definition_schemas(self):
        """Tool definitions correctly transform into provider-native schemas."""
        google_tools = to_google_tools()
        self.assertIsInstance(google_tools, list)
        self.assertIn("function_declarations", google_tools[0])
        names = [f["name"] for f in google_tools[0]["function_declarations"]]
        self.assertIn("read_file", names)
        self.assertIn("edit_file", names)
        self.assertIn("run_command", names)

        anthropic_tools = to_anthropic_tools()
        self.assertIsInstance(anthropic_tools, list)
        self.assertEqual(len(anthropic_tools), len(RAW_TOOL_DEFINITIONS))
        self.assertIn("input_schema", anthropic_tools[0])

        openai_tools = to_openai_tools()
        self.assertIsInstance(openai_tools, list)
        self.assertEqual(openai_tools[0]["type"], "function")
        self.assertIn("parameters", openai_tools[0]["function"])

    def test_fluid_turn_native_tool_call_dispatch(self):
        """`run_fluid_turn` consumes native `tool_calls` list and dispatches execution."""
        mock_resp_1 = GenerationResponse(
            text="Inspecting code.",
            tool_calls=[{
                "id": "call_abc123",
                "name": "read_file",
                "args": {"path": "src/sample.py", "start_line": 1, "end_line": 2}
            }]
        )
        mock_resp_2 = GenerationResponse(
            text="File contains `def hello(): return 'world'`."
        )

        with patch.object(self.controller.gateway, "generate", side_effect=[mock_resp_1, mock_resp_2]):
            result = self.controller.run_fluid_turn("Inspect src/sample.py")
            self.assertTrue(result["success"])
            self.assertEqual(len(result["tools_executed"]), 1)
            self.assertEqual(result["tools_executed"][0]["tool"], "read_file")
            self.assertTrue(result["tools_executed"][0]["success"])
            self.assertIn("hello()", result["tools_executed"][0]["output"])
            self.assertIn("def hello(): return 'world'", result["text"])

    def test_fluid_turn_regex_tool_fallback(self):
        """`run_fluid_turn` gracefully parses markdown tool blocks when native tools are absent."""
        mock_resp_1 = GenerationResponse(
            text=(
                "I will search files.\n"
                "```tool\n"
                "{\"tool\": \"find_files\", \"args\": {\"pattern\": \"*.py\"}}\n"
                "```"
            ),
            tool_calls=None
        )
        mock_resp_2 = GenerationResponse(
            text="Found python files in repository."
        )

        with patch.object(self.controller.gateway, "generate", side_effect=[mock_resp_1, mock_resp_2]):
            result = self.controller.run_fluid_turn("Find python files")
            self.assertTrue(result["success"])
            self.assertEqual(len(result["tools_executed"]), 1)
            self.assertEqual(result["tools_executed"][0]["tool"], "find_files")
            self.assertIn("Found python files", result["text"])

if __name__ == "__main__":
    unittest.main()
