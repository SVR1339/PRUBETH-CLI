"""PRUBETH Polyglot Syntax Gate Exhaustive Permutations Matrix.

Tests every syntax gate invariant across all 15+ supported file extensions and languages,
including delimiter balancing, nesting permutations, comment/string escape masking,
Ruby block depth, Go package rules, PHP tags, TOML headers, Markdown fences,
and developer pragma overrides.
"""

from __future__ import annotations

import pytest
from prubeth.verification.polyglot import PolyglotSyntaxGate

ALL_DELIMITED_EXTS = [
    (".js", "JS/TS"),
    (".jsx", "JS/TS"),
    (".ts", "JS/TS"),
    (".tsx", "JS/TS"),
    (".mjs", "JS/TS"),
    (".cjs", "JS/TS"),
    (".c", "C/C++"),
    (".cpp", "C/C++"),
    (".cc", "C/C++"),
    (".cxx", "C/C++"),
    (".h", "C/C++"),
    (".hpp", "C/C++"),
    (".java", "Java/C#"),
    (".kt", "Java/C#"),
    (".kts", "Java/C#"),
    (".cs", "Java/C#"),
    (".dart", "Dart"),
]

VALID_BRACKET_SNIPPETS = [
    "function test() { return (1 + 2) * [3, 4][0]; }",
    "let a = { b: [1, 2, (3 + 4)], c: { d: true } };",
    "class Node { constructor() { this.items = []; } }",
    "void compute() { int x = (5 + (3 * (2 - 1))); }",
    "/* comment with unmatched ( [ { */ int ok = 1;",
    "// single line comment with ( { [ \nint ok2 = 2;",
    'const s = "string with unmatched ( { [ and \\" escapes";',
]

INVALID_BRACKET_SNIPPETS = [
    ("function broken() { return (1 + 2;", "Unclosed delimiter"),
    ("function broken() { return [1, 2, 3;", "Unclosed delimiter"),
    ("function broken() { if (true) { return 1; ", "Unclosed delimiter"),
    ("function broken() { return 1; } }", "Unmatched closing '}'"),
    ("function broken() { return (1 + 2]; }", "Mismatched closing ']'"),
    ("function broken() { return [1 + 2); }", "Mismatched closing ')'"),
    ("function broken() { return {1 + 2]; }", "Mismatched closing ']'"),
]


# ============================================================================
# 1. Delimited Source Languages Exhaustive Matrix
# ============================================================================

@pytest.mark.parametrize("ext,lang_name", ALL_DELIMITED_EXTS)
@pytest.mark.parametrize("snippet", VALID_BRACKET_SNIPPETS)
def test_delimited_source_valid_snippets(ext: str, lang_name: str, snippet: str):
    path = f"src/module/sample{ext}"
    ok, msg = PolyglotSyntaxGate.validate_content(path, snippet)
    assert ok is True, f"Failed for {ext} on snippet: {snippet}. Msg: {msg}"
    assert "invariants validated" in msg or "successful" in msg or "No syntax restrictions" in msg


@pytest.mark.parametrize("ext,lang_name", ALL_DELIMITED_EXTS)
@pytest.mark.parametrize("snippet,expected_err", INVALID_BRACKET_SNIPPETS)
def test_delimited_source_invalid_snippets(ext: str, lang_name: str, snippet: str, expected_err: str):
    path = f"src/module/broken{ext}"
    ok, msg = PolyglotSyntaxGate.validate_content(path, snippet)
    assert ok is False, f"Expected failure for {ext} on snippet: {snippet}"
    assert expected_err in msg


# ============================================================================
# 2. Unterminated Block Comments & Strings Across Delimited Languages
# ============================================================================

@pytest.mark.parametrize("ext,lang_name", ALL_DELIMITED_EXTS)
def test_delimited_source_unclosed_block_comment(ext: str, lang_name: str):
    snippet = "/* start of unclosed block comment\nint x = 10;\n"
    ok, msg = PolyglotSyntaxGate.validate_content(f"test{ext}", snippet)
    assert ok is False
    assert "Unterminated block comment" in msg


@pytest.mark.parametrize("ext,lang_name", ALL_DELIMITED_EXTS)
def test_delimited_source_unclosed_string_literal(ext: str, lang_name: str):
    snippet = 'const message = "unclosed string without end\nlet next = 1;'
    ok, msg = PolyglotSyntaxGate.validate_content(f"test{ext}", snippet)
    assert ok is False
    assert "Unterminated string literal" in msg


# ============================================================================
# 3. Rust Invariants Permutations Matrix
# ============================================================================

@pytest.mark.parametrize("snippet", [
    "fn main() { println!(\"Hello, world!\"); }",
    "pub struct Buffer<'a> { data: &'a [u8] }",
    "fn lifetime<'a, 'b>(x: &'a str, y: &'b str) -> &'a str { x }",
    "let c: char = 'x'; let d: char = '\\n';",
    "fn calc() -> i32 { (10 + 20) * [1, 2, 3][0] }",
    "const RAW: &str = r#\"hello world\"#;",
])
def test_rust_valid_snippets(snippet: str):
    ok, msg = PolyglotSyntaxGate.validate_content("src/main.rs", snippet)
    assert ok is True
    assert "Rust" in msg


