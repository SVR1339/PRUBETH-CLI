"""Tests for CodebaseTopologyMapper architectural analysis across workspace structures."""

import pytest
from pathlib import Path
from prubeth.repository.topology import CodebaseTopologyMapper


@pytest.fixture
def topology_workspace(tmp_path):
    """Sets up a multi-tiered repository for topology analysis."""
    # 1. Entrypoints
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "index.ts").write_text("console.log('web');\n", encoding="utf-8")

    # 2. Modules
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "service.py").write_text("class Service:\n    pass\n", encoding="utf-8")
    (src / "utils.ts").write_text("export function helper() {}\n", encoding="utf-8")

    # 3. Tests
    tests = tmp_path / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_service.py").write_text("def test_one():\n    assert True\n", encoding="utf-8")

    # 4. Ignored directories (must not appear in scan)
    ignored = tmp_path / "node_modules" / "pkg"
    ignored.mkdir(parents=True, exist_ok=True)
    (ignored / "index.js").write_text("module.exports = {};\n", encoding="utf-8")

    return tmp_path


def test_topology_mapper_baseline_categorisation(topology_workspace):
    mapper = CodebaseTopologyMapper(workspace_root=topology_workspace)
    data = mapper.scan_workspace()

    assert data["total_files"] == 5  # main.py, index.ts, service.py, utils.ts, test_service.py (node_modules ignored!)
    assert data["test_file_count"] == 1
    assert data["test_ratio"] > 0

    files = data["files"]
    entrypoints = [f for f in files if f["category"] == "entrypoint"]
    tests = [f for f in files if f["category"] == "test"]
    modules = [f for f in files if f["category"] == "module"]

    assert len(entrypoints) == 2  # main.py and index.ts
    assert len(tests) == 1        # test_service.py
    assert len(modules) == 2      # service.py and utils.ts


# =========================================================================
# Topology Scan Scale Permutations (N files across categories)
# =========================================================================

SCALE_PERMUTATIONS = [
    (10, 2),
    (20, 5),
    (30, 8),
]

@pytest.mark.parametrize("module_count,test_count", SCALE_PERMUTATIONS)
def test_topology_scale_permutations(tmp_path, module_count, test_count):
    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)

    for i in range(module_count):
        (src / f"mod_{i}.py").write_text(f"def func_{i}():\n    pass\n", encoding="utf-8")

    for j in range(test_count):
        (tests / f"test_mod_{j}.py").write_text(f"def test_{j}():\n    assert True\n", encoding="utf-8")

    mapper = CodebaseTopologyMapper(workspace_root=tmp_path)
    data = mapper.scan_workspace()

    assert data["total_files"] == module_count + test_count
    assert data["test_file_count"] == test_count
    assert data["test_ratio"] > 0
    assert "Python" in data["languages"] or "python" in data["languages"].keys()
