import unittest
import tempfile
import shutil
from pathlib import Path

from prubeth.verification.polyglot import PolyglotSyntaxGate
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase

class TestPolyglotSyntaxGate(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.test_dir)
        self.db = TaskDatabase(str(self.workspace_root / "test.db"))
        self.security = SecurityEngine(workspace_root=str(self.workspace_root), auto_approve_all=True)
        self.tool_engine = ToolExecutionEngine(self.security, self.db, "task_polyglot")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_python_ast_validation(self):
        valid_py = "def add(a: int, b: int) -> int:\n    return a + b\n"
        ok, msg = PolyglotSyntaxGate.validate_content("calc.py", valid_py)
        self.assertTrue(ok)

        invalid_py = "def broken(:\n    return 42\n"
        ok, msg = PolyglotSyntaxGate.validate_content("broken.py", invalid_py)
        self.assertFalse(ok)
        self.assertIn("SyntaxError", msg)

    def test_json_validation(self):
        valid_json = '{"name": "prubeth", "version": 1, "enabled": true}'
        ok, _ = PolyglotSyntaxGate.validate_content("config.json", valid_json)
        self.assertTrue(ok)

        invalid_json = '{"name": "prubeth", "version": 1, trailing_comma: true,}'
        ok, msg = PolyglotSyntaxGate.validate_content("config.json", invalid_json)
        self.assertFalse(ok)
        self.assertIn("JSONDecodeError", msg)

    def test_javascript_typescript_delimiter_balance(self):
        valid_js = """
        function calculateTotal(items) {
            const mapped = items.map(x => ({ id: x.id, val: x.val * 2 }));
            return mapped.reduce((acc, curr) => acc + curr.val, 0);
        }
        """
        ok, _ = PolyglotSyntaxGate.validate_content("calc.ts", valid_js)
        self.assertTrue(ok)

        # Unmatched closing brace
        unmatched_closing = "function broken() { return [1, 2, 3]; }}"
        ok, msg = PolyglotSyntaxGate.validate_content("app.js", unmatched_closing)
        self.assertFalse(ok)
        self.assertIn("Unmatched closing '}'", msg)

        # Mismatched bracket
        mismatched = "const arr = [1, 2, 3);"
        ok, msg = PolyglotSyntaxGate.validate_content("app.js", mismatched)
        self.assertFalse(ok)
        self.assertIn("Mismatched closing", msg)

        # Unclosed delimiter
        unclosed = "function test() { const x = 10;"
        ok, msg = PolyglotSyntaxGate.validate_content("app.js", unclosed)
        self.assertFalse(ok)
        self.assertIn("Unclosed delimiter", msg)

    def test_yaml_tab_rejection(self):
        invalid_yaml = "version: 1\nservices:\n\tweb:\n\t\timage: nginx"
        ok, msg = PolyglotSyntaxGate.validate_content("docker-compose.yaml", invalid_yaml)
        self.assertFalse(ok)
        self.assertIn("Tab characters used in indentation", msg)

    def test_markdown_fence_balance(self):
        valid_md = "# Title\n```python\nprint(1)\n```\n"
        ok, _ = PolyglotSyntaxGate.validate_content("README.md", valid_md)
        self.assertTrue(ok)

        invalid_md = "# Title\n```python\nprint(1)\n"
        ok, msg = PolyglotSyntaxGate.validate_content("README.md", invalid_md)
        self.assertFalse(ok)
        self.assertIn("Unclosed code fence", msg)

    def test_tool_execution_engine_rejects_bad_syntax(self):
        bad_code = "def syntax_err(\n"
        ok, err = self.tool_engine.execute_tool("write_file", {"path": "bad.py", "content": bad_code})
        self.assertFalse(ok)
        self.assertIn("Pre-Flight Syntax Invariant Failed", err)

    def test_rust_and_go_validation(self):
        valid_rs = "fn main() {\n    let msg = \"Hello\";\n    println!(\"{}\", msg);\n}\n"
        ok, _ = PolyglotSyntaxGate.validate_content("main.rs", valid_rs)
        self.assertTrue(ok)

        unclosed_rs = "fn main() { let x = 5;"
        ok, msg = PolyglotSyntaxGate.validate_content("main.rs", unclosed_rs)
        self.assertFalse(ok)
        self.assertIn("Unclosed delimiter", msg)

        valid_go = "package main\n\nimport \"fmt\"\n\nfunc main() {\n    fmt.Println(\"Go\")\n}\n"
        ok, _ = PolyglotSyntaxGate.validate_content("main.go", valid_go)
        self.assertTrue(ok)

        missing_pkg_go = "func broken() {}"
        ok, msg = PolyglotSyntaxGate.validate_content("main.go", missing_pkg_go)
        self.assertFalse(ok)
        self.assertIn("Missing required 'package <name>'", msg)

    def test_polyglot_language_manager_and_stacks(self):
        from prubeth.polyglot.manager import PolyglotLanguageManager
        from prubeth.polyglot.stacks import SUPPORTED_STACKS, get_stack_by_id
        from prubeth.config.manager import ConfigManager

        cfg_mgr = ConfigManager(self.workspace_root / ".prubeth")
        mgr = PolyglotLanguageManager(self.workspace_root, cfg_mgr)

        # Default is auto
        self.assertEqual(mgr.get_configured_language(), "auto")

        # Explicitly switch to rust
        ok, msg = mgr.set_default_language("rust")
        self.assertTrue(ok)
        self.assertEqual(mgr.get_configured_language(), "rust")
        resolved = mgr.resolve_active_stack()
        self.assertEqual(resolved.id, "rust")
        self.assertEqual(resolved.default_test_cmd, "cargo test")

        # Switch back to auto
        ok, _ = mgr.set_default_language("auto")
        self.assertTrue(ok)
        self.assertEqual(mgr.get_configured_language(), "auto")

        # Verify stacks list
        all_stacks = mgr.list_all_stacks()
        self.assertGreaterEqual(len(all_stacks), 12)

    def test_fuzzy_patch_engine_robustness(self):
        # 1. Setup a file with target code
        original = "def compute(val: int) -> int:\n    res = val * 2  \n    return res\n"
        self.tool_engine.execute_tool("write_file", {"path": "algo.py", "content": original})

        # 2. Target has trailing whitespace drift: "    res = val * 2" (no trailing spaces)
        drifted_target = "    res = val * 2"
        replacement = "    res = val * 4"
        ok, msg = self.tool_engine.execute_tool("edit_file", {
            "path": "algo.py",
            "target": drifted_target,
            "replacement": replacement
        })
        self.assertTrue(ok, f"Fuzzy patch failed: {msg}")

        # Check edited file
        ok, new_code = self.tool_engine.execute_tool("read_file", {"path": "algo.py"})
        self.assertIn("val * 4", new_code)

    def test_handle_language_command(self):
        from unittest.mock import patch
        from prubeth.cli.commands import handle_language_command
        mock_controller = unittest.mock.MagicMock()
        mock_controller.workspace_root = self.workspace_root

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_language_command(["status"], mock_controller)
            self.assertTrue(mock_print.called)

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_language_command(["list"], mock_controller)
            self.assertTrue(mock_print.called)

        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_language_command(["set", "typescript"], mock_controller)
            self.assertTrue(mock_print.called)
            # Restore auto so subsequent test suites remain completely isolated
            handle_language_command(["set", "auto"], mock_controller)

if __name__ == "__main__":
    unittest.main()
