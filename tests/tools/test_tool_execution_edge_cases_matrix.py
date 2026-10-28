"""PRUBETH Tool Execution Edge Cases, Verification & Security Resilience Matrix.

Exhaustively verifies:
1. PatchVerifierTool: dry-run patching, fuzzy matching, post-patch syntax validation.
2. LintCheckerTool: built-in AST diagnostics, syntax flaw detection across polyglot files.
3. TypeCheckerTool: static type signature coverage, strict enforcement, and partial annotation tracking.
4. CoverageAnalyserTool: JSON and report parser, threshold enforcement, uncovered line attribution.
5. SecurityLinterTool: leak detection across provider tokens, injection vectors, and severity filtering.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from prubeth.tools.verification.patch_verifier import PatchVerifierTool
from prubeth.tools.verification.lint_checker import LintCheckerTool
from prubeth.tools.verification.type_checker import TypeCheckerTool
from prubeth.tools.verification.coverage_analyser import CoverageAnalyserTool
from prubeth.tools.domain.security_linter import SecurityLinterTool


# ============================================================================
# 1. PatchVerifierTool Permutations (Exact, Fuzzy, Syntax Validation)
# ============================================================================

EXACT_PATCH_CASES = [
    ("python", "def calculate(a, b):\n    return a + b\n", "return a + b", "return a * b", True),
    ("python", "x = 10\ny = 20\n", "y = 20", "y = 30", True),
    ("python", "class Config:\n    TIMEOUT = 30\n", "TIMEOUT = 30", "TIMEOUT = 60", True),
    ("python", "async def fetch():\n    return None\n", "return None", "return {'status': 200}", True),
    ("python", "import os\n\ndef main(): pass\n", "import os", "import os\nimport sys", True),
    ("typescript", "const port: number = 3000;\n", "3000", "8080", True),
    ("typescript", "function greet(name: string): string {\n    return 'Hello ' + name;\n}\n", "'Hello '", "'Hi '", True),
    ("go", "package main\nfunc Add(a, b int) int { return a + b }\n", "return a + b", "return a - b", True),
    ("rust", "fn main() {\n    let val = 42;\n}\n", "let val = 42;", "let val = 100;", True),
    ("json", '{\n  "version": "1.0.0"\n}\n', '"1.0.0"', '"2.0.0"', True),
    ("yaml", "server:\n  port: 80\n", "port: 80", "port: 443", True),
    ("markdown", "# Header 1\nContent line\n", "Header 1", "Header 2", True),
    ("python", "def divide(a, b):\n    return a / b\n", "return a / b", "return a // b", True),
    ("python", "DATA = [1, 2, 3]\n", "[1, 2, 3]", "[1, 2, 3, 4, 5]", True),
    ("python", "MODE = 'dev'\n", "'dev'", "'prod'", True),
    ("typescript", "export interface User { id: string; }\n", "id: string;", "id: string; email: string;", True),
    ("go", "type Config struct { Host string }\n", "Host string", "Host, Port string", True),
    ("rust", "pub struct Point { x: i32 }\n", "x: i32", "x: i32, y: i32", True),
    ("python", "FLAG = False\n", "False", "True", True),
    ("python", "items = {'a': 1}\n", "{'a': 1}", "{'a': 1, 'b': 2}", True),
]

@pytest.mark.parametrize("lang,content,target,replacement,expected_success", EXACT_PATCH_CASES)
def test_patch_verifier_exact_matches(tmp_path, lang: str, content: str, target: str, replacement: str, expected_success: bool):
    ext_map = {"python": ".py", "typescript": ".ts", "go": ".go", "rust": ".rs", "json": ".json", "yaml": ".yaml", "markdown": ".md"}
    ext = ext_map.get(lang, ".txt")
    test_file = tmp_path / f"test_{lang}{ext}"
    test_file.write_text(content, encoding="utf-8")

    tool = PatchVerifierTool(workspace_root=tmp_path)
    res = tool.execute({"path": str(test_file), "target": target, "replacement": replacement})
    assert res.success is expected_success
    if expected_success:
        assert "Patch Verification PASSED" in res.output
        assert res.exit_code == 0


FUZZY_PATCH_CASES = [
    ("def run():\n    step1()\n    step2()\n", "    step1()\n    step2()", "    step1()\n    step2()\n    step3()"),
    ("class Worker:\n    def do_work(self):\n        pass\n", "    def do_work(self):\n        pass", "    def do_work(self):\n        return True"),
    ("if condition:\n    foo = 1\n", "if condition:\n    foo = 1", "if condition:\n    foo = 2"),
    ("def compute(a, b):\n    return a + b\n", "def compute(a, b):\n    return a + b", "def compute(a, b):\n    return a + b + 1"),
    ("def process():\n    return {'ok': True}\n", "def process():\n    return {'ok': True}", "def process():\n    return {'ok': False}"),
    ("for i in range(10):\n    print(i)\n", "for i in range(10):\n    print(i)", "for i in range(10):\n    print(i * 2)"),
    ("try:\n    risky()\nexcept Exception:\n    pass\n", "try:\n    risky()\nexcept Exception:\n    pass", "try:\n    risky()\nexcept Exception:\n    pass\n    return False"),
    ("with open('a.txt') as f:\n    data = f.read()\n", "with open('a.txt') as f:\n    data = f.read()", "with open('a.txt') as f:\n    data = f.read().strip()"),
    ("a = 1\nb = 2\n", "a = 1\nb = 2", "a = 10\nb = 20"),
    ("items = [1, 2, 3]\n", "items = [1, 2, 3]", "items = [1, 2, 3, 4]"),
    ("msg = 'hello world'\n", "msg = 'hello world'", "msg = 'hello prubeth'"),
    ("def ping():\n    return 'pong'\n", "def ping():\n    return 'pong'", "def ping():\n    return 'pong!'"),
    ("status = 200\n", "status = 200", "status = 204"),
    ("class App:\n    pass\n", "class App:\n    pass", "class App:\n    active = True"),
    ("x = 100\n", "x = 100", "x = 200"),
]

@pytest.mark.parametrize("content,target,replacement", FUZZY_PATCH_CASES)
def test_patch_verifier_fuzzy_matching(tmp_path, content: str, target: str, replacement: str):
    f = tmp_path / "fuzzy_sample.py"
    f.write_text(content, encoding="utf-8")

    tool = PatchVerifierTool(workspace_root=tmp_path)
    res = tool.execute({"path": str(f), "target": target, "replacement": replacement})
    assert res.success is True
    assert "Patch Verification PASSED" in res.output


SYNTAX_ERROR_POST_PATCH_CASES = [
    ("def valid():\n    return 42\n", "return 42", "return (unclosed paren"),
    ("x = 10\n", "x = 10", "x = if True: pass"),
    ("def hello():\n    pass\n", "pass", "def invalid syntax 123 !"),
    ("class A:\n    pass\n", "pass", "def broken(a, )::"),
    ("import os\n", "import os", "import = ="),
    ("y = [1, 2, 3]\n", "[1, 2, 3]", "[1, 2,"),
    ("d = {'a': 1}\n", "{'a': 1}", "{'a': 1"),
    ("z = 5\n", "z = 5", "z = 5 + * 2"),
    ("def test():\n    return True\n", "return True", "return True else False"),
    ("def foo():\n    x = 1\n", "x = 1", "x = 1;\n    for:"),
    ("a = 1\n", "a = 1", "while True"),
    ("b = 2\n", "b = 2", "try:\n    pass\nexcept: except:"),
    ("c = 3\n", "c = 3", "from os import * as foo"),
    ("d = 4\n", "d = 4", "def (*args): pass"),
    ("e = 5\n", "e = 5", "lambda x: for i in range(x):"),
]

@pytest.mark.parametrize("content,target,replacement", SYNTAX_ERROR_POST_PATCH_CASES)
def test_patch_verifier_detects_post_patch_syntax_error(tmp_path, content: str, target: str, replacement: str):
    f = tmp_path / "syntax_target.py"
    f.write_text(content, encoding="utf-8")

    tool = PatchVerifierTool(workspace_root=tmp_path)
    res = tool.execute({"path": str(f), "target": target, "replacement": replacement})
    assert res.success is False
    assert "SyntaxError in prospective patched code" in res.output or "Patch verification failed" in res.output


INVALID_PATCH_TARGET_CASES = [
    ("def func(): pass\n", "completely_unknown_token_xyz"),
    ("class S: pass\n", "def non_existent_method():"),
    ("import sys\n", "import nonexistent_package_symbol"),
    ("x = 100\n", "x = 999999"),
    ("return 'ok'\n", "return 'definitely_not_here'"),
    ("print('a')\n", "print('z_unknown')"),
    ("a = [1, 2]\n", "a = [9, 8, 7]"),
    ("b = {'k': 'v'}\n", "b = {'ghost': 42}"),
    ("c = True\n", "c = None_Unmatched"),
    ("async def a(): pass\n", "async def z_unmatched(): pass"),
]

@pytest.mark.parametrize("content,target", INVALID_PATCH_TARGET_CASES)
def test_patch_verifier_unmatched_target_fails(tmp_path, content: str, target: str):
    f = tmp_path / "unmatched.py"
    f.write_text(content, encoding="utf-8")

    tool = PatchVerifierTool(workspace_root=tmp_path)
    res = tool.execute({"path": str(f), "target": target, "replacement": "replacement"})
    assert res.success is False
    assert "Patch verification failed" in res.output


EMPTY_AND_MISSING_PATCH_ARGS = [
    ("", "target", "rep", "Missing file path"),
    ("ghost_file_123.py", "target", "rep", "not found"),
    ("some_file.py", "", "rep", "Target string cannot be empty"),
    ("ghost_file_456.py", "foo", "bar", "not found"),
    ("", "a", "b", "Missing file path"),
    ("missing_a.txt", "x", "y", "not found"),
    ("missing_b.txt", "m", "n", "not found"),
    ("missing_c.txt", "1", "2", "not found"),
    ("some_file2.py", "", "new", "Target string cannot be empty"),
    ("", "", "", "Missing file path"),
]

@pytest.mark.parametrize("path,target,replacement,expected_err", EMPTY_AND_MISSING_PATCH_ARGS)
def test_patch_verifier_missing_and_invalid_args(tmp_path, path: str, target: str, replacement: str, expected_err: str):
    resolved_path = str(tmp_path / path) if path else ""
    tool = PatchVerifierTool(workspace_root=tmp_path)
    res = tool.execute({"path": resolved_path, "target": target, "replacement": replacement})
    assert res.success is False
    assert expected_err.lower() in res.output.lower()


# ============================================================================
# 2. LintCheckerTool Permutations (AST Diagnostics, Polyglot Handling)
# ============================================================================

CLEAN_PYTHON_LINT_CASES = [
    "def add(a: int, b: int) -> int:\n    return a + b\n",
    "class Greeter:\n    def greet(self) -> str:\n        return 'hello'\n",
    "import math\n\ndef circle_area(radius: float) -> float:\n    return math.pi * radius ** 2\n",
    "async def fetch_data() -> dict:\n    return {'status': 200}\n",
    "DATA = [i * 2 for i in range(10)]\n",
    "CONSTANT: int = 42\n",
    "from typing import List, Optional\ndef process(items: List[str]) -> Optional[str]:\n    return items[0] if items else None\n",
    "try:\n    x = 1 / 1\nexcept ZeroDivisionError:\n    x = 0\n",
    "with open(__file__, 'r') as f:\n    pass\n",
    "def factorial(n: int) -> int:\n    return 1 if n <= 1 else n * factorial(n - 1)\n",
]

@pytest.mark.parametrize("code", CLEAN_PYTHON_LINT_CASES)
def test_lint_checker_ast_clean_python(tmp_path, code: str):
    f = tmp_path / "clean.py"
    f.write_text(code, encoding="utf-8")

    tool = LintCheckerTool()
    res = tool.execute({"path": str(f), "linter": "ast"})
    assert res.success is True
    assert "Found 0 issues" in res.output or "clean" in res.output.lower()


SYNTAX_ERROR_PYTHON_LINT_CASES = [
    ("def broken(\n", "unexpected EOF"),
    ("x = [1, 2,\n", "was never closed"),
    ("if True\n    pass\n", "expected ':'"),
    ("class\n", "invalid syntax"),
    ("def bad():\nreturn 1\n", "expected an indented block"),
    ("import\n", "invalid syntax"),
    ("a = 1 + *\n", "invalid syntax"),
    ("def bad_op():\n    return 1 + / 2\n", "invalid syntax"),
    ("print 'hello'\n", "Missing parentheses"),
    ("for in range(5):\n    pass\n", "invalid syntax"),
]

@pytest.mark.parametrize("code,expected_err", SYNTAX_ERROR_PYTHON_LINT_CASES)
def test_lint_checker_ast_catches_syntax_flaws(tmp_path, code: str, expected_err: str):
    f = tmp_path / "broken.py"
    f.write_text(code, encoding="utf-8")

    tool = LintCheckerTool()
    res = tool.execute({"path": str(f), "linter": "ast"})
    assert res.success is False
    assert res.exit_code != 0
    assert "Syntax error" in res.output or "Error" in res.output


NON_PYTHON_LINT_FALLBACK_CASES = [
    ("service.ts", "const x: number = 42;\n"),
    ("main.go", "package main\nfunc main() {}\n"),
    ("lib.rs", "pub fn ping() -> bool { true }\n"),
    ("data.json", '{"name": "test", "valid": true}\n'),
    ("README.md", "# Documentation\nPRUBETH CLI\n"),
]

@pytest.mark.parametrize("filename,content", NON_PYTHON_LINT_FALLBACK_CASES)
def test_lint_checker_non_python_fallback(tmp_path, filename: str, content: str):
    f = tmp_path / filename
    f.write_text(content, encoding="utf-8")

    tool = LintCheckerTool()
    res = tool.execute({"path": str(f), "linter": "ast"})
    assert res.success is True


MISSING_OR_INVALID_LINT_PATHS = [
    ("", "Missing target path to lint"),
    ("ghost_dir/ghost_file.py", "does not exist"),
    ("nonexistent_folder_abc", "does not exist"),
    ("missing_script.py", "does not exist"),
    ("   ", "Missing target path to lint"),
]

@pytest.mark.parametrize("path,expected_err", MISSING_OR_INVALID_LINT_PATHS)
def test_lint_checker_missing_and_invalid_paths(tmp_path, path: str, expected_err: str):
    resolved = str(tmp_path / path) if path.strip() else ""
    tool = LintCheckerTool()
    res = tool.execute({"path": resolved, "linter": "ast"})
    assert res.success is False
    assert expected_err.lower() in res.output.lower()


# ============================================================================
# 3. TypeCheckerTool Permutations (AST Type Signature Analysis)
# ============================================================================

FULLY_ANNOTATED_PYTHON_CASES = [
    "def add(a: int, b: int) -> int:\n    return a + b\n",
    "def greet(name: str) -> str:\n    return f'Hello {name}'\n",
    "def is_positive(num: float) -> bool:\n    return num > 0.0\n",
    "def identity(val: any) -> any:\n    return val\n",
    "def get_items() -> list[str]:\n    return ['a', 'b']\n",
    "def get_map() -> dict[str, int]:\n    return {'a': 1}\n",
    "def noop() -> None:\n    pass\n",
    "def combine(x: int, y: str) -> tuple[int, str]:\n    return (x, y)\n",
    "def compute(flag: bool) -> int:\n    return 1 if flag else 0\n",
    "def calc(val: int) -> float:\n    return float(val)\n",
]

@pytest.mark.parametrize("code", FULLY_ANNOTATED_PYTHON_CASES)
def test_type_checker_fully_annotated(tmp_path, code: str):
    f = tmp_path / "typed.py"
    f.write_text(code, encoding="utf-8")

    tool = TypeCheckerTool()
    res = tool.execute({"path": str(f), "engine": "ast", "strict": True})
    assert res.success is True
    assert "Type Annotation Coverage: 100.0%" in res.output


UNANNOTATED_STRICT_VS_RELAXED_CASES = [
    ("def unannotated_add(a, b):\n    return a + b\n", False, True),
    ("def unannotated_add(a, b):\n    return a + b\n", True, False),
    ("def get_val():\n    return 42\n", False, True),
    ("def get_val():\n    return 42\n", True, False),
    ("def echo(x):\n    return x\n", False, True),
    ("def echo(x):\n    return x\n", True, False),
    ("def run(cmd):\n    pass\n", False, True),
    ("def run(cmd):\n    pass\n", True, False),
    ("def check(flag):\n    return not flag\n", False, True),
    ("def check(flag):\n    return not flag\n", True, False),
    ("def sum_all(*args):\n    return sum(args)\n", False, True),
    ("def sum_all(*args):\n    return sum(args)\n", True, False),
    ("def config(**kwargs):\n    return kwargs\n", False, True),
    ("def config(**kwargs):\n    return kwargs\n", True, False),
    ("def calc(a, b, c):\n    return (a + b) * c\n", False, True),
]

@pytest.mark.parametrize("code,strict,expected_success", UNANNOTATED_STRICT_VS_RELAXED_CASES)
def test_type_checker_strict_vs_relaxed(tmp_path, code: str, strict: bool, expected_success: bool):
    f = tmp_path / "partially_typed.py"
    f.write_text(code, encoding="utf-8")

    tool = TypeCheckerTool()
    res = tool.execute({"path": str(f), "engine": "ast", "strict": strict})
    assert res.success is expected_success


DIRECTORY_TYPE_SCAN_CASES = [
    (["def f1() -> int: return 1", "def f2() -> str: return 's'"], 100.0),
    (["def f1(a: int) -> int: return a", "def f2(b): return b"], 50.0),
    (["def f1(): pass", "def f2(): pass", "def f3(): pass"], 0.0),
    (["def f1() -> None: pass", "def f2() -> None: pass", "def f3(): pass", "def f4(): pass"], 50.0),
    (["def a(x: int) -> int: return x", "def b(y: float) -> float: return y", "def c(z: str) -> str: return z"], 100.0),
    (["def f1(): pass"], 0.0),
    (["def f1() -> bool: return True"], 100.0),
    (["def a(x: int) -> int: return x", "def b(): pass"], 50.0),
    (["def f1() -> int: return 1", "def f2() -> int: return 2", "def f3(): pass"], 66.7),
    (["def a(): pass", "def b(): pass", "def c(): pass", "def d() -> int: return 4"], 25.0),
]

@pytest.mark.parametrize("funcs,expected_pct", DIRECTORY_TYPE_SCAN_CASES)
def test_type_checker_directory_scan(tmp_path, funcs: list[str], expected_pct: float):
    pkg_dir = tmp_path / "scan_pkg"
    pkg_dir.mkdir(exist_ok=True)
    for idx, fn in enumerate(funcs):
        (pkg_dir / f"mod_{idx}.py").write_text(f"{fn}\n", encoding="utf-8")

    tool = TypeCheckerTool()
    res = tool.execute({"path": str(pkg_dir), "engine": "ast", "strict": False})
    assert res.success is True
    assert "Type Annotation Coverage:" in res.output


MISSING_OR_INVALID_TYPE_PATHS = [
    ("", "Missing target path"),
    ("missing_type_file.py", "does not exist"),
    ("missing_dir_xyz", "does not exist"),
    ("invalid_path/sub/nonexistent.py", "does not exist"),
    ("   ", "Missing target path"),
]

@pytest.mark.parametrize("path,expected_err", MISSING_OR_INVALID_TYPE_PATHS)
def test_type_checker_missing_and_invalid_paths(tmp_path, path: str, expected_err: str):
    resolved = str(tmp_path / path) if path.strip() else ""
    tool = TypeCheckerTool()
    res = tool.execute({"path": resolved, "engine": "ast"})
    assert res.success is False
    assert expected_err.lower() in res.output.lower()


# ============================================================================
# 4. CoverageAnalyserTool Permutations (JSON Report Parsing & Thresholds)
# ============================================================================

COVERAGE_REPORT_PARSER_CASES = [
    (100.0, 80.0, True),
    (95.5, 90.0, True),
    (88.0, 80.0, True),
    (80.0, 80.0, True),
    (79.9, 80.0, False),
    (50.0, 60.0, False),
    (0.0, 50.0, False),
    (100.0, 100.0, True),
    (99.0, 100.0, False),
    (75.0, 0.0, True),
]

@pytest.mark.parametrize("actual_pct,min_threshold,expected_success", COVERAGE_REPORT_PARSER_CASES)
def test_coverage_analyser_report_parser(tmp_path, actual_pct: float, min_threshold: float, expected_success: bool):
    rep_file = tmp_path / "coverage.json"
    rep_data = {
        "totals": {
            "percent_covered": actual_pct,
            "covered_lines": int(actual_pct),
            "num_statements": 100,
            "missing_lines": 100 - int(actual_pct),
        },
        "files": {
            "src/module.py": {
                "summary": {"percent_covered": actual_pct},
                "missing_lines": [i for i in range(1, 101 - int(actual_pct))],
            }
        }
    }
    rep_file.write_text(json.dumps(rep_data), encoding="utf-8")

    tool = CoverageAnalyserTool()
    res = tool.execute({"report_file": str(rep_file), "min_coverage": min_threshold})
    assert res.success is expected_success
    assert f"{actual_pct:.1f}%" in res.output or f"{actual_pct}" in res.output


COVERAGE_MISSING_LINES_EXTRACTION = [
    ([10, 11, 12], 3),
    ([1, 2, 3, 4, 5], 5),
    ([42], 1),
    ([], 0),
    ([100, 101, 102, 103, 104, 105, 106], 7),
]

@pytest.mark.parametrize("missing_lines,count", COVERAGE_MISSING_LINES_EXTRACTION)
def test_coverage_analyser_missing_lines(tmp_path, missing_lines: list[int], count: int):
    rep_file = tmp_path / "coverage_missing.json"
    rep_data = {
        "totals": {"percent_covered": 85.0},
        "files": {
            "src/service.py": {
                "summary": {"percent_covered": 85.0},
                "missing_lines": missing_lines,
            }
        }
    }
    rep_file.write_text(json.dumps(rep_data), encoding="utf-8")

    tool = CoverageAnalyserTool()
    res = tool.execute({"report_file": str(rep_file), "min_coverage": 0.0})
    assert res.success is True
    assert "Total Coverage: 85.0%" in res.output


# ============================================================================
# 5. SecurityLinterTool Permutations (Token Leak & Injection Vectors)
# ============================================================================

SECRET_DETECTION_CASES = [
    ("google_key", 'api_key = "AIzaSyD-1234567890abcdefghijklmnopqrstuv"', "Google Cloud / Firebase API Key"),
    ("openai_key", 'token = "sk-abcdefghijklmnopqrstuvwxyz1234567890"', "OpenAI / Anthropic Secret Key"),
    ("github_pat", 'gh = "ghp_123456789012345678901234567890123456"', "GitHub Personal Access Token"),
    ("aws_key", 'aws = "AKIA1234567890ABCDEF"', "AWS Access Key ID"),
    ("generic_secret", 'secret = "my_super_secret_production_password_token_123456"', "Hardcoded Secret / Token"),
    ("api_key_assign", 'apikey: "abcdefghijklmnopqrstuvwxyz123456"', "Hardcoded Secret / Token"),
    ("token_assign", 'token = "xyz1234567890abcdefghijklmnopqrstuvw"', "Hardcoded Secret / Token"),
    ("password_assign", 'password = "supersecretpassword1234567890"', "Hardcoded Secret / Token"),
    ("openai_proj", 'key = "sk-proj-1234567890abcdefghijklmnopqrstuvw"', "OpenAI / Anthropic Secret Key"),
    ("google_alt", 'google_key = "AIzaSyABCDEF1234567890abcdefghijklmnopqr"', "Google Cloud / Firebase API Key"),
    ("github_token", 'pat = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"', "GitHub Personal Access Token"),
    ("aws_alt", 'aws_key = "AKIAABCDEFGHIJKLMNOP"', "AWS Access Key ID"),
    ("auth_secret", 'auth_secret = "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"', "Hardcoded Secret / Token"),
    ("db_password", 'db_password = "productiondatabasepasswordverysecure123"', "Hardcoded Secret / Token"),
    ("jwt_secret", 'jwt_secret = "jwtsecretkeythatisatleasttwentyfivecharacters"', "Hardcoded Secret / Token"),
]

@pytest.mark.parametrize("label,secret_line,expected_pattern_name", SECRET_DETECTION_CASES)
def test_security_linter_detects_secrets(tmp_path, label: str, secret_line: str, expected_pattern_name: str):
    f = tmp_path / f"leak_{label}.py"
    f.write_text(f"# Leak sample\n{secret_line}\n", encoding="utf-8")

    tool = SecurityLinterTool()
    res = tool.execute({"path": str(f), "min_severity": "LOW"})
    assert res.success is False
    assert expected_pattern_name in res.output or "Issues Found:" in res.output


INSECURE_CONSTRUCT_CASES = [
    ("eval_usage", "eval(user_input)", "Dangerous eval() usage", False),
    ("exec_usage", "exec(arbitrary_code)", "Dangerous exec() usage", False),
    ("subprocess_shell", "subprocess.run(user_cmd, shell=True)", "Subprocess shell=True injection risk", True),
    ("subprocess_call", "subprocess.call(arg, shell=True)", "Subprocess shell=True injection risk", True),
    ("md5_hash", "hashlib.md5(data.encode())", "Weak cryptographic hash (MD5/SHA1)", True),
    ("sha1_hash", "hashlib.sha1(data.encode())", "Weak cryptographic hash (MD5/SHA1)", True),
    ("sql_percent", 'query = "SELECT * FROM users WHERE id = %s" % user_id', "Potential SQL string formatting injection", False),
    ("sql_fstring", 'query = f"DELETE FROM accounts WHERE name = \'{account_name}\'"', "Potential SQL f-string injection", False),
    ("eval_multiline", "data = eval(raw_json)", "Dangerous eval() usage", False),
    ("exec_multiline", "exec(script_payload)", "Dangerous exec() usage", False),
    ("sql_insert_fstring", 'q = f"INSERT INTO logs VALUES (\'{entry}\')"', "Potential SQL f-string injection", False),
    ("sql_update_fmt", 'sql = "UPDATE settings SET val = %d" % new_val', "Potential SQL string formatting injection", False),
    ("subprocess_popen", "subprocess.Popen(cmd, shell=True)", "Subprocess shell=True injection risk", True),
    ("eval_nested", "result = parse(eval(untrusted))", "Dangerous eval() usage", False),
    ("exec_nested", "sandbox.run(exec(code_block))", "Dangerous exec() usage", False),
]

@pytest.mark.parametrize("label,code_line,expected_flaw,expected_success", INSECURE_CONSTRUCT_CASES)
def test_security_linter_detects_insecure_constructs(tmp_path, label: str, code_line: str, expected_flaw: str, expected_success: bool):
    f = tmp_path / f"insecure_{label}.py"
    f.write_text(f"# Insecure code\n{code_line}\n", encoding="utf-8")

    tool = SecurityLinterTool()
    res = tool.execute({"path": str(f), "min_severity": "LOW"})
    assert res.success is expected_success
    assert expected_flaw in res.output


SEVERITY_FILTERING_CASES = [
    ("md5", "import hashlib\nx = hashlib.md5(b'test')", "CRITICAL", True),  # LOW severity ignored when min=CRITICAL
    ("md5", "import hashlib\nx = hashlib.md5(b'test')", "HIGH", True),      # LOW severity ignored when min=HIGH
    ("md5", "import hashlib\nx = hashlib.md5(b'test')", "LOW", True),       # LOW severity caught, but has_critical is False -> res.success is True
    ("eval", "eval(untrusted)", "CRITICAL", True),                          # HIGH severity ignored when min=CRITICAL
    ("eval", "eval(untrusted)", "HIGH", False),                              # HIGH severity caught and has_critical is True -> res.success is False
    ("eval", "eval(untrusted)", "LOW", False),                               # HIGH severity caught and has_critical is True -> res.success is False
    ("openai_key", 'k = "sk-abcdefghijklmnopqrstuvwxyz1234567890"', "CRITICAL", False), # CRITICAL caught on CRITICAL
    ("openai_key", 'k = "sk-abcdefghijklmnopqrstuvwxyz1234567890"', "HIGH", False),     # CRITICAL caught on HIGH
    ("openai_key", 'k = "sk-abcdefghijklmnopqrstuvwxyz1234567890"', "LOW", False),      # CRITICAL caught on LOW
    ("shell_true", "subprocess.run(c, shell=True)", "HIGH", True),          # MEDIUM ignored when min=HIGH
]

@pytest.mark.parametrize("flaw_kind,code_line,min_sev,expected_success", SEVERITY_FILTERING_CASES)
def test_security_linter_severity_threshold_filtering(tmp_path, flaw_kind: str, code_line: str, min_sev: str, expected_success: bool):
    f = tmp_path / f"sev_{flaw_kind}.py"
    f.write_text(f"{code_line}\n", encoding="utf-8")

    tool = SecurityLinterTool()
    res = tool.execute({"path": str(f), "min_severity": min_sev})
    assert res.success is expected_success


CLEAN_SECURITY_REPO_CASES = [
    "def safe_add(a: int, b: int) -> int:\n    return a + b\n",
    "import json\ndata = json.loads('{\"key\": \"value\"}')\n",
    "import subprocess\nsubprocess.run(['git', 'status'])\n",
    "import hashlib\nhashlib.sha256(b'secure').hexdigest()\n",
    "class User:\n    def __init__(self, name: str):\n        self.name = name\n",
]

@pytest.mark.parametrize("code", CLEAN_SECURITY_REPO_CASES)
def test_security_linter_clean_code_passes(tmp_path, code: str):
    f = tmp_path / "clean_secure.py"
    f.write_text(code, encoding="utf-8")

    tool = SecurityLinterTool()
    res = tool.execute({"path": str(f), "min_severity": "LOW"})
    assert res.success is True
    assert "Issues Found:  0" in res.output
