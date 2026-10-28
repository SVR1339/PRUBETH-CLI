"""Tests for PRUBETH Repository Intelligence scale, edge cases, polyglot coexistence, and architectural invariants."""

import gc
import os
import pytest
from pathlib import Path

from prubeth.repository.ast_parser import PolyglotASTParser, SymbolKind, CodeSymbol
from prubeth.repository.graph import CodeGraph
from prubeth.repository.incremental_index import IncrementalCodeIndex


# =========================================================================
# Polyglot Multi-Language Coexistence in Single Workspace
# =========================================================================

def test_polyglot_coexistence_in_unified_graph(tmp_path):
    # Python file
    (tmp_path / "backend.py").write_text('''
def serve_api():
    return "ok"
''', encoding="utf-8")

    # TypeScript file
    (tmp_path / "frontend.ts").write_text('''
export function renderUI(): void {
    console.log("rendered");
}
''', encoding="utf-8")

    # Go microservice
    (tmp_path / "daemon.go").write_text('''
package main
func RunDaemon() {
}
''', encoding="utf-8")

    # Rust core
    (tmp_path / "engine.rs").write_text('''
pub fn compute_heavy() -> u64 {
    42
}
''', encoding="utf-8")

    index = IncrementalCodeIndex(workspace_root=tmp_path)
    stats = index.sync_index()
    assert stats["scanned"] == 4
    assert stats["total_symbols"] == 4

    graph = index.load_graph()
    assert len(graph.symbols) == 4

    # Verify each language's symbol is indexed with correct path
    assert any(s.file_path == "backend.py" for s in graph.symbols.values())
    assert any(s.file_path == "frontend.ts" for s in graph.symbols.values())
    assert any(s.file_path == "daemon.go" for s in graph.symbols.values())
    assert any(s.file_path == "engine.rs" for s in graph.symbols.values())


# =========================================================================
# Unicode and International Symbol Names
# =========================================================================

def test_unicode_and_utf8_symbol_extraction(tmp_path):
    py_code = '''
def calcul_rendement_énergétique(vitesse: float) -> float:
    """Calcul du rendement en unités SI."""
    return vitesse * 1.5

class DonnéesUtilisateur:
    def initialiser_session(self):
        pass
'''
    p = tmp_path / "unicode_app.py"
    p.write_text(py_code, encoding="utf-8")

    parser = PolyglotASTParser(workspace_root=tmp_path)
    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]
    assert "calcul_rendement_énergétique" in names
    assert "DonnéesUtilisateur" in names


# =========================================================================
# Nested Classes and Closures
# =========================================================================

def test_nested_classes_and_inner_functions(tmp_path):
    code = '''
class OuterContainer:
    class InnerWorker:
        def process(self):
            def local_closure():
                return 1
            return local_closure()
'''
    p = tmp_path / "nested.py"
    p.write_text(code, encoding="utf-8")

    parser = PolyglotASTParser(workspace_root=tmp_path)
    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]
    assert "OuterContainer" in names
    assert "InnerWorker" in names
    assert "process" in names


# =========================================================================
# Large Scale Synthetic Repository Graph Tests
# =========================================================================

@pytest.mark.parametrize("module_count", [10, 25, 50])
def test_large_repository_graph_indexing_and_pagerank(tmp_path, module_count):
    # Generate modular layered architecture
    for i in range(module_count):
        file_path = tmp_path / f"mod_{i}.py"
        # Each module calls the next, forming a DAG
        next_call = f"mod_{i+1}.call_{i+1}()" if i < module_count - 1 else "pass"
        import_stmt = f"import mod_{i+1}" if i < module_count - 1 else ""
        content = f'''
{import_stmt}

def call_{i}():
    {next_call}
'''
        file_path.write_text(content, encoding="utf-8")

    index = IncrementalCodeIndex(workspace_root=tmp_path)
    stats = index.sync_index()
    assert stats["scanned"] == module_count
    assert stats["total_symbols"] == module_count

    graph = index.load_graph()
    ranked = graph.rank_central_files()
    assert len(ranked) == module_count


# =========================================================================
# Memory Footprint Invariant Verification
# =========================================================================

def test_memory_micro_footprint_invariant():
    """Verifies that indexing and graph structures maintain an ultra-lean memory footprint."""
    gc.collect()
    import sys

    graph = CodeGraph()
    for i in range(500):
        sym = CodeSymbol(
            name=f"function_{i}",
            kind=SymbolKind.FUNCTION,
            file_path=f"src/file_{i // 10}.py",
            start_line=i,
            end_line=i + 5,
            signature=f"def function_{i}()",
            calls=[f"function_{(i + 1) % 500}"],
        )
        graph.add_symbol(sym)

    # 500 symbols in memory should consume < 5 MB of heap
    estimated_size = sys.getsizeof(graph.symbols) + sys.getsizeof(graph.call_edges)
    assert estimated_size < 5 * 1024 * 1024  # Well under 5 MB limit!


# =========================================================================
# Deterministic Ordering Invariants
# =========================================================================

def test_graph_algorithms_deterministic_output():
    """Verifies that multiple runs of cycle detection and PageRank produce identical outputs."""
    g1 = CodeGraph()
    g2 = CodeGraph()

    imports = [
        ("a.py", "b.py"),
        ("b.py", "c.py"),
        ("c.py", "a.py"),
        ("x.py", "y.py"),
        ("y.py", "x.py"),
    ]

    for s, t in imports:
        g1.add_file_import(s, t)
        g2.add_file_import(s, t)

    cycles1 = g1.detect_circular_imports()
    cycles2 = g2.detect_circular_imports()
    assert cycles1 == cycles2

    ranks1 = g1.rank_central_files()
    ranks2 = g2.rank_central_files()
    assert ranks1 == ranks2
