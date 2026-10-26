"""Unit & Invariant Verification Suite for PRUBETH APEX Edition (v1.1.0).

Tests:
1. Pure-Python BM25 Codebase Index & Symbol Graph (CodebaseIndex)
2. Smart Inline Context Expansion & @mentions Resolver (ContextExpander)
3. Autonomous Auto-TDD Self-Healing Engine & Rollback Gate (AutoHealer)
4. Live Cockpit Telemetry HUD & Token Cost Radar (hud.py)
5. Time-Travel Conversation Branching & Rollback Tree (ConversationTree)
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Prioritize local src over globally installed site-packages
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rich.console import Console

from prubeth.repository.index import CodebaseIndex, CodeSymbol, SearchResult
from prubeth.repository.context import ContextExpander
from prubeth.runtime.auto_heal import AutoHealer
from prubeth.cli.hud import calculate_session_spend, render_cockpit_hud_bar, render_cost_report
from prubeth.persistence.tree import ConversationTree, ConversationNode
from prubeth.models.telemetry import LLMOpsMonitor
from prubeth.config.manager import ConfigManager

class TestApexPerfection(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace = Path(self.test_dir)
        LLMOpsMonitor().reset()

        # Create dummy workspace files
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        self.auth_file = self.workspace / "src" / "auth.py"
        self.auth_file.write_text(
            'class UserAuthenticator:\n'
            '    """Handles user JWT authentication and validation."""\n'
            '    def authenticate(self, username, password):\n'
            '        if username == "admin" and password == "secret":\n'
            '            return True\n'
            '        return False\n\n'
            'def hash_password(raw_pwd):\n'
            '    return f"hashed_{raw_pwd}"\n',
            encoding="utf-8"
        )

        self.test_file = self.workspace / "tests" / "test_auth.py"
        self.test_file.parent.mkdir(parents=True, exist_ok=True)
        self.test_file.write_text(
            'from src.auth import UserAuthenticator\n'
            'def test_auth():\n'
            '    auth = UserAuthenticator()\n'
            '    assert auth.authenticate("admin", "secret") is True\n',
            encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # Pillar 1: Codebase BM25 Semantic Index & Symbol Graph
    # -------------------------------------------------------------
    def test_bm25_index_and_symbol_extraction(self):
        idx = CodebaseIndex(workspace_root=self.workspace)
        indexed_count = idx.index_workspace()
        self.assertGreaterEqual(indexed_count, 2)

        # 1. Symbol lookup
        sym_class = idx.resolve_symbol("UserAuthenticator")
        self.assertIsNotNone(sym_class)
        self.assertEqual(sym_class.kind, "class")
        self.assertIn("class UserAuthenticator", sym_class.signature)
        self.assertIn("Handles user JWT", sym_class.docstring or "")

        sym_method = idx.resolve_symbol("authenticate")
        self.assertIsNotNone(sym_method)
        self.assertIn("authenticate", sym_method.signature)

        sym_func = idx.resolve_symbol("hash_password")
        self.assertIsNotNone(sym_func)
        self.assertEqual(sym_func.kind, "function")

        # 2. BM25 Search
        results = idx.search("JWT authentication password", top_k=2)
        self.assertTrue(len(results) > 0)
        top = results[0]
        self.assertIn("auth.py", top.file_path)
        self.assertGreater(top.score, 0.0)

    # -------------------------------------------------------------
    # Pillar 2: Context @mentions Expander
    # -------------------------------------------------------------
    def test_context_expander_file_and_symbol_mentions(self):
        expander = ContextExpander(workspace_root=self.workspace)

        # @file mention
        prompt = "Review @src/auth.py and check for security issues"
        expanded, attachments = expander.resolve_mentions(prompt)
        self.assertIn("UserAuthenticator", expanded)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["type"], "file")
        self.assertIn("src/auth.py", attachments[0]["label"])

        # @symbol mention
        prompt_sym = "Explain how @sym:UserAuthenticator works"
        expanded_sym, attachments_sym = expander.resolve_mentions(prompt_sym)
        self.assertEqual(len(attachments_sym), 1)
        self.assertEqual(attachments_sym[0]["type"], "symbol")
        self.assertIn("UserAuthenticator", expanded_sym)

        # @diff mention
        prompt_diff = "Summarize @diff"
        expanded_diff, attachments_diff = expander.resolve_mentions(prompt_diff)
        self.assertEqual(len(attachments_diff), 1)
        self.assertEqual(attachments_diff[0]["type"], "diff")

    # -------------------------------------------------------------
    # Pillar 3: Auto-TDD Self-Healing Engine
    # -------------------------------------------------------------
    def test_auto_healer_success_baseline(self):
        console = Console(record=True, width=140, legacy_windows=False)
        healer = AutoHealer(workspace_root=self.workspace, console=console)

        # Mock run_command to succeed
        with patch.object(healer, "run_command", return_value=(0, "All tests passed", "")):
            result = healer.heal("pytest tests/")
            self.assertTrue(result["success"])
            self.assertFalse(result["healed"])
            self.assertEqual(result["attempts"], 0)

    def test_auto_healer_recovers_from_failure(self):
        console = Console(record=True, width=140, legacy_windows=False)
        healer = AutoHealer(workspace_root=self.workspace, console=console)

        # Create broken file
        broken_file = self.workspace / "src" / "math_util.py"
        broken_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

        mock_runs = [
            (1, "", 'File "src/math_util.py", line 2, in add\nAssertionError: expected 5 got -1'),  # baseline run
            (0, "All tests passed cleanly", "")  # re-run after patch
        ]
        mock_response = MagicMock()
        mock_response.text = (
            '{\n'
            '  "root_cause": "add function subtracted instead of adding",\n'
            '  "file_path": "src/math_util.py",\n'
            '  "find_str": "return a - b",\n'
            '  "replace_str": "return a + b"\n'
            '}'
        )

        with patch.object(healer, "run_command", side_effect=mock_runs), \
             patch.object(healer.gateway, "generate", return_value=mock_response):
            result = healer.heal("pytest")
            self.assertTrue(result["success"])
            self.assertTrue(result["healed"])
            self.assertEqual(result["attempts"], 1)
            # Verify file on disk was patched
            content = broken_file.read_text(encoding="utf-8")
            self.assertEqual(content.strip(), "def add(a, b):\n    return a + b")

    # -------------------------------------------------------------
    # Pillar 4: Live Cockpit Status HUD & Token Cost Radar
    # -------------------------------------------------------------
    def test_cockpit_hud_and_cost_radar(self):
        monitor = LLMOpsMonitor()
        monitor.record_call(
            model="gemini-3.1-pro-preview",
            provider="google",
            latency_s=0.45,
            input_tokens=10_000,
            output_tokens=2_000,
            cached_tokens=8_000,
            success=True
        )
        monitor.record_call(
            model="gemini-3.8-flash",
            provider="google",
            latency_s=0.15,
            input_tokens=5_000,
            output_tokens=500,
            cached_tokens=0,
            success=True
        )

        spend = calculate_session_spend()
        self.assertEqual(spend["total_calls"], 2)
        self.assertEqual(spend["total_tokens"], 17_500)
        self.assertGreater(spend["total_cost_usd"], 0.0)

        # Test rendering without crashing
        console = Console(record=True, width=140, legacy_windows=False)
        render_cost_report(console)
        output = console.export_text()
        self.assertIn("gemini-3.1-pro-preview", output)
        self.assertIn("gemini-3.8-flash", output)

        cfg_mgr = ConfigManager()
        render_cockpit_hud_bar(console, cfg_mgr)
        hud_output = console.export_text()
        self.assertIn("Model:", hud_output)
        self.assertIn("RAM:", hud_output)

    # -------------------------------------------------------------
    # Pillar 5: Conversation Time-Travel Tree & Forking
    # -------------------------------------------------------------
    def test_conversation_tree_branching_and_rewind(self):
        tree_dir = self.workspace / ".prubeth" / "history"
        tree = ConversationTree(storage_dir=tree_dir)

        # Add turns
        t1 = tree.add_turn("Create login endpoint", "Created auth.py", snapshot_id="snap_001")
        t2 = tree.add_turn("Add JWT signing", "Added jwt tokens", snapshot_id="snap_002")
        self.assertEqual(t1, "turn_001")
        self.assertEqual(t2, "turn_002")
        self.assertEqual(tree.head_turn_id, "turn_002")

        # Fork new branch
        new_branch = tree.fork("oauth_experiment")
        self.assertEqual(new_branch, "oauth_experiment")
        self.assertEqual(tree.current_branch, "oauth_experiment")

        t3 = tree.add_turn("Implement GitHub OAuth", "OAuth added", snapshot_id="snap_003")
        self.assertEqual(t3, "turn_003")

        # Switch back to main
        self.assertTrue(tree.switch_branch("main"))
        self.assertEqual(tree.head_turn_id, "turn_002")

        # Rewind to turn_001
        ok, snap = tree.rewind("turn_001")
        self.assertTrue(ok)
        self.assertEqual(snap, "snap_001")
        self.assertEqual(tree.head_turn_id, "turn_001")

        # Visual Table render
        table = tree.render_history_table()
        self.assertIsNotNone(table)

if __name__ == "__main__":
    unittest.main()
