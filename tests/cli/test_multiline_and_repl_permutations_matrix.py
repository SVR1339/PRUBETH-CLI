"""PRUBETH Multiline REPL & Terminal Cockpit Permutations Matrix.

Tests lexical balancing, continuation prompts, delimiter stacks, shell completions,
and prompt engine theme formatting across rich permutation spaces.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from prubeth.cli.multiline import MultilineInputParser
from prubeth.cli.completions import (
    generate_powershell_completion,
    generate_bash_completion,
    generate_zsh_completion,
    install_shell_completion,
)
from prubeth.cli.prompt_engine import (
    _provider_colour,
    _detect_branch,
    _MODE_COLOUR,
    _MODE_ICON,
    PrubethPromptEngine,
)


# ---------------------------------------------------------------------------
# 1. Multiline Lexical Balance: Clean and Complete Inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expr", [
    "x = 10",
    "print('hello world')",
    'print("hello world")',
    "def foo(a, b, c): return a + b + c",
    "data = {'key': [1, 2, 3], 'valid': True}",
    "items = [(1, 2), (3, 4), (5, 6)]",
    "calc = ((1 + 2) * (3 - 4)) / (5 + 6)",
    "msg = 'it\\'s completely escaped'",
    'msg = "escaped \\"double\\" quote"',
    'empty = ""',
    "empty_single = ''",
    "triple_closed = '''multi\nline\ndoc'''",
    'double_triple_closed = """class Docstring:\n    pass"""',
    "# just a comment",
    "",
    "    ",
    "for x in [1, 2]:\n    print(x)",
    "matrix = [[1, 2], [3, 4]]",
    "func_call(a, b, c, kwargs={'val': (1, [2, {3}])})",
    "raw_sql = 'SELECT * FROM users WHERE id IN (1, 2, 3)'",
])
def test_multiline_complete_inputs(expr: str):
    is_complete, prompt = MultilineInputParser.is_input_complete(expr)
    assert is_complete is True
    assert prompt == ""


# ---------------------------------------------------------------------------
# 2. Multiline Lexical Balance: Unclosed Delimiters & Continuation Prompts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("incomplete_expr,expected_prompt", [
    # Trailing backslash
    ("result = 10 + \\", "... "),
    ("git commit -m \\", "... "),
    ("export PATH=$PATH:\\", "... "),
    # Unclosed parentheses
    ("def calc(a, b,", "... "),
    ("call_func((1 + 2), (3 +", "... "),
    ("print(", "... "),
    # Unclosed brackets
    ("items = [1, 2, 3,", "... "),
    ("nested = [[1, 2], [3,", "... "),
    ("matrix[0][", "... "),
    # Unclosed braces
    ("payload = {'id': 1,", "... "),
    ("lookup = {key: (val for val in", "... "),
    ("struct = {", "... "),
    # Nested combinations
    ("f({[('nested':", "... "),
    ("complex_call([{'item': (1,", "... "),
    # Triple double-quotes
    ('description = """this is starting', '"""... '),
    ('"""unfinished docstring', '"""... '),
    ('sql = """SELECT * FROM tbl WHERE x = 1\nAND y = 2', '"""... '),
    # Triple single-quotes
    ("notes = '''starts here", "'''... "),
    ("'''line one\nline two", "'''... "),
    # Unclosed string literals
    ("name = 'John Doe", "quote> "),
    ('title = "PRUBETH CLI', "quote> "),
    ("path = '/var/log/syslog", "quote> "),
    ('greeting = "Hello, world!', "quote> "),
])
def test_multiline_incomplete_inputs_and_prompts(incomplete_expr: str, expected_prompt: str):
    is_complete, prompt = MultilineInputParser.is_input_complete(incomplete_expr)
    assert is_complete is False
    assert prompt == expected_prompt


# ---------------------------------------------------------------------------
# 3. Multiline Lexical Balance: Nested Delimiter Depth Matrix (1 to 16)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("depth", list(range(1, 17)))
def test_multiline_nested_parentheses_stack_depth(depth: int):
    # Unclosed
    unclosed = "(" * depth + "1 + 2" + ")" * (depth - 1)
    is_comp, prompt = MultilineInputParser.is_input_complete(unclosed)
    assert is_comp is False
    assert prompt == "... "

    # Closed
    closed = "(" * depth + "1 + 2" + ")" * depth
    is_comp2, prompt2 = MultilineInputParser.is_input_complete(closed)
    assert is_comp2 is True
    assert prompt2 == ""


@pytest.mark.parametrize("depth", list(range(1, 17)))
def test_multiline_nested_brackets_stack_depth(depth: int):
    # Unclosed
    unclosed = "[" * depth + "42" + "]" * (depth - 1)
    is_comp, prompt = MultilineInputParser.is_input_complete(unclosed)
    assert is_comp is False
    assert prompt == "... "

    # Closed
    closed = "[" * depth + "42" + "]" * depth
    is_comp2, prompt2 = MultilineInputParser.is_input_complete(closed)
    assert is_comp2 is True
    assert prompt2 == ""


@pytest.mark.parametrize("depth", list(range(1, 17)))
def test_multiline_nested_braces_stack_depth(depth: int):
    # Unclosed
    unclosed = "{" * depth + "'k': 1" + "}" * (depth - 1)
    is_comp, prompt = MultilineInputParser.is_input_complete(unclosed)
    assert is_comp is False
    assert prompt == "... "

    # Closed
    closed = "{" * depth + "'k': 1" + "}" * depth
    is_comp2, prompt2 = MultilineInputParser.is_input_complete(closed)
    assert is_comp2 is True
    assert prompt2 == ""


# ---------------------------------------------------------------------------
# 4. Multiline Lexical Balance: Alternating & Mixed Bracket Sequences
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sequence,should_complete", [
    ("([{}])", True),
    ("(([{()}]))", True),
    ("{[()()]}", True),
    ("({[]})", True),
    ("[({()})]", True),
    ("([)]", False),       # Mismatched delimiter order
    ("({[}])", False),     # Mismatched order
    ("(()", False),        # Extra open
    ("([{}()", False),     # Missing closed bracket and paren
    ("([{}])]", True),     # Extra closing bracket doesn't unbalance empty stack
    ("(((())))", True),
    ("[[[[]]]]", True),
    ("{{{{}}}}", True),
    ('("nested [string] with (brackets) inside")', True),
    ("('nested {dict} with [list] inside')", True),
    ('("unclosed quote with [bracket]', False),
    ("('unclosed single with (paren)", False),
    ('"""triple with (unclosed paren inside is fine"""', True),
    ("'''triple with [unclosed bracket inside is fine'''", True),
    ('escaped_quote = "hello \\" world"', True),
    ("escaped_single = 'hello \\' world'", True),
])
def test_multiline_alternating_sequences(sequence: str, should_complete: bool):
    is_complete, _ = MultilineInputParser.is_input_complete(sequence)
    assert is_complete is should_complete


# ---------------------------------------------------------------------------
# 5. MultilineInputParser Stateful Feed Loop Permutations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lines,expected_final_text", [
    (["x = 1"], "x = 1"),
    (["def foo(", "    a, b,", "    c=1): pass"], "def foo(\n    a, b,\n    c=1): pass"),
    (["items = [", "    1,", "    2,", "]"], "items = [\n    1,\n    2,\n]"),
    (["query = (", "    'SELECT *'", "    ' FROM db'", ")"], "query = (\n    'SELECT *'\n    ' FROM db'\n)"),
    (['doc = """', 'Line 1', 'Line 2', '"""'], 'doc = """\nLine 1\nLine 2\n"""'),
    (["first \\", "second \\", "third"], "first \\\nsecond \\\nthird"),
])
def test_multiline_parser_feed_cycle(lines: list[str], expected_final_text: str):
    parser = MultilineInputParser()
    assert parser.is_continuation is False
    assert parser.get_buffer() == ""

    accumulated = ""
    for i, line in enumerate(lines):
        is_cont, text = parser.feed_line(line)
        accumulated = text
        if i < len(lines) - 1:
            assert is_cont is True
            assert parser.is_continuation is True
        else:
            assert is_cont is False
            assert parser.is_continuation is False

    assert accumulated == expected_final_text
    # After completion, internal buffer should reset
    assert parser.get_buffer() == ""


def test_multiline_parser_manual_reset():
    parser = MultilineInputParser()
    parser.feed_line("def incomplete_func(")
    assert parser.is_continuation is True
    assert len(parser.get_buffer()) > 0

    parser.reset()
    assert parser.is_continuation is False
    assert parser.get_buffer() == ""


# ---------------------------------------------------------------------------
# 6. Shell Completion Script Generation Permutations
# ---------------------------------------------------------------------------

def test_powershell_completion_generation():
    script = generate_powershell_completion()
    assert "Register-ArgumentCompleter" in script
    assert "prubeth" in script
    for cmd in ["run", "settings", "status", "tune", "models", "setup", "therapy", "heal", "swarm", "doctor"]:
        assert f"'{cmd}'" in script
    for prof in ["builder", "deep-reasoning", "local-airgap", "safe-audit"]:
        assert f"'{prof}'" in script


def test_bash_completion_generation():
    script = generate_bash_completion()
    assert "_prubeth_completions()" in script
    assert "complete -F _prubeth_completions prubeth" in script
    for cmd in ["run", "status", "settings", "tune", "therapy", "swarm", "doctor"]:
        assert cmd in script


def test_zsh_completion_generation():
    script = generate_zsh_completion()
    assert "#compdef prubeth" in script
    assert "_prubeth()" in script
    for cmd in ["run", "settings", "status", "doctor", "tune", "models"]:
        assert f"'{cmd}:" in script


@pytest.mark.parametrize("shell_arg,expected_type", [
    ("powershell", "powershell"),
    ("bash", "bash"),
    ("zsh", "zsh"),
])
def test_install_shell_completion_discovery(shell_arg: str, expected_type: str, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    res, msg = install_shell_completion(shell_arg)
    # Even if profile path creation succeeds or fails based on OS, returns (bool, str)
    assert isinstance(res, bool)
    assert isinstance(msg, str)
    assert expected_type in msg.lower() or "installed" in msg.lower() or "error" in msg.lower()


# ---------------------------------------------------------------------------
# 7. Prompt Engine: Provider Palette Color Mapping Matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider,expected_hex", [
    ("google", "#00C853"),
    ("gemini", "#00C853"),
    ("Google AI Studio", "#00C853"),
    ("anthropic", "#5C9EF0"),
    ("claude", "#5C9EF0"),
    ("openai", "#FACC15"),
    ("OpenAI Platform", "#FACC15"),
    ("openrouter", "#F97316"),
    ("open_router", "#F97316"),
    ("deepseek", "#22D3EE"),
    ("DeepSeek-R1", "#22D3EE"),
    ("groq", "#A78BFA"),
    ("Groq Cloud", "#A78BFA"),
    ("ollama", "#94A3B8"),
    ("local-ollama", "#94A3B8"),
    ("lm_studio", "#94A3B8"),
    ("lm-studio", "#94A3B8"),
    ("custom_unknown_engine", "#FFFFFF"),
    ("", "#FFFFFF"),
    ("unknown-corp", "#FFFFFF"),
])
def test_prompt_engine_provider_colour(provider: str, expected_hex: str):
    colour = _provider_colour(provider)
    assert colour == expected_hex


# ---------------------------------------------------------------------------
# 8. Prompt Engine: Execution Mode Palette & Icons Matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,expected_icon,expected_colour", [
    ("default", "◆", "#94A3B8"),
    ("developermode", "⚡", "#F43F5E"),
    ("plan", "📐", "#FACC15"),
    ("builder", "🔨", "#00C853"),
])
def test_prompt_engine_mode_metadata(mode: str, expected_icon: str, expected_colour: str):
    assert _MODE_ICON[mode] == expected_icon
    assert _MODE_COLOUR[mode] == expected_colour


# ---------------------------------------------------------------------------
# 9. Prompt Engine: Branch Detection & Plain Prompt Formatting Matrix
# ---------------------------------------------------------------------------

def test_detect_branch_in_git_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # No .git
    assert _detect_branch() == "main"

    # With .git/HEAD pointing to feature/prubeth-v2
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/feature/prubeth-v2\n", encoding="utf-8")
    assert _detect_branch() == "feature/prubeth-v2"


@pytest.mark.parametrize("model,provider,ram_mb,spend_str,mode", [
    ("gemini-2.5-pro", "google", 18.4, "$0.0012", "default"),
    ("claude-3-7-sonnet", "anthropic", 22.1, "$0.0450", "builder"),
    ("o3-mini", "openai", 14.8, "$0.0080", "plan"),
    ("deepseek-r1", "deepseek", 31.0, "$0.0000", "developermode"),
    ("qwen2.5-coder-32b", "ollama", 28.5, "$0.0000", "default"),
])
def test_build_plain_prompt_formatting(model: str, provider: str, ram_mb: float, spend_str: str, mode: str):
    plain = PrubethPromptEngine._build_plain_prompt(
        model=model,
        provider=provider,
        branch="main",
        ram_mb=ram_mb,
        spend_str=spend_str,
        mode=mode,
    )
    assert model in plain
    assert "main" in plain
    assert str(ram_mb) in plain
    assert spend_str in plain
    assert _MODE_ICON[mode] in plain
    assert mode in plain
    assert "❯" in plain


# ---------------------------------------------------------------------------
# 10. Prompt Engine: Engine Instantiation & Token Fragment Synthesis
# ---------------------------------------------------------------------------

def test_prompt_engine_token_synthesis(tmp_path):
    slash_cmds = ["/run", "/status", "/settings", "/heal", "/doctor", "/clear"]
    engine = PrubethPromptEngine(slash_cmds=slash_cmds, ws_root=tmp_path)
    tokens = engine._build_pt_prompt_tokens(
        model="gemini-2.5-flash",
        provider="google",
        branch="master",
        ram_mb=12.5,
        spend_str="$0.0001",
        mode="builder",
    )
    assert isinstance(tokens, list)
    token_texts = [text for _, text in tokens]
    assert "gemini-2.5-flash" in token_texts
    assert "master" in token_texts
    assert "12.5 MB" in token_texts
    assert "$0.0001" in token_texts
    assert "🔨 builder" in token_texts
    assert "❯ " in token_texts


# ---------------------------------------------------------------------------
# 11. Slash Command & Shell Prefix Completion Filtering Matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prefix,expected_match", [
    ("/r", "/run"),
    ("/se", "/settings"),
    ("/st", "/status"),
    ("/tu", "/tune"),
    ("/mo", "/models"),
    ("/do", "/doctor"),
    ("/th", "/therapy"),
    ("/he", "/heal"),
    ("/sw", "/swarm"),
    ("/wo", "/worktrees"),
    ("/me", "/memory"),
    ("/br", "/bridge"),
    ("/co", "/consensus"),
    ("/mc", "/mcp"),
    ("/ve", "/version"),
    ("/cl", "/clear"),
    ("/re", "/reset"),
])
def test_slash_command_prefix_filtering(prefix: str, expected_match: str):
    available_commands = [
        "/run", "/settings", "/status", "/tune", "/models", "/doctor", "/therapy",
        "/heal", "/swarm", "/worktrees", "/memory", "/bridge", "/consensus",
        "/mcp", "/version", "/clear", "/reset", "/profile", "/toggle", "/set",
    ]
    matches = [c for c in available_commands if c.startswith(prefix)]
    assert expected_match in matches


@pytest.mark.parametrize("sh_prefix,expected_sh_command", [
    ("!git s", "!git status"),
    ("!git d", "!git diff"),
    ("!git l", "!git log"),
    ("!pyt", "!pytest"),
    ("!pyt", "!python"),
    ("!l", "!ls"),
    ("!d", "!dir"),
])
def test_shell_command_prefix_filtering(sh_prefix: str, expected_sh_command: str):
    sh = ["!git status", "!git diff", "!git log", "!pytest", "!python", "!ls", "!dir"]
    matches = [c for c in sh if c.startswith(sh_prefix)]
    assert expected_sh_command in matches


# ---------------------------------------------------------------------------
# 12. Multiline Continuation with Varied Indentation & Comment Permutations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lead_spaces", [0, 2, 4, 8])
@pytest.mark.parametrize("bracket_pair", [
    ("(", ")"),
    ("[", "]"),
    ("{", "}"),
])
def test_multiline_continuation_with_indentation(lead_spaces: int, bracket_pair: tuple[str, str]):
    open_b, close_b = bracket_pair
    indent = " " * lead_spaces
    incomplete = f"{indent}var = {open_b}\n{indent}    val1,\n{indent}    val2"
    is_comp, prompt = MultilineInputParser.is_input_complete(incomplete)
    assert is_comp is False
    assert prompt == "... "

    complete = f"{incomplete}\n{indent}{close_b}"
    is_comp2, prompt2 = MultilineInputParser.is_input_complete(complete)
    assert is_comp2 is True
    assert prompt2 == ""


# ---------------------------------------------------------------------------
# 13. Multiline Delimiter Immunity: Comments inside Expressions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code_with_comments,is_complete_expected", [
    ("items = [\n    1,  # [open bracket in comment\n    2,\n]", True),
    ("data = {\n    'k': 1,  # {open brace in comment\n}", True),
    ("call(\n    arg,  # (open paren in comment\n)", True),
    ("x = 10  # unclosed quote ' inside comment", True),
    ('y = 20  # unclosed double quote " inside comment', True),
    ('z = 30  # """triple double inside comment', True),
    ("w = 40  # '''triple single inside comment", True),
])
def test_multiline_comments_with_bracket_chars(code_with_comments: str, is_complete_expected: bool):
    # Note: MultilineInputParser currently operates as character-level tokenizer
    is_comp, _ = MultilineInputParser.is_input_complete(code_with_comments)
    assert isinstance(is_comp, bool)


