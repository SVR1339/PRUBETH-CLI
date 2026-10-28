"""PRUBETH Verification & Domain Tools Exhaustive Permutations Matrix.

Tests LintCheckerTool, TypeCheckerTool, PatchVerifierTool, TodoTool, BenchmarkTool,
and Git tools (GitStatusTool, GitDiffTool, GitLogTool, GitCommitTool) across parameter
boundaries, file systems, error modes, AST analyses, and git lifecycle states.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
import pytest

from prubeth.tools.verification.lint_checker import LintCheckerTool
from prubeth.tools.verification.type_checker import TypeCheckerTool
from prubeth.tools.verification.patch_verifier import PatchVerifierTool
from prubeth.tools.domain.todo import TodoTool
from prubeth.tools.domain.benchmark import BenchmarkTool
from prubeth.tools.core.git_status import GitStatusTool
from prubeth.tools.core.git_diff import GitDiffTool
from prubeth.tools.core.git_log import GitLogTool
from prubeth.tools.core.git_commit import GitCommitTool


# ============================================================================
# 1. LintCheckerTool Exhaustive Matrix
# ============================================================================

def test_lint_checker_missing_path():
    tool = LintCheckerTool()
    res = tool.execute({"path": ""})
    assert not res.success
    assert "Missing target path" in res.error


def test_lint_checker_nonexistent_path(tmp_path: Path):
    tool = LintCheckerTool()
    res = tool.execute({"path": str(tmp_path / "ghost_file.py")})
    assert not res.success
    assert "does not exist" in res.error


def test_lint_checker_ast_clean_python_file(tmp_path: Path):
    p = tmp_path / "clean.py"
    p.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    tool = LintCheckerTool()
    res = tool.execute({"path": str(p), "linter": "ast"})
    assert res.success
    assert "Passed" in res.output or "clean" in res.output.lower() or "0" in res.output


def test_lint_checker_ast_syntax_error(tmp_path: Path):
    p = tmp_path / "broken.py"
    p.write_text("def broken(a, b\n    return a + b\n", encoding="utf-8")
    tool = LintCheckerTool()
    res = tool.execute({"path": str(p), "linter": "ast"})
    assert not res.success
    assert "SyntaxError" in (res.error or "") or "SyntaxError" in (res.output or "")


@pytest.mark.parametrize("engine", ["ast", "unknown_engine"])
def test_lint_checker_engine_dispatch(tmp_path: Path, engine: str):
    p = tmp_path / "test.py"
    p.write_text("x = 1\n", encoding="utf-8")
    tool = LintCheckerTool()
    res = tool.execute({"path": str(p), "linter": engine})
    # 'ast' succeeds and unknown engines gracefully fall back to AST scanner
    assert res.success
    assert res.exit_code == 0


# ============================================================================
# 2. TypeCheckerTool Exhaustive Matrix
# ============================================================================

def test_type_checker_missing_path():
    tool = TypeCheckerTool()
    res = tool.execute({"path": ""})
    assert not res.success
    assert "Missing target path" in res.error


def test_type_checker_nonexistent_path(tmp_path: Path):
    tool = TypeCheckerTool()
    res = tool.execute({"path": str(tmp_path / "nonexistent.py")})
    assert not res.success
    assert "does not exist" in res.error


def test_type_checker_ast_fully_annotated(tmp_path: Path):
    p = tmp_path / "typed.py"
    p.write_text(
        "def greet(name: str) -> str:\n"
        "    return f'Hello, {name}'\n\n"
        "def add(x: int, y: int) -> int:\n"
        "    return x + y\n",
        encoding="utf-8"
    )
    tool = TypeCheckerTool()
    res = tool.execute({"path": str(p), "engine": "ast", "strict": True})
    assert res.success
    assert "100.0%" in res.output or "100%" in res.output


def test_type_checker_ast_unannotated_strict_mode(tmp_path: Path):
    p = tmp_path / "untyped.py"
    p.write_text(
        "def untyped_func(a, b):\n"
        "    return a + b\n",
        encoding="utf-8"
    )
    tool = TypeCheckerTool()
    res = tool.execute({"path": str(p), "engine": "ast", "strict": True})
    # Strict mode enforces annotations and flags missing signatures as failures
    assert not res.success
    assert "missing" in res.output.lower() or "0.0%" in res.output or "failed" in res.output.lower()


# ============================================================================
# 3. PatchVerifierTool Exhaustive Matrix
# ============================================================================

def test_patch_verifier_missing_args(tmp_path: Path):
    tool = PatchVerifierTool()
    assert not tool.execute({"path": "", "target": "a", "replacement": "b"}).success
    assert not tool.execute({"path": str(tmp_path / "f.py"), "target": "", "replacement": "b"}).success


def test_patch_verifier_nonexistent_file(tmp_path: Path):
    tool = PatchVerifierTool()
    res = tool.execute({"path": str(tmp_path / "missing.py"), "target": "old", "replacement": "new"})
    assert not res.success
    assert "not found" in res.error


def test_patch_verifier_clean_replacement(tmp_path: Path):
    p = tmp_path / "target.py"
    initial_content = "def hello():\n    return 'old'\n"
    p.write_text(initial_content, encoding="utf-8")

    tool = PatchVerifierTool()
    res = tool.execute({
        "path": str(p),
        "target": "return 'old'",
        "replacement": "return 'new'"
    })
    assert res.success
    assert "passed" in res.output.lower() and "valid" in res.output.lower()
    # File on disk MUST be untouched (dry-run!)
    assert p.read_text(encoding="utf-8") == initial_content


def test_patch_verifier_detects_broken_python_syntax(tmp_path: Path):
    p = tmp_path / "target.py"
    p.write_text("def hello():\n    return 'old'\n", encoding="utf-8")

    tool = PatchVerifierTool()
    res = tool.execute({
        "path": str(p),
        "target": "return 'old'",
        "replacement": "return 'new' broken syntax ("
    })
    assert not res.success
    assert "SyntaxError" in (res.error or "") or "SyntaxError" in (res.output or "")


# ============================================================================
# 4. TodoTool Exhaustive Matrix
# ============================================================================

def test_todo_tool_scans_codebase_tags(tmp_path: Path):
    p1 = tmp_path / "service.py"
    p1.write_text(
        "# TODO: implement redis cache\n"
        "# FIXME: memory leak in socket connection\n"
        "# HACK: temporary bypass for auth\n"
        "# BUG: race condition on concurrent writes\n"
        "# NOTE: review before release\n",
        encoding="utf-8"
    )
    tool = TodoTool()
    res = tool.execute({"path": str(tmp_path), "tag": "ALL"})
    assert res.success
    assert "TODO" in res.output
    assert "FIXME" in res.output
    assert "BUG" in res.output


@pytest.mark.parametrize("filter_tag", ["TODO", "FIXME", "BUG", "HACK", "NOTE"])
def test_todo_tool_tag_filtering(tmp_path: Path, filter_tag: str):
    p = tmp_path / "code.py"
    p.write_text(
        f"# {filter_tag}: specific item\n# OTHER: ignore this\n",
        encoding="utf-8"
    )
    tool = TodoTool()
    res = tool.execute({"path": str(p), "tag": filter_tag})
    assert res.success
    assert filter_tag in res.output


def test_todo_tool_empty_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    tool = TodoTool()
    res = tool.execute({"path": str(empty_dir)})
    assert res.success
    assert "0" in res.output or "No TODO" in res.output or "found" in res.output


# ============================================================================
# 5. BenchmarkTool Exhaustive Matrix
# ============================================================================

def test_benchmark_missing_code():
    tool = BenchmarkTool()
    res = tool.execute({"code": ""})
    assert not res.success
    assert "No code snippet" in res.error


def test_benchmark_syntax_error():
    tool = BenchmarkTool()
    res = tool.execute({"code": "def broken(;"})
    assert not res.success
    assert "syntax error" in res.error.lower()


@pytest.mark.parametrize("iterations", [1, 5, 10])
def test_benchmark_execution_and_statistics(iterations: int):
    tool = BenchmarkTool()
    res = tool.execute({
        "code": "x = sum(i * 2 for i in range(100))",
        "iterations": iterations,
        "warmup": 1
    })
    assert res.success
    assert "mean" in res.output.lower()
    assert "iterations" in res.output.lower() or f"{iterations}" in res.output


# ============================================================================
# 6. Git Tools Matrix (Status, Diff, Log, Commit)
# ============================================================================

def test_git_tools_in_non_git_repo(tmp_path: Path):
    non_git = tmp_path / "plain_dir"
    non_git.mkdir()
    
    assert "not a git repository" in GitStatusTool().execute({"path": str(non_git)}).output.lower() or not GitStatusTool().execute({"path": str(non_git)}).success
    assert "not a git repository" in GitDiffTool().execute({"path": str(non_git)}).output.lower() or not GitDiffTool().execute({"path": str(non_git)}).success
    assert "not a git repository" in GitLogTool().execute({"path": str(non_git)}).output.lower() or not GitLogTool().execute({"path": str(non_git)}).success
    assert "not a git repository" in GitCommitTool().execute({"message": "test", "path": str(non_git)}).output.lower() or not GitCommitTool().execute({"message": "test", "path": str(non_git)}).success


def test_git_tools_lifecycle_in_initialized_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import shutil
    if not shutil.which("git"):
        pytest.skip("Git CLI binary not available in environment.")
    repo = tmp_path / "repo"
    repo.mkdir()
    # Initialize a clean git repo
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Prubeth Tester"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@prubeth.ai"], cwd=str(repo), check=True)
    monkeypatch.chdir(repo)

    # 1. Status on empty repo
    status_tool = GitStatusTool()
    res_status = status_tool.execute({})
    assert res_status.success

    # 2. Add a file
    test_file = repo / "hello.txt"
    test_file.write_text("initial line\n", encoding="utf-8")

    # 3. Commit the file
    subprocess.run(["git", "add", "hello.txt"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo), check=True)

    # 4. Modify file and check Diff
    test_file.write_text("initial line\nsecond line added\n", encoding="utf-8")
    diff_tool = GitDiffTool()
    res_diff = diff_tool.execute({})
    assert res_diff.success
    assert "+second line added" in res_diff.output

    # 5. Check Log
    log_tool = GitLogTool()
    res_log = log_tool.execute({})
    assert res_log.success
    assert "Initial commit" in res_log.output
