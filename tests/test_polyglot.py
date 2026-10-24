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

if __name__ == "__main__":
    unittest.main()