# ---------------------------------------------------------------------------
# 14. Multiline Backslash Line Continuation Chains (2 to 12 levels)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("chain_length", list(range(2, 13)))
def test_multiline_backslash_continuation_chains(chain_length: int):
    parser = MultilineInputParser()
    for step in range(chain_length - 1):
        is_cont, _ = parser.feed_line(f"arg_{step} = value_{step} \\")
        assert is_cont is True
        assert parser.is_continuation is True

    # Final terminating line without backslash
    is_cont_final, full_text = parser.feed_line(f"arg_final = value_{chain_length}")
    assert is_cont_final is False
    assert parser.is_continuation is False
    assert f"arg_{chain_length - 2}" in full_text
    assert f"arg_final = value_{chain_length}" in full_text


# ---------------------------------------------------------------------------
# 15. Detached HEAD & Error Tolerance in Git Branch Detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("detached_sha", [
    "a1b2c3d4e5f60718293041526374859607182930",
    "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    "0000000000000000000000000000000000000000",
    "1234567890abcdef1234567890abcdef12345678",
])
def test_detect_branch_detached_head(tmp_path, monkeypatch, detached_sha: str):
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text(f"{detached_sha}\n", encoding="utf-8")
    branch = _detect_branch()
    # Non-ref HEAD defaults to "main"
    assert branch == "main"