@pytest.mark.parametrize("snippet,expected", [
    ("fn main() { println!(\"Hello\"); ", "Unclosed delimiter '{'"),
    ("fn main() { return (1 + 2; }", "Mismatched closing '}'"),
    ("fn main() { (1 + 2", "Unclosed delimiter"),
    ("fn main() { return 1; }}", "Unmatched closing '}'"),
    ("fn main() { let x = (10 + 2]; }", "Mismatched closing ']'"),
    ("/* unclosed rust block comment\nfn test() {}", "Unterminated block comment"),
])
def test_rust_invalid_snippets(snippet: str, expected: str):
    ok, msg = PolyglotSyntaxGate.validate_content("src/main.rs", snippet)
    assert ok is False
    assert expected in msg


# ============================================================================
# 4. Go Language Permutations Matrix
# ============================================================================

@pytest.mark.parametrize("pkg_decl", [
    "package main\n\nfunc main() {}",
    "package prubeth\n\ntype Engine struct {}",
    "package server\n\nfunc Serve(port int) error { return nil }",
    "  package   custom_pkg  \n\nfunc Run() {}",
])
def test_go_valid_package_declarations(pkg_decl: str):
    ok, msg = PolyglotSyntaxGate.validate_content("pkg/engine/engine.go", pkg_decl)
    assert ok is True
    assert "Go" in msg


@pytest.mark.parametrize("broken_go,expected", [
    ("func main() { fmt.Println(\"No package!\") }", "Missing required 'package <name>' declaration"),
    ("// only comments\nvar x = 10", "Missing required 'package <name>' declaration"),
    ("package main\nfunc broken() { return (10 + 2 }", "Mismatched closing '}'"),
    ("package main\nfunc broken() { (10 + 2", "Unclosed delimiter"),
    ("package main\nfunc broken() { return 1; }}", "Unmatched closing '}'"),
    ("package main\nfunc broken() { return [1, 2); }", "Mismatched closing ')'"),
])
def test_go_invalid_snippets(broken_go: str, expected: str):
    ok, msg = PolyglotSyntaxGate.validate_content("pkg/main.go", broken_go)
    assert ok is False
    assert expected in msg


# ============================================================================
# 5. PHP Language Permutations Matrix
# ============================================================================

@pytest.mark.parametrize("snippet", [
    "<?php echo 'hello world'; ?>",
    "<?php\nclass App {\n  public function run(): void {}\n}\n",
    "<?\n$var = [1, 2, (3 + 4)];\n",
    "<?php\n// Comment with ( { [\n$x = 10;\n",
])
def test_php_valid_snippets(snippet: str):
    ok, msg = PolyglotSyntaxGate.validate_content("index.php", snippet)
    assert ok is True
    assert "PHP" in msg


@pytest.mark.parametrize("broken_php,expected", [
    ("echo 'Missing opening tag';", "Missing opening '<?php' tag"),
    ("$a = 10; $b = 20;", "Missing opening '<?php' tag"),
    ("<?php function broken() { echo (1 + 2; }", "Mismatched closing '}'"),
    ("<?php function broken() { (1 + 2", "Unclosed delimiter"),
    ("<?php function broken() { return 1; }}", "Unmatched closing '}'"),
    ("<?php function broken() { return [1, 2); }", "Mismatched closing ')'"),
])
def test_php_invalid_snippets(broken_php: str, expected: str):
    ok, msg = PolyglotSyntaxGate.validate_content("app.php", broken_php)
    assert ok is False
    assert expected in msg


# ============================================================================
# 6. Ruby Block Invariants Permutations Matrix
# ============================================================================

@pytest.mark.parametrize("snippet", [
    "def calculate(x, y)\n  x + y\nend",
    "class Controller\n  def index\n    render json: {}\n  end\nend",
    "module Helpers\n  class Formatter\n    def fmt\n      true\n    end\n  end\nend",
    "items.each do |item|\n  puts item\nend",
    "begin\n  risky_op\nrescue => e\n  log(e)\nend",
    "if condition\n  true\nelse\n  false\nend",
    "unless ready\n  wait\nend",
    "case state\nwhen :ready\n  start\nend",
    "# Ruby comment with def\ndef hello\n  'hi'\nend",
])
def test_ruby_valid_snippets(snippet: str):
    ok, msg = PolyglotSyntaxGate.validate_content("script.rb", snippet)
    assert ok is True
    assert "Ruby" in msg


@pytest.mark.parametrize("broken_ruby,expected", [
    ("def calc(x, y)\n  x + y\n", "Missing 'end' statement"),
    ("class Person\n  def name\n    'Alice'\n  end\n", "Missing 'end' statement"),
    ("def calc\n  1\nend\nend", "Unexpected 'end' statement"),
    ("items.each do |i|\n  puts i\n", "Missing 'end' statement"),
])
def test_ruby_invalid_snippets(broken_ruby: str, expected: str):
    ok, msg = PolyglotSyntaxGate.validate_content("app.rb", broken_ruby)
    assert ok is False
    assert expected in msg


