"""Deep Parameterized Matrix Tests for TodoTool across code comment conventions."""

import pytest
from pathlib import Path
from prubeth.tools.domain.todo import TodoTool, PRIORITY_MAP


@pytest.fixture
def todo_tool():
    return TodoTool()


# =========================================================================
# Matrix: 30 Tag and Comment Permutations
# =========================================================================

TAG_VARIATIONS = [
    ("TODO", "implement feature", "MEDIUM"),
    ("todo", "lower case tag", "MEDIUM"),
    ("ToDo", "mixed case tag", "MEDIUM"),
    ("FIXME", "critical memory leak", "HIGH"),
    ("fixme", "lower fixme", "HIGH"),
    ("BUG", "null pointer exception on startup", "CRITICAL"),
    ("bug", "lower bug", "CRITICAL"),
    ("HACK", "temporary workaround for windows paths", "MEDIUM"),
    ("hack", "lower hack", "MEDIUM"),
    ("XXX", "dangerous code block review required", "HIGH"),
    ("xxx", "lower xxx", "HIGH"),
    ("OPTIMISE", "vectorize inner loop with SIMD", "LOW"),
    ("optimise", "british spelling lower", "LOW"),
    ("OPTIMIZE", "american spelling", "LOW"),
    ("NOTE", "architectural invariant explanation", "LOW"),
    ("note", "lower note", "LOW"),
]

@pytest.mark.parametrize("tag, text, expected_priority", TAG_VARIATIONS)
def test_matrix_todo_tags_and_priorities(tmp_path: Path, todo_tool, tag, text, expected_priority):
    f = tmp_path / f"test_{tag}.py"
    f.write_text(f"# {tag}: {text}\ndef worker(): pass\n", encoding="utf-8")

    res = todo_tool.execute({"path": str(f)})
    assert res.success is True
    assert res.metadata["count"] == 1
    item = res.metadata["items"][0]
    assert item["tag"] == tag.upper()
    assert item["priority"] == expected_priority
    assert text in item["text"]


# =========================================================================
# Matrix: 20 Author Parenthetical Formats
# =========================================================================

AUTHORS = ["alice", "bob", "developer-1", "sre.team", "core_maintainer"]

@pytest.mark.parametrize("author", AUTHORS)
def test_matrix_todo_author_extraction(tmp_path: Path, todo_tool, author):
    f = tmp_path / f"author_{author}.py"
    f.write_text(f"# TODO({author}): optimize query latency\nx = 1\n", encoding="utf-8")

    res = todo_tool.execute({"path": str(f)})
    assert res.success is True
    assert res.metadata["count"] == 1
    assert res.metadata["items"][0]["author"] == author


# =========================================================================
# Matrix: Polyglot Comment Syntax (//, #, /* */, --)
# =========================================================================

@pytest.mark.parametrize("ext, prefix", [
    (".py", "#"),
    (".sh", "#"),
    (".ts", "//"),
    (".js", "//"),
    (".go", "//"),
    (".rs", "//"),
    (".java", "//"),
    (".c", "//"),
    (".cpp", "//"),
    (".sql", "--"),
])
def test_matrix_polyglot_comment_syntax(tmp_path: Path, todo_tool, ext, prefix):
    f = tmp_path / f"module{ext}"
    f.write_text(f"{prefix} TODO: implement polyglot logic\n", encoding="utf-8")

    res = todo_tool.execute({"path": str(f)})
    assert res.success is True
    assert res.metadata["count"] == 1
    assert res.metadata["items"][0]["tag"] == "TODO"


# =========================================================================
# Matrix: Limit and Pagination
# =========================================================================

@pytest.mark.parametrize("limit", [1, 3, 5, 10])
def test_matrix_todo_limit(tmp_path: Path, todo_tool, limit):
    f = tmp_path / "bulk.py"
    lines = [f"# TODO: task {i}" for i in range(20)]
    f.write_text("\n".join(lines), encoding="utf-8")

    res = todo_tool.execute({"path": str(f), "limit": limit})
    assert res.success is True
    assert res.metadata["count"] == limit
