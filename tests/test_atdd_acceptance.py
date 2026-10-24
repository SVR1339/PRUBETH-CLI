import os
import sys
import unittest
import subprocess
from pathlib import Path

class TestATDDAcceptanceCriteria(unittest.TestCase):
    """Acceptance Test-Driven Development (ATDD): Developer CLI Acceptance Criteria Verification."""

    def run_cli(self, args, cwd=None):
        """Helper to invoke prubeth CLI via python module to test CLI interface directly."""
        cmd = [sys.executable, "-m", "prubeth.cli.main"] + args
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd or str(Path(__file__).parent.parent)
        )
        return proc

    def test_cli_help_acceptance(self):
        """CLI Acceptance: `prubeth --help` must display usage, arguments, and exit code 0."""
        proc = self.run_cli(["--help"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("PRUBETH Autonomous Developer CLI", proc.stdout)
        self.assertIn("--profile", proc.stdout)
        self.assertIn("--output-format", proc.stdout)

    def test_cli_settings_subcommands_acceptance(self):
        """CLI Acceptance: `prubeth settings` and `prubeth inspect`."""
        proc_list = self.run_cli(["settings"])
        self.assertEqual(proc_list.returncode, 0)
        self.assertIn("MASTER SETTINGS HUD", proc_list.stdout)
        self.assertIn("speculative_plan_b", proc_list.stdout)

        proc_inspect = self.run_cli(["inspect", "developer_mode"])
        self.assertEqual(proc_inspect.returncode, 0)
        self.assertIn("SETTING INSPECTOR", proc_inspect.stdout)
        self.assertIn("developer_mode", proc_inspect.stdout)

    def test_cli_config_list_acceptance(self):
        """CLI Acceptance: `prubeth config list` renders the configuration table."""
        proc = self.run_cli(["config", "list"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("PRUBETH Raw Configuration Matrix", proc.stdout)

    def test_cli_swarm_subcommands_acceptance(self):
        """CLI Acceptance: `prubeth swarm roles` displays all specialized swarm roles."""
        proc = self.run_cli(["swarm", "roles"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("architect", proc.stdout)
        self.assertIn("coder", proc.stdout)
        self.assertIn("critic", proc.stdout)
        self.assertIn("test_engineer", proc.stdout)
        self.assertIn("docs", proc.stdout)

    def test_cli_worktrees_subcommands_acceptance(self):
        """CLI Acceptance: `prubeth worktrees list` lists active shadow worktrees."""
        proc = self.run_cli(["worktrees", "list"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("PRUBETH Shadow Worktree Subsystem", proc.stdout)

    def test_cli_memory_subcommands_acceptance(self):
        """CLI Acceptance: `prubeth memory decisions` prints architectural decisions."""
        proc = self.run_cli(["memory", "decisions"])
        self.assertEqual(proc.returncode, 0)
        self.assertTrue("decisions" in proc.stdout.lower())

    def test_cli_consensus_subcommand_acceptance(self):
        """CLI Acceptance: `prubeth consensus` shows voting threshold and rules."""
        proc = self.run_cli(["consensus"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("PRUBETH Pre-Flight AST & Adversarial Consensus Gates", proc.stdout)

    def test_cli_mcp_subcommand_acceptance(self):
        """CLI Acceptance: `prubeth mcp list` displays registered MCP servers."""
        proc = self.run_cli(["mcp", "list"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Model Context Protocol (MCP) Registry", proc.stdout)

    def test_cli_status_flag_acceptance(self):
        """CLI Acceptance: `prubeth --status` displays the performance and settings dashboard."""
        proc = self.run_cli(["--status"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("MASTER SETTINGS HUD", proc.stdout)

if __name__ == "__main__":
    unittest.main()