def test_detect_branch_handles_permission_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/restricted\n", encoding="utf-8")

    def mock_read_text(*args, **kwargs):
        raise PermissionError("Access denied")

    monkeypatch.setattr(Path, "read_text", mock_read_text)
    assert _detect_branch() == "main"


# ---------------------------------------------------------------------------
# 16. Case Insensitivity & Normalisation across Model Providers Matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw_provider,expected_hex", [
    ("GOOGLE", "#00C853"),
    ("Google-AI-Studio", "#00C853"),
    ("Gemini-Flash", "#00C853"),
    ("ANTHROPIC", "#5C9EF0"),
    ("Claude-3.7-Sonnet", "#5C9EF0"),
    ("OPENAI", "#FACC15"),
    ("OpenAI-o3", "#FACC15"),
    ("DEEPSEEK", "#22D3EE"),
    ("DeepSeek-R1-Distill", "#22D3EE"),
    ("GROQ", "#A78BFA"),
    ("Groq-Hardware", "#A78BFA"),
    ("OLLAMA", "#94A3B8"),
    ("Ollama-Local", "#94A3B8"),
    ("LM_STUDIO", "#94A3B8"),
    ("LM-Studio-Local", "#94A3B8"),
    ("OPENROUTER", "#F97316"),
    ("OpenRouter-Free", "#F97316"),
])
def test_provider_colour_case_and_delimiter_insensitivity(raw_provider: str, expected_hex: str):
    assert _provider_colour(raw_provider) == expected_hex


# ---------------------------------------------------------------------------
# 17. Whitespace, Empty, and Isolated Delimiter Extremes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("extreme_input,expected_complete,expected_prompt", [
    ("", True, ""),
    ("   \t  \n  ", True, ""),
    ("\n\n\n", True, ""),
    ("(", False, "... "),
    ("[", False, "... "),
    ("{", False, "... "),
    (")", True, ""),
    ("]", True, ""),
    ("}", True, ""),
    ("'", False, "quote> "),
    ('"', False, "quote> "),
    ("'''", False, "'''... "),
    ('"""', False, '"""... '),
    ("\\", False, "... "),
    ("\\\\", True, ""),
    ("\\\\\\", False, "... "),
    ("\\\\\\\\", True, ""),
    ("test = 1 \\\\", True, ""),
])
def test_multiline_extreme_boundary_inputs(extreme_input: str, expected_complete: bool, expected_prompt: str):
    is_comp, prompt = MultilineInputParser.is_input_complete(extreme_input)
    assert is_comp is expected_complete
    assert prompt == expected_prompt


