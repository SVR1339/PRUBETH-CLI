"""PRUBETH Polyglot Syntax Gate Matrix Tests.

Exhaustively verifies Pre-Flight Invariant & Syntax Gate (Subsystem 17) across 15+
languages: Python, JSON/JSONC, JS/TS, Rust, Go, C/C++, Java, C#, Kotlin, Dart,
PHP, Ruby, YAML, TOML, Markdown, and SQL.
"""

from __future__ import annotations

import pytest
from prubeth.verification.polyglot import PolyglotSyntaxGate


# ============================================================================
# 1. Python AST Validation Matrix
# ============================================================================

def test_python_valid_ast():
    code = (
        "def compute_total(items: list[int]) -> int:\n"
        "    return sum(items)\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("src/main.py", code)
    assert ok is True
    assert "successful" in msg


def test_python_syntax_error_detected():
    code = "def broken(x:\n    return x + 1\n"
    ok, msg = PolyglotSyntaxGate.validate_content("src/calc.py", code)
    assert ok is False
    assert "Python SyntaxError" in msg


def test_python_empty_file():
    ok, msg = PolyglotSyntaxGate.validate_content("src/__init__.py", "")
    assert ok is True


# ============================================================================
# 2. JSON & JSONC Validation Matrix
# ============================================================================

def test_json_valid():
    code = '{"name": "prubeth", "version": "2.0.0", "active": true, "ports": [80, 443]}'
    ok, msg = PolyglotSyntaxGate.validate_content("package.json", code)
    assert ok is True
    assert "JSON parsed successfully" in msg


def test_json_with_comments_stripped_jsonc():
    code = (
        "{\n"
        "  // Config section\n"
        '  "mode": "autonomous",\n'
        '  "threads": 4\n'
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("tsconfig.jsonc", code)
    assert ok is True


def test_json_invalid_trailing_comma():
    code = '{"a": 1, "b": 2,}'
    ok, msg = PolyglotSyntaxGate.validate_content("data.json", code)
    assert ok is False
    assert "JSONDecodeError" in msg


def test_json_unclosed_brace():
    code = '{"open": "value"'
    ok, msg = PolyglotSyntaxGate.validate_content("config.json", code)
    assert ok is False
    assert "JSONDecodeError" in msg


# ============================================================================
# 3. JavaScript & TypeScript Validation Matrix
# ============================================================================

@pytest.mark.parametrize("ext", [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"])
def test_js_ts_valid_delimiters(ext: str):
    code = (
        "export function processPayload(data: Array<any>): Promise<void> {\n"
        "  const formatted = data.map((item) => ({ id: item.id, score: item.score * 10 }));\n"
        "  return Promise.resolve();\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content(f"src/service{ext}", code)
    assert ok is True
    assert "invariants validated" in msg


def test_js_ts_unmatched_closing_brace():
    code = "function test() { return 42; }}"
    ok, msg = PolyglotSyntaxGate.validate_content("index.ts", code)
    assert ok is False
    assert "Unmatched closing '}'" in msg


def test_js_ts_mismatched_delimiters():
    code = "const items = (1, 2, 3];"
    ok, msg = PolyglotSyntaxGate.validate_content("index.js", code)
    assert ok is False
    assert "Mismatched closing ']'" in msg


def test_js_ts_unclosed_template_literal():
    code = "const str = `unclosed template literal;\nconst x = 10;"
    ok, msg = PolyglotSyntaxGate.validate_content("app.tsx", code)
    assert ok is False
    assert "Unterminated template literal" in msg


def test_js_ts_unclosed_block_comment():
    code = "/* unclosed comment\nconst x = 10;\n"
    ok, msg = PolyglotSyntaxGate.validate_content("app.ts", code)
    assert ok is False
    assert "Unterminated block comment" in msg


# ============================================================================
# 4. Rust Validation Matrix
# ============================================================================

def test_rust_valid_with_lifetimes_and_char_literals():
    code = (
        "pub struct Buffer<'a> {\n"
        "    data: &'a [u8],\n"
        "    delimiter: char,\n"
        "}\n\n"
        "impl<'a> Buffer<'a> {\n"
        "    pub fn new(slice: &'a [u8]) -> Self {\n"
        "        Self { data: slice, delimiter: '\\n' }\n"
        "    }\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("src/lib.rs", code)
    assert ok is True
    assert "Rust delimiter invariants validated" in msg


def test_rust_unclosed_brace():
    code = "fn main() { println!(\"Hello\");"
    ok, msg = PolyglotSyntaxGate.validate_content("src/main.rs", code)
    assert ok is False
    assert "Rust SyntaxError" in msg
    assert "Unclosed delimiter '{'" in msg


# ============================================================================
# 5. Go Validation Matrix
# ============================================================================

def test_go_valid_package_and_syntax():
    code = (
        "package main\n\n"
        "import \"fmt\"\n\n"
        "func main() {\n"
        "    fmt.Println(\"PRUBETH Go Runtime\")\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("main.go", code)
    assert ok is True
    assert "Go delimiter invariants validated" in msg


def test_go_missing_package_declaration():
    code = (
        "import \"fmt\"\n\n"
        "func helper() {}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("helper.go", code)
    assert ok is False
    assert "Missing required 'package <name>' declaration" in msg


def test_go_unmatched_bracket():
    code = (
        "package main\n\n"
        "func process(vals []int) {\n"
        "    vals = append(vals, 10))\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("pkg/proc.go", code)
    assert ok is False
    assert "Mismatched closing ')'" in msg


# ============================================================================
# 6. C and C++ Validation Matrix
# ============================================================================

@pytest.mark.parametrize("ext", [".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"])
def test_c_cpp_valid_structure(ext: str):
    code = (
        "#include <stdio.h>\n"
        "#include <stdlib.h>\n\n"
        "typedef struct {\n"
        "    int id;\n"
        "    char *name;\n"
        "} Item;\n\n"
        "int main(void) {\n"
        "    /* allocate item */\n"
        "    Item *i = (Item*)malloc(sizeof(Item));\n"
        "    free(i);\n"
        "    return 0;\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content(f"src/core{ext}", code)
    assert ok is True
    assert "C/C++ delimiter invariants validated" in msg


def test_c_cpp_unclosed_block_comment():
    code = (
        "/* beginning of block comment\n"
        "int x = 42;\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("src/main.cpp", code)
    assert ok is False
    assert "Unterminated block comment" in msg


# ============================================================================
# 7. Java, C#, and Kotlin Validation Matrix
# ============================================================================

@pytest.mark.parametrize("ext", [".java", ".cs", ".kt", ".kts"])
def test_java_csharp_kotlin_valid(ext: str):
    code = (
        "public class EnterpriseBridge {\n"
        "    private final List<String> records = new ArrayList<>();\n\n"
        "    public void addRecord(String rec) {\n"
        "        records.add(rec);\n"
        "    }\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content(f"src/Bridge{ext}", code)
    assert ok is True
    assert "Java/C# delimiter invariants validated" in msg


def test_java_unclosed_brace():
    code = "public class A { void run() {}"
    ok, msg = PolyglotSyntaxGate.validate_content("A.java", code)
    assert ok is False
    assert "Unclosed delimiter '{'" in msg


# ============================================================================
# 8. Dart Validation Matrix
# ============================================================================

def test_dart_valid_structure():
    code = (
        "class CounterWidget {\n"
        "  final int count;\n"
        "  const CounterWidget({required this.count});\n\n"
        "  List<int> getValues() => [1, 2, count];\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("lib/widget.dart", code)
    assert ok is True
    assert "Dart delimiter invariants validated" in msg


def test_dart_mismatched_brackets():
    code = "final list = [1, 2, 3);"
    ok, msg = PolyglotSyntaxGate.validate_content("lib/util.dart", code)
    assert ok is False
    assert "Mismatched closing ')'" in msg


# ============================================================================
# 9. PHP Validation Matrix
# ============================================================================

def test_php_valid():
    code = (
        "<?php\n\n"
        "namespace App\\Controllers;\n\n"
        "class HomeController {\n"
        "    public function index(): array {\n"
        "        return ['status' => 200, 'message' => 'ok'];\n"
        "    }\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("app/HomeController.php", code)
    assert ok is True
    assert "PHP delimiter invariants validated" in msg


def test_php_missing_opening_tag():
    code = (
        "class BrokenController {\n"
        "    public function test() {}\n"
        "}\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("app/Broken.php", code)
    assert ok is False
    assert "Missing opening '<?php' tag" in msg


# ============================================================================
# 10. Ruby Validation Matrix
# ============================================================================

def test_ruby_valid_blocks():
    code = (
        "module Analytics\n"
        "  class Tracker\n"
        "    def track(event_name)\n"
        "      puts \"Tracking: #{event_name}\"\n"
        "    end\n"
        "  end\n"
        "end\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("lib/tracker.rb", code)
    assert ok is True
    assert "Ruby structural invariants validated" in msg


def test_ruby_missing_end():
    code = (
        "class Incomplete\n"
        "  def run\n"
        "    puts 'hello'\n"
        "end\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("lib/broken.rb", code)
    assert ok is False
    assert "Missing 'end' statement" in msg


def test_ruby_negative_block_depth():
    code = (
        "def test\n"
        "  42\n"
        "end\n"
        "end\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("lib/negative.rb", code)
    assert ok is False
    assert "Unexpected 'end' statement" in msg


# ============================================================================
# 11. YAML, TOML, Markdown, and SQL Validation Matrix
# ============================================================================

def test_yaml_valid_spaces():
    code = (
        "name: prubeth-ci\n"
        "stages:\n"
        "  - build\n"
        "  - test\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("ci.yaml", code)
    assert ok is True
    assert "YAML structural invariants validated" in msg


def test_yaml_tab_rejection():
    code = "services:\n\tweb:\n\t\timage: nginx\n"
    ok, msg = PolyglotSyntaxGate.validate_content("docker-compose.yml", code)
    assert ok is False
    assert "Tab characters used in indentation" in msg


def test_toml_valid():
    code = (
        "[project]\n"
        "name = \"prubeth\"\n"
        "version = \"2.0.0\"\n\n"
        "[project.dependencies]\n"
        "rich = \">=13.0.0\"\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("pyproject.toml", code)
    assert ok is True
    assert "TOML structural invariants validated" in msg


def test_toml_unclosed_header():
    code = "[broken_section\nkey = 'val'\n"
    ok, msg = PolyglotSyntaxGate.validate_content("config.toml", code)
    assert ok is False
    assert "Unclosed section header" in msg


def test_markdown_balanced_code_fences():
    code = (
        "# Title\n\n"
        "```python\n"
        "print('hello')\n"
        "```\n\n"
        "```bash\n"
        "pytest\n"
        "```\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("DOCS.md", code)
    assert ok is True
    assert "Markdown structural invariants validated" in msg


def test_markdown_odd_code_fence_count():
    code = (
        "# Title\n\n"
        "```python\n"
        "print('hello')\n"
    )
    ok, msg = PolyglotSyntaxGate.validate_content("README.markdown", code)
    assert ok is False
    assert "Unclosed code fence" in msg


def test_sql_valid():
    code = "SELECT id, name, email FROM users WHERE active = 1 ORDER BY created_at DESC;"
    ok, msg = PolyglotSyntaxGate.validate_content("schema.sql", code)
    assert ok is True
    assert "SQL structural invariants validated" in msg


def test_sql_unclosed_block_comment():
    code = "/* unclosed comment\nSELECT * FROM orders;"
    ok, msg = PolyglotSyntaxGate.validate_content("query.sql", code)
    assert ok is False
    assert "Unclosed block comment" in msg


# ============================================================================
# 12. Pragma Bypasses & Relaxed Developer Clearance
# ============================================================================

@pytest.mark.parametrize("pragma", [
    "# prubeth: allow-syntax-error",
    "// prubeth: allow-syntax-error",
    "/* prubeth: allow-syntax-error */",
    "# prubeth: no-gate",
    "// prubeth: relaxed",
    "# prubeth: force-syntax",
    "# noqa: syntax",
])
def test_pragma_bypass_allows_broken_syntax(pragma: str):
    code = f"{pragma}\ndef broken(:\n    pass\n"
    ok, msg = PolyglotSyntaxGate.validate_content("broken.py", code)
    assert ok is True
    assert "bypassed via developer pragma" in msg


def test_relaxed_mode_validates_clean_python():
    code = "def valid(): return 1\n"
    ok, msg = PolyglotSyntaxGate.validate_content("relaxed.py", code, relaxed=True)
    assert ok is True
    assert "successful" in msg


def test_relaxed_mode_returns_notice_on_broken_python():
    code = "def broken(:\n    pass\n"
    ok, msg = PolyglotSyntaxGate.validate_content("broken.py", code, relaxed=True)
    assert ok is False
    assert "Relaxed Python AST notice" in msg


def test_unrestricted_file_type():
    ok, msg = PolyglotSyntaxGate.validate_content("data.csv", "id,name,value\n1,alpha,100\n")
    assert ok is True
    assert "No syntax restrictions" in msg