# ============================================================================
# 7. YAML, TOML, Markdown, SQL Matrix
# ============================================================================

@pytest.mark.parametrize("yaml_code", [
    "name: prubeth\nversion: 2.0.0\nsettings:\n  enabled: true\n  workers: 4",
    "# comment with tab: \t\nkey: value\nlist:\n  - a\n  - b",
    "empty: true\n",
])
def test_yaml_valid(yaml_code: str):
    ok, msg = PolyglotSyntaxGate.validate_content("config.yaml", yaml_code)
    assert ok is True
    assert "YAML" in msg


@pytest.mark.parametrize("broken_yaml", [
    "name: prubeth\n\tenabled: true",
    "services:\n  worker:\n\timage: test",
])
def test_yaml_invalid_tab_indent(broken_yaml: str):
    ok, msg = PolyglotSyntaxGate.validate_content("pipeline.yml", broken_yaml)
    assert ok is False
    assert "Tab characters used in indentation" in msg


@pytest.mark.parametrize("toml_code", [
    "[package]\nname = 'prubeth'\nversion = '2.0.0'\n\n[dependencies]\npytest = '8.0'",
    "[[services]]\nname = 'gateway'\nport = 8080\n\n[[services]]\nname = 'worker'\nport = 8081",
    "# empty TOML\n",
])
def test_toml_valid(toml_code: str):
    ok, msg = PolyglotSyntaxGate.validate_content("pyproject.toml", toml_code)
    assert ok is True
    assert "TOML" in msg


@pytest.mark.parametrize("broken_toml", [
    "[package\nname = 'prubeth'",
    "[settings.advanced\nkey = 1",
])
def test_toml_unclosed_header(broken_toml: str):
    ok, msg = PolyglotSyntaxGate.validate_content("config.toml", broken_toml)
    assert ok is False
    assert "Unclosed section header" in msg


@pytest.mark.parametrize("md_code", [
    "# Title\n\n```python\nprint('hello')\n```\n\nRegular text.",
    "No code blocks here, just markdown.",
    "```bash\necho 1\n```\n\n```js\nconsole.log(2);\n```",
])
def test_markdown_valid(md_code: str):
    ok, msg = PolyglotSyntaxGate.validate_content("README.md", md_code)
    assert ok is True
    assert "Markdown" in msg


@pytest.mark.parametrize("broken_md", [
    "# Broken Guide\n\n```python\nprint('unclosed fence')",
    "```bash\nfirst fence\n```\n\n```second unclosed",
])
def test_markdown_odd_fences(broken_md: str):
    ok, msg = PolyglotSyntaxGate.validate_content("docs/guide.markdown", broken_md)
    assert ok is False
    assert "Unclosed code fence" in msg


@pytest.mark.parametrize("sql_code", [
    "SELECT id, name, email FROM users WHERE active = 1 ORDER BY id DESC;",
    "/* multi-line comment */ SELECT * FROM orders;",
    "-- single line comment\nINSERT INTO logs (msg) VALUES ('ready');",
])
def test_sql_valid(sql_code: str):
    ok, msg = PolyglotSyntaxGate.validate_content("schema.sql", sql_code)
    assert ok is True
    assert "SQL" in msg


def test_sql_unclosed_comment():
    broken = "/* unclosed comment\nSELECT * FROM secret_table;"
    ok, msg = PolyglotSyntaxGate.validate_content("query.sql", broken)
    assert ok is False
    assert "Unclosed block comment" in msg


# ============================================================================
# 8. Unrestricted Extensions Passthrough Matrix
# ============================================================================

@pytest.mark.parametrize("ext", [
    ".txt", ".sh", ".bash", ".zsh", ".bat", ".ps1", ".ini",
    ".cfg", ".csv", ".tsv", ".html", ".css", ".scss", ".svg",
    ".xml", ".dockerfile", ".env", ".properties"
])
def test_unrestricted_extensions(ext: str):
    arbitrary_content = "any arbitrary text ( [ { without closure or tags"
    ok, msg = PolyglotSyntaxGate.validate_content(f"data/file{ext}", arbitrary_content)
    assert ok is True
    assert "No syntax restrictions" in msg


# ============================================================================
# 9. Pragma Bypass Permutations Matrix
# ============================================================================

@pytest.mark.parametrize("pragma", [
    "prubeth: allow-syntax-error",
    "prubeth: no-gate",
    "prubeth: relaxed",
    "prubeth: force-syntax",
    "noqa: syntax",
])
@pytest.mark.parametrize("ext", [".py", ".rs", ".go", ".js", ".php", ".rb", ".yaml", ".toml"])
def test_all_pragmas_bypass_all_languages(pragma: str, ext: str):
    broken_content = f"# {pragma}\nThis is deliberately broken ( [ {{ def"
    ok, msg = PolyglotSyntaxGate.validate_content(f"fixture{ext}", broken_content)
    assert ok is True
    assert "bypassed via developer pragma" in msg
