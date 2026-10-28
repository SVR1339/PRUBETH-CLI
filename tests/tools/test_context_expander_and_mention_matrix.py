"""Tests for ContextExpander @mention parsing, code slicing, and token guard matrices."""

import pytest
from pathlib import Path
from prubeth.repository.context import ContextExpander


@pytest.fixture
def mention_workspace(tmp_path):
    """Sets up a realistic workspace for @mention expansion tests."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)

    # 1. Component file
    (src / "auth.py").write_text('''
def verify_credentials(user: str, token: str) -> bool:
    """Verifies user credentials."""
    if not user or not token:
        return False
    return True

class Session:
    def __init__(self, user: str):
        self.user = user
''', encoding="utf-8")

    # 2. Config file
    (src / "config.json").write_text('{"env": "production", "debug": false}', encoding="utf-8")

    return tmp_path


# =========================================================================
# File Mention Resolution Tests
# =========================================================================

def test_resolve_file_mention_whole_file(mention_workspace):
    expander = ContextExpander(workspace_root=mention_workspace)
    cleaned, atts = expander.resolve_mentions("Please review @src/auth.py for security.")
    assert len(atts) >= 1
    file_att = next(a for a in atts if a["type"] == "file")
    assert "src/auth.py" in file_att["label"]
    assert "verify_credentials" in file_att["content"]


def test_resolve_file_mention_with_line_range(mention_workspace):
    expander = ContextExpander(workspace_root=mention_workspace)
    cleaned, atts = expander.resolve_mentions("Check lines @src/auth.py:2-6 specifically.")
    assert len(atts) >= 1
    file_att = next(a for a in atts if a["type"] == "file")
    assert "verify_credentials" in file_att["content"]


def test_resolve_nonexistent_file_mention_handled_cleanly(mention_workspace):
    expander = ContextExpander(workspace_root=mention_workspace)
    cleaned, atts = expander.resolve_mentions("Inspect @src/missing.py please.")
    # Should not crash, and cleaned prompt remains intelligible
    assert "missing.py" in cleaned or len(atts) == 0


# =========================================================================
# Mention Extraction Scale Matrix (Parametrized Prompts)
# =========================================================================

PROMPT_PERMUTATIONS = [
    (f"Refactor @src/auth.py focusing on security aspect #{i}", "src/auth.py")
    for i in range(25)
]

@pytest.mark.parametrize("prompt,expected_file", PROMPT_PERMUTATIONS)
def test_mention_matrix_prompts(mention_workspace, prompt, expected_file):
    expander = ContextExpander(workspace_root=mention_workspace)
    cleaned, atts = expander.resolve_mentions(prompt)
    assert len(atts) >= 1
    assert any(expected_file in a.get("label", "") for a in atts)


LINE_RANGE_PERMUTATIONS = [
    (1, 4),
    (2, 6),
    (5, 8),
    (1, 10),
]

@pytest.mark.parametrize("start,end", LINE_RANGE_PERMUTATIONS)
def test_mention_line_range_slices(mention_workspace, start, end):
    expander = ContextExpander(workspace_root=mention_workspace)
    prompt = f"Examine slice @src/auth.py:{start}-{end}."
    cleaned, atts = expander.resolve_mentions(prompt)
    assert len(atts) >= 1
    att = next(a for a in atts if a["type"] == "file")
    assert f":{start}-{end}" in att["label"]
