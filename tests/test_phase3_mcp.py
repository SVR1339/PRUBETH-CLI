import unittest
from unittest.mock import MagicMock, patch
import json
import tempfile
import shutil
from pathlib import Path

from prubeth.mcp.protocol import MCPRequest, MCPResponse, MCPTool, MCPResource
from prubeth.mcp.manager import MCPManager
from prubeth.mcp.client import MCPClient
from prubeth.cli.commands import handle_mcp_command
from prubeth.evaluation.benchmark import AutonomousBenchmarkRunner

class TestPhase3MCPAndEvaluation(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.test_dir)
        self.mcp_config = self.workspace_root / ".prubeth" / "mcp.json"
        self.mcp_mgr = MCPManager(self.workspace_root, self.mcp_config)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_mcp_protocol_dataclasses(self):
        req = MCPRequest(id=42, method="tools/list", params={"filter": "all"})
        d = req.to_dict()
        self.assertEqual(d["jsonrpc"], "2.0")
        self.assertEqual(d["id"], 42)
        self.assertEqual(d["method"], "tools/list")

        raw_resp = {
            "jsonrpc": "2.0",
            "id": 42,
            "result": {"tools": [{"name": "query_db", "description": "Execute SQL"}]}
        }
        resp = MCPResponse.from_dict(raw_resp)
        self.assertEqual(resp.id, 42)
        self.assertIsNone(resp.error)
        self.assertIn("tools", resp.result)

    def test_mcp_manager_register_and_list(self):
        self.mcp_mgr.register_server("sqlite", "mcp-sqlite", ["--db", "test.db"])
        servers = self.mcp_mgr.list_servers()
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]["name"], "sqlite")
        self.assertEqual(servers[0]["command"], "mcp-sqlite")

        # Mock tool discovery on client
        client = self.mcp_mgr.servers["sqlite"]
        client.tools = [
            MCPTool(name="read_query", description="Reads from database")
        ]
        tools = self.mcp_mgr.get_all_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "mcp_sqlite_read_query")
        self.assertEqual(tools[0]["server"], "sqlite")

    def test_mcp_command_cli_handlers(self):
        mock_controller = MagicMock()
        mock_controller.mcp = self.mcp_mgr

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_mcp_command(["list"], mock_controller)
            self.assertTrue(mock_print.called)

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_mcp_command(["add", "github", "npx", "-y", "@modelcontextprotocol/server-github"], mock_controller)
            self.assertTrue(mock_print.called)

        self.assertIn("github", self.mcp_mgr.servers)

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_mcp_command(["remove", "github"], mock_controller)
            self.assertTrue(mock_print.called)

        self.assertNotIn("github", self.mcp_mgr.servers)

    def test_autonomous_benchmark_runner(self):
        runner = AutonomousBenchmarkRunner(controller=None)
        tasks = [
            {"name": "Add Fibonacci Function", "goal": "Write fib(n) in math.py"},
            {"name": "Fix ZeroDivisionError", "goal": "Guard against division by zero"}
        ]
        report = runner.run_benchmark(tasks)
        self.assertEqual(report.total_tasks, 2)
        self.assertEqual(report.completed_tasks, 2)
        self.assertEqual(report.autonomy_quotient, 100.0)
        self.assertGreaterEqual(report.average_latency_s, 0.0)

if __name__ == "__main__":
    unittest.main()
