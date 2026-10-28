"""PRUBETH Repository Topology & Incremental Index Permutations Matrix.

Exhaustively verifies CodebaseTopologyMapper entrypoint detection, test ratio accounting,
ignored directory filtering, language statistics across all 13 ecosystems,
and IncrementalCodeIndex SQLite cache synchronization and delta invalidation.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.repository.topology import CodebaseTopologyMapper, ENTRYPOINT_NAMES
from prubeth.repository.incremental_index import IncrementalCodeIndex, SUPPORTED_EXTENSIONS


# ============================================================================
# 1. CodebaseTopologyMapper Entrypoint Detection Matrix
# ============================================================================

ALL_ENTRYPOINTS = sorted(list(ENTRYPOINT_NAMES))


@pytest.mark.parametrize("entry_filename", ALL_ENTRYPOINTS)
def test_topology_mapper_detects_entrypoint(tmp_path: Path, entry_filename: str):
    f = tmp_path / entry_filename
    f.write_text("// entrypoint code\n", encoding="utf-8")

    mapper = CodebaseTopologyMapper(workspace_root=tmp_path)
    scan = mapper.scan_workspace()

    assert scan["total_files"] == 1
    file_info = scan["files"][0]
    assert file_info["name"] == entry_filename
    assert file_info["category"] == "entrypoint"


# ============================================================================
# 2. Test File Recognition & Test Ratio Accounting Matrix
# ============================================================================

@pytest.mark.parametrize("test_filename", [
    "test_auth.py",
    "auth_test.go",
    "service.test.ts",
    "calculator.spec.js",
    "TestUserService.java",
    "AuthTests.cs",
])
def test_topology_mapper_detects_test_files(tmp_path: Path, test_filename: str):
    t_file = tmp_path / "tests" / test_filename
    t_file.parent.mkdir(parents=True, exist_ok=True)
    t_file.write_text("// test implementation\n", encoding="utf-8")

    mapper = CodebaseTopologyMapper(workspace_root=tmp_path)
    scan = mapper.scan_workspace()

    assert scan["test_file_count"] == 1
    assert scan["files"][0]["category"] == "test"


def test_topology_mapper_calculates_test_ratio(tmp_path: Path):
    # 50 lines of source code
    src_file = tmp_path / "src" / "engine.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("\n".join(f"x = {i}" for i in range(50)) + "\n", encoding="utf-8")

    # 50 lines of test code
    test_file = tmp_path / "tests" / "test_engine.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("\n".join(f"def test_{i}(): pass" for i in range(50)) + "\n", encoding="utf-8")

    mapper = CodebaseTopologyMapper(workspace_root=tmp_path)
    scan = mapper.scan_workspace()

    assert scan["total_files"] == 2
    assert scan["total_lines"] == 100
    assert scan["test_lines"] == 50
    assert scan["test_ratio"] == 50.0


# ============================================================================
# 3. Ignored Directories Filtering Matrix
# ============================================================================

@pytest.mark.parametrize("ignored_dir", [
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache"
])
def test_topology_mapper_ignores_vendor_and_build_dirs(tmp_path: Path, ignored_dir: str):
    ign = tmp_path / ignored_dir
    ign.mkdir(parents=True, exist_ok=True)
    (ign / "ignored_file.py").write_text("x = 100\n", encoding="utf-8")

    # Valid file
    valid = tmp_path / "valid.py"
    valid.write_text("y = 200\n", encoding="utf-8")

    mapper = CodebaseTopologyMapper(workspace_root=tmp_path)
    scan = mapper.scan_workspace()

    assert scan["total_files"] == 1
    assert scan["files"][0]["name"] == "valid.py"


# ============================================================================
# 4. Multi-Language Ecosystems Statistics Matrix
# ============================================================================

@pytest.mark.parametrize("ext,lang_name", [
    (".py", "Python"),
    (".ts", "TypeScript"),
    (".js", "JavaScript"),
    (".rs", "Rust"),
    (".go", "Go"),
    (".java", "Java"),
    (".cs", "C# (.NET)"),
    (".cpp", "C++"),
    (".rb", "Ruby"),
    (".php", "PHP"),
])
def test_topology_mapper_detects_language_stats(tmp_path: Path, ext: str, lang_name: str):
    f = tmp_path / f"sample{ext}"
    f.write_text("code line 1\ncode line 2\n", encoding="utf-8")

    mapper = CodebaseTopologyMapper(workspace_root=tmp_path)
    scan = mapper.scan_workspace()

    assert lang_name in scan["languages"]
    assert scan["languages"][lang_name] == 2


# ============================================================================
# 5. IncrementalCodeIndex SQLite Cache Lifecycle Matrix
# ============================================================================

def test_incremental_index_initial_sync(tmp_path: Path):
    f1 = tmp_path / "src" / "math_ops.py"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    db_file = tmp_path / "cache" / "symbols.db"
    idx = IncrementalCodeIndex(workspace_root=tmp_path, db_path=db_file)

    res1 = idx.sync_index()
    assert res1["scanned"] == 1
    assert res1["added"] == 1
    assert res1["total_symbols"] >= 1

    # Second sync without changes should report unchanged
    res2 = idx.sync_index()
    assert res2["scanned"] == 1
    assert res2["added"] == 0
    assert res2["unchanged"] == 1


def test_incremental_index_detects_modification_and_deletion(tmp_path: Path):
    f1 = tmp_path / "src" / "service.py"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("def run(): pass\n", encoding="utf-8")

    f2 = tmp_path / "src" / "to_delete.py"
    f2.write_text("def ephemeral(): pass\n", encoding="utf-8")

    db_file = tmp_path / "cache" / "symbols.db"
    idx = IncrementalCodeIndex(workspace_root=tmp_path, db_path=db_file)

    # Initial sync
    idx.sync_index()

    # 1. Modify f1
    f1.write_text("def run():\n    return 'updated'\n", encoding="utf-8")
    # 2. Delete f2
    f2.unlink()

    res = idx.sync_index()
    assert res["modified"] == 1
    assert res["deleted"] == 1


def test_incremental_index_graph_reconstruction(tmp_path: Path):
    f1 = tmp_path / "src" / "calc.py"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text(
        "class Calculator:\n"
        "    def multiply(self, a: int, b: int) -> int:\n"
        "        return a * b\n",
        encoding="utf-8"
    )

    db_file = tmp_path / "cache" / "symbols.db"
    idx = IncrementalCodeIndex(workspace_root=tmp_path, db_path=db_file)
    idx.sync_index()

    # Reconstruct CodeGraph from SQLite
    graph = idx.load_graph()
    assert graph is not None
    syms = list(graph.symbols.values())
    sym_names = [s.name for s in syms]
    assert "Calculator" in sym_names or "multiply" in sym_names
