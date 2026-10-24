import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from prubeth.cli.commands import (
    handle_swarm_command,
    handle_worktrees_command,
    handle_memory_command,
    handle_bridge_command,
    handle_consensus_command
)
from prubeth.persistence.memory import MemoryVault
from prubeth.agents.worktree import WorktreeManager

class TestCLICommands(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.test_dir)
        self.mem_dir = self.workspace_root / ".prubeth" / "memory"
        self.mem_vault = MemoryVault(self.mem_dir)
        self.wt_mgr = WorktreeManager(self.workspace_root)

        self.mock_controller = MagicMock()
        self.mock_controller.workspace_root = self.workspace_root
        self.mock_controller.memory_vault = self.mem_vault
        self.mock_controller.ide_bridge = MagicMock()
        self.mock_controller.ide_bridge.running = True
        self.mock_controller.ide_bridge.client_count = 1

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_swarm_roles_and_list(self):
        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_swarm_command(["roles"], self.mock_controller)
            self.assertTrue(mock_print.called)

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_swarm_command(["list"], self.mock_controller)
            self.assertTrue(mock_print.called)

    def test_worktrees_list_and_clean(self):
        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_worktrees_command(["list"], self.mock_controller)
            self.assertTrue(mock_print.called)

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_worktrees_command(["clean"], self.mock_controller)
            self.assertTrue(mock_print.called)

    def test_memory_commands(self):
        self.mem_vault.record_anti_pattern(
            failing_component="TestRunner",
            error_symptom="Timeout in worker",
            root_cause="Missing timeout parameter",
            prevention_rule="Always configure socket timeouts"
        )
        self.mem_vault.record_decision(
            decision_title="Adopt SE 3.0 Invariants",
            rationale="Eliminates non-deterministic agent regressions",
            affected_modules=["runtime", "agents"]
        )

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_memory_command(["summary"], self.mock_controller)
            self.assertTrue(mock_print.called)

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_memory_command(["anti-patterns"], self.mock_controller)
            self.assertTrue(mock_print.called)

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_memory_command(["decisions"], self.mock_controller)
            self.assertTrue(mock_print.called)

    def test_bridge_command_status(self):
        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_bridge_command(["status"], self.mock_controller)
            self.assertTrue(mock_print.called)

    def test_consensus_command(self):
        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_consensus_command([], self.mock_controller)
            self.assertTrue(mock_print.called)

if __name__ == "__main__":
    unittest.main()
