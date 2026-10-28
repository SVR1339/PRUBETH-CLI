"""Tests verifying Phase 2 repository intelligence invariants, mathematical guarantees, and brand rules."""

import os
from pathlib import Path
import pytest
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind, PolyglotASTParser
from prubeth.repository.graph import CodeGraph
from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.tools.registry import get_default_registry


# =========================================================================
# Brand and Language Invariant Tests
# =========================================================================

def test_strictly_no_forbidden_word_in_repository_subsystem():
    """Validates that the forbidden word never appears in any repository files or docstrings."""
    forbidden = "sover" + "eign"
    repo_dir = Path(__file__).resolve().parent.parent.parent / "src" / "prubeth" / "repository"

    for py_file in repo_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore").lower()
        assert forbidden not in content, f"Forbidden word found in {py_file.name}!"


def test_strictly_no_forbidden_word_in_intelligence_tools():
    """Validates that the forbidden word never appears in any intelligence tools."""
    forbidden = "sover" + "eign"
    tools_dir = Path(__file__).resolve().parent.parent.parent / "src" / "prubeth" / "tools" / "intelligence"

    for py_file in tools_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore").lower()
        assert forbidden not in content, f"Forbidden word found in {py_file.name}!"


# =========================================================================
# PageRank Normalisation and Convergence Invariant Matrix (50 Topologies)
# =========================================================================

PAGERANK_TEST_SIZES = list(range(3, 53))

@pytest.mark.parametrize("n", PAGERANK_TEST_SIZES)
def test_pagerank_probability_conservation_matrix(n):
    graph = CodeGraph()
    # Create directed path with cycle return
    for i in range(n):
        nxt = (i + 1) % n
        graph.add_file_import(f"node_{i}.py", f"node_{nxt}.py")

    ranks = graph.rank_central_files(damping=0.85, max_iterations=50)
    assert len(ranks) == n
    total = sum(score for _, score in ranks)
    assert 0.95 <= total <= 1.05
    # Symmetry: in a ring of size N, every node must have equal centrality
    scores = [s for _, s in ranks]
    assert max(scores) - min(scores) < 1e-4


# =========================================================================
# Full Registry Inventory Invariants
# =========================================================================

def test_tool_registry_contains_25_tools():
    reg = get_default_registry()
    assert len(reg) >= 25
    assert reg.has("code_structure")
    assert reg.has("find_callers")
    assert reg.has("find_callees")
    assert reg.has("find_type_definition")
    assert reg.has("find_implementations")
    assert reg.has("detect_circular_imports")
    assert reg.has("trace_data_flow")
    assert reg.has("find_dead_code")
    assert reg.has("rank_central_files")
    assert reg.has("explain_symbol")
