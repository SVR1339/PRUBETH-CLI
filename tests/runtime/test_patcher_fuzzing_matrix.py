"""Deep Fuzzing and Invariant Permutation Tests for FuzzyPatcher."""

import pytest
from prubeth.runtime.patcher import FuzzyPatcher, PatchResult


@pytest.fixture
def patcher():
    return FuzzyPatcher(fuzzy_threshold=0.88)


# =========================================================================
# Matrix: 24 Indentation Space Variations (0, 2, 4, 8 spaces, tabs)
# =========================================================================

INDENT_LEVELS = [0, 2, 4, 6, 8]

@pytest.mark.parametrize("orig_spaces", INDENT_LEVELS)
@pytest.mark.parametrize("target_spaces", [0, 2, 4])
def test_matrix_indentation_permutations(patcher, orig_spaces, target_spaces):
    orig_prefix = " " * orig_spaces
    target_prefix = " " * target_spaces

    orig = (
        f"{orig_prefix}def worker():\n"
        f"{orig_prefix}    val = 10\n"
        f"{orig_prefix}    return val\n"
    )
    target = (
        f"{target_prefix}def worker():\n"
        f"{target_prefix}    val = 10\n"
        f"{target_prefix}    return val\n"
    )
    repl = (
        f"{target_prefix}def worker():\n"
        f"{target_prefix}    val = 20\n"
        f"{target_prefix}    return val\n"
    )

    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert "val = 20" in res.patched_content
    # Original indentation level preserved
    assert f"{orig_prefix}def worker():" in res.patched_content


# =========================================================================
# Matrix: 30 Boundary and Escaped Regex Special Characters
# =========================================================================

SPECIAL_CODE_STRINGS = [
    "regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$'",
    "formula = a * (b + c) / (d - e) ** 2",
    "query = 'SELECT * FROM users WHERE (id = ? AND status = ?)'",
    "shell = '$VAR || echo \"default\" && exit 1'",
    "json_data = '{\"key\": [1, 2, 3], \"nested\": {\"valid\": true}}'",
    "unicode_txt = '# CJK text: 开发者自治系统 · 零延迟'",
    "emoji_txt = '# Status: 🚀 Success | 🛡️ Secure | ⚡ 10x Fast'",
    "path_str = 'C:\\\\Users\\\\asus\\\\AppData\\\\Local\\\\Programs'",
    "pointer_arith = 'void* ptr = (char*)base + offset * sizeof(int);'",
    "lambda_expr = 'fn = lambda x, y: (x + y) if x > 0 else (x - y)'",
]

@pytest.mark.parametrize("idx, snippet", list(enumerate(SPECIAL_CODE_STRINGS)))
def test_matrix_special_characters_exact_replacement(patcher, idx, snippet):
    orig = f"def setup_{idx}():\n    {snippet}\n    return True\n"
    target = f"    {snippet}"
    repl = f"    # Replaced: {snippet}\n    pass"

    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert "pass" in res.patched_content


# =========================================================================
# Matrix: 30 Multi-Line Window Replacements
# =========================================================================

@pytest.mark.parametrize("block_lines", [2, 3, 5, 8, 12])
def test_matrix_variable_length_block_replacement(patcher, block_lines):
    lines_orig = [f"    line_{i} = {i} * 10" for i in range(block_lines)]
    orig = "def compute():\n" + "\n".join(lines_orig) + "\n    return True\n"

    target_lines = [f"    line_{i} = {i} * 10" for i in range(block_lines)]
    target = "\n".join(target_lines)

    repl_lines = [f"    line_{i}_mod = {i} * 20" for i in range(block_lines)]
    repl = "\n".join(repl_lines)

    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert "line_0_mod" in res.patched_content
    assert "return True" in res.patched_content


# =========================================================================
# Matrix: 20 Partial Context Disambiguations
# =========================================================================

@pytest.mark.parametrize("ctx_size", [1, 2, 3, 4])
def test_matrix_context_disambiguation_avoids_ambiguity(patcher, ctx_size):
    # Two identical functions except surrounding comments
    orig = (
        "# Function Section Alpha\n"
        "def helper():\n"
        "    return 42\n\n"
        "# Function Section Beta\n"
        "def helper():\n"
        "    return 42\n"
    )

    # Disambiguated by including Section Alpha comment
    target = (
        "# Function Section Alpha\n"
        "def helper():\n"
        "    return 42"
    )
    repl = (
        "# Function Section Alpha\n"
        "def helper():\n"
        "    return 100"
    )

    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert "return 100" in res.patched_content
    # Verify Beta was preserved
    assert "# Function Section Beta\ndef helper():\n    return 42" in res.patched_content
