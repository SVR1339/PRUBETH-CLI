"""Comprehensive Unit and Stress Tests for FuzzyPatcher Whitespace Resilience."""

import pytest
from prubeth.runtime.patcher import FuzzyPatcher, PatchResult


@pytest.fixture
def patcher():
    return FuzzyPatcher(fuzzy_threshold=0.88)


# =========================================================================
# Exact Match & Ambiguity Invariants
# =========================================================================

def test_exact_single_occurrence_replaces_cleanly(patcher):
    orig = "def compute():\n    return 42\n"
    target = "    return 42"
    repl = "    return 100"
    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert res.match_kind == "exact"
    assert res.confidence == 1.0
    assert "return 100" in res.patched_content


def test_empty_target_returns_failure(patcher):
    orig = "some code\n"
    res = patcher.apply_patch(orig, "", "replacement")
    assert res.success is False
    assert "cannot be empty" in res.error_message


def test_ambiguous_target_multiple_occurrences_fails_with_count(patcher):
    orig = "x = 1\nx = 1\nx = 1\n"
    target = "x = 1"
    res = patcher.apply_patch(orig, target, "x = 2")
    assert res.success is False
    assert res.matches_found == 3
    assert "Ambiguous target" in res.error_message


# =========================================================================
# Line Ending Invariants (\r\n vs \n)
# =========================================================================

def test_crlf_target_in_lf_file_matches_and_preserves_lf(patcher):
    orig = "def test():\n    pass\n"  # LF file
    target = "def test():\r\n    pass\r\n"  # CRLF target from Windows model
    repl = "def test():\r\n    return True\r\n"
    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert "\r\n" not in res.patched_content  # LF preserved
    assert "return True" in res.patched_content


def test_lf_target_in_crlf_file_matches_and_preserves_crlf(patcher):
    orig = "def test():\r\n    pass\r\n"  # CRLF file
    target = "def test():\n    pass\n"  # LF target
    repl = "def test():\n    return True\n"
    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert "\r\n" in res.patched_content  # CRLF preserved
    assert "return True" in res.patched_content


# =========================================================================
# Indentation Transfer & Trimmed Line Matching
# =========================================================================

def test_indentation_transfer_2_spaces_to_4_spaces(patcher):
    # Original file is 4-space indented
    orig = (
        "class Worker:\n"
        "    def run(self):\n"
        "        step_one()\n"
        "        step_two()\n"
    )
    # Model target has 2 spaces
    target = (
        "  def run(self):\n"
        "    step_one()\n"
        "    step_two()\n"
    )
    # Model replacement has 2 spaces
    repl = (
        "  def run(self):\n"
        "    step_one()\n"
        "    step_two_optimized()\n"
    )
    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    # Verify that original 4-space indentation is preserved in patched result
    assert "    def run(self):" in res.patched_content
    assert "        step_two_optimized()" in res.patched_content


def test_tab_indentation_transfer(patcher):
    orig = (
        "def main():\n"
        "\tstep_a()\n"
        "\tstep_b()\n"
    )
    target = (
        "def main():\n"
        "    step_a()\n"
        "    step_b()\n"
    )
    repl = (
        "def main():\n"
        "    step_a_v2()\n"
        "    step_b_v2()\n"
    )
    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert "step_a_v2()" in res.patched_content


# =========================================================================
# Fuzzy Sliding Window Matching
# =========================================================================

def test_fuzzy_match_minor_character_difference(patcher):
    orig = (
        "def authenticate_user(username: str, password_hash: str) -> bool:\n"
        "    if not username:\n"
        "        return False\n"
        "    return verify_hash(username, password_hash)\n"
    )
    # Model missed type annotation in target
    target = (
        "def authenticate_user(username, password_hash):\n"
        "    if not username:\n"
        "        return False\n"
        "    return verify_hash(username, password_hash)\n"
    )
    repl = (
        "def authenticate_user(username: str, password_hash: str) -> bool:\n"
        "    if not username or not password_hash:\n"
        "        return False\n"
        "    return verify_hash(username, password_hash)\n"
    )
    res = patcher.apply_patch(orig, target, repl)
    assert res.success is True
    assert res.match_kind in ("fuzzy_line_match", "normalised_whitespace")
    assert "not password_hash" in res.patched_content


def test_completely_unrelated_target_fails(patcher):
    orig = "def existing_function():\n    return 1\n"
    target = "def non_existent_thing(xyz):\n    do_nothing()\n"
    res = patcher.apply_patch(orig, target, "new_code")
    assert res.success is False
    assert res.match_kind == "failed"
    assert "could not be located" in res.error_message or "below required threshold" in res.error_message
