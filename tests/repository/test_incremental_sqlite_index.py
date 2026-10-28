"""Tests for PRUBETH Incremental Git-Aware SQLite Symbol Indexer."""

import time
import pytest
from pathlib import Path
from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.repository.ast_parser import SymbolKind


@pytest.fixture
def repo_env(tmp_path):
    """Sets up a temporary repository directory with initial code files."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)

    # 1. Auth module
    (src / "auth.py").write_text('''
def authenticate(token: str) -> bool:
    """Verifies JWT auth token."""
    return len(token) > 10

class AuthManager:
    def __init__(self, secret: str):
        self.secret = secret

    def login(self, user: str) -> bool:
        return True
''', encoding="utf-8")

    # 2. Main controller
    (src / "main.py").write_text('''
from src.auth import authenticate, AuthManager

def run():
    auth = AuthManager("secret")
    return auth.login("developer")
''', encoding="utf-8")

    return tmp_path


def test_sqlite_index_initial_creation_and_sync(repo_env):
    index = IncrementalCodeIndex(workspace_root=repo_env)
    assert index.db_path.is_file()

    stats = index.sync_index()
    assert stats["scanned"] == 2
    assert stats["added"] == 2
    assert stats["modified"] == 0
    assert stats["deleted"] == 0
    assert stats["unchanged"] == 0
    assert stats["total_symbols"] >= 4  # authenticate, AuthManager, __init__, login, run


def test_sqlite_index_subsequent_sync_skips_unchanged(repo_env):
    index = IncrementalCodeIndex(workspace_root=repo_env)
    index.sync_index()

    # Second sync without any changes
    stats2 = index.sync_index()
    assert stats2["scanned"] == 2
    assert stats2["added"] == 0
    assert stats2["modified"] == 0
    assert stats2["deleted"] == 0
    assert stats2["unchanged"] == 2
    assert stats2["elapsed_ms"] < 200.0  # sub-second caching


def test_sqlite_index_incremental_modification(repo_env):
    index = IncrementalCodeIndex(workspace_root=repo_env)
    index.sync_index()

    # Modify auth.py
    time.sleep(0.01)
    auth_file = repo_env / "src" / "auth.py"
    content = auth_file.read_text(encoding="utf-8")
    auth_file.write_text(content + "\ndef logout():\n    return True\n", encoding="utf-8")

    stats = index.sync_index()
    assert stats["modified"] == 1
    assert stats["unchanged"] == 1
    assert stats["added"] == 0
    assert stats["deleted"] == 0

    # Verify new symbol exists in index
    results = index.search_symbols("logout")
    assert len(results) == 1
    assert results[0].name == "logout"
    assert results[0].kind == SymbolKind.FUNCTION


def test_sqlite_index_deletion_pruning(repo_env):
    index = IncrementalCodeIndex(workspace_root=repo_env)
    index.sync_index()

    # Delete main.py
    main_file = repo_env / "src" / "main.py"
    main_file.unlink()

    stats = index.sync_index()
    assert stats["deleted"] == 1
    assert stats["scanned"] == 1

    # Verify deleted symbols are removed
    assert index.search_symbols("run") == []


def test_sqlite_index_search_symbols_and_filtering(repo_env):
    index = IncrementalCodeIndex(workspace_root=repo_env)
    index.sync_index()

    # Search by exact name
    auth_syms = index.search_symbols("AuthManager")
    assert len(auth_syms) == 1
    assert auth_syms[0].kind == SymbolKind.CLASS

    # Filter by kind
    class_syms = index.search_symbols("", kind="class")
    assert any(s.name == "AuthManager" for s in class_syms)
    assert not any(s.name == "authenticate" for s in class_syms)

    # Search with limit
    limited = index.search_symbols("", limit=2)
    assert len(limited) <= 2


def test_sqlite_index_get_file_symbols(repo_env):
    index = IncrementalCodeIndex(workspace_root=repo_env)
    index.sync_index()

    symbols = index.get_file_symbols("src/auth.py")
    assert len(symbols) >= 3
    # Check start_line ordering
    for i in range(len(symbols) - 1):
        assert symbols[i].start_line <= symbols[i + 1].start_line


def test_sqlite_index_load_graph_reconstruction(repo_env):
    index = IncrementalCodeIndex(workspace_root=repo_env)
    index.sync_index()

    graph = index.load_graph()
    assert len(graph.symbols) >= 4
    # Check that callers and callees can be queried from the reconstructed graph
    assert graph.find_type_definition("AuthManager") != []


# =========================================================================
# Polyglot Multi-File Stress Test
# =========================================================================

@pytest.mark.parametrize("file_count", [5, 15, 25])
def test_polyglot_incremental_indexing_scale(tmp_path, file_count):
    for i in range(file_count):
        # Python
        (tmp_path / f"service_{i}.py").write_text(f"def serve_{i}():\n    return {i}\n", encoding="utf-8")
        # TypeScript
        (tmp_path / f"handler_{i}.ts").write_text(f"export function handle_{i}(): number {{\n    return {i};\n}}\n", encoding="utf-8")
        # Go
        (tmp_path / f"worker_{i}.go").write_text(f"package worker\nfunc Work_{i}() {{\n}}\n", encoding="utf-8")

    index = IncrementalCodeIndex(workspace_root=tmp_path)
    stats = index.sync_index()
    assert stats["scanned"] == file_count * 3
    assert stats["added"] == file_count * 3
    assert stats["total_symbols"] == file_count * 3
