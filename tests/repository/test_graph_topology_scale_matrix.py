"""Tests for Graph Topology Scale Matrices across DAGs, cycles, bipartite graphs, and PageRank."""

import pytest
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind
from prubeth.repository.graph import CodeGraph


# =========================================================================
# Disconnected Graph Components PageRank Tests
# =========================================================================

@pytest.mark.parametrize("cluster_count", [2, 3, 5])
def test_pagerank_disconnected_components(cluster_count):
    graph = CodeGraph()
    # Create N independent 3-node cycles
    for c in range(cluster_count):
        a = f"c{c}_a.py"
        b = f"c{c}_b.py"
        c_node = f"c{c}_c.py"
        graph.add_file_import(a, b)
        graph.add_file_import(b, c_node)
        graph.add_file_import(c_node, a)

    ranked = graph.rank_central_files()
    assert len(ranked) == cluster_count * 3
    # Symmetrical clusters must have identical scores across nodes
    first_score = ranked[0][1]
    last_score = ranked[-1][1]
    assert abs(first_score - last_score) < 0.01


# =========================================================================
# Complete Bipartite Graph Matrix (Clients -> Services)
# =========================================================================

BIPARTITE_SIZES = [(3, 2), (5, 3), (8, 4)]

@pytest.mark.parametrize("clients,services", BIPARTITE_SIZES)
def test_bipartite_client_service_pagerank(clients, services):
    graph = CodeGraph()
    # All clients import all services
    for c in range(clients):
        for s in range(services):
            graph.add_file_import(f"client_{c}.py", f"service_{s}.py")

    ranked = graph.rank_central_files()
    assert len(ranked) == clients + services

    # Services must strictly outrank clients because services have in-degree > 0
    service_scores = [score for f, score in ranked if f.startswith("service_")]
    client_scores = [score for f, score in ranked if f.startswith("client_")]

    assert min(service_scores) > max(client_scores)


# =========================================================================
# Cycle Permutation Matrix (Sizes 2 to 20)
# =========================================================================

CYCLE_SIZES = list(range(2, 21))

@pytest.mark.parametrize("cycle_len", CYCLE_SIZES)
def test_cycle_matrix_detection(cycle_len):
    graph = CodeGraph()
    for i in range(cycle_len):
        nxt = (i + 1) % cycle_len
        graph.add_file_import(f"step_{i}.py", f"step_{nxt}.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 1
    assert len(cycles[0]) == cycle_len + 1


# =========================================================================
# Deep Call Chain Traversal Matrix
# =========================================================================

CHAIN_DEPTHS = [5, 10, 15, 20]

@pytest.mark.parametrize("chain_len", CHAIN_DEPTHS)
def test_deep_call_chain_traversal(chain_len):
    graph = CodeGraph()
    for i in range(chain_len - 1):
        sym = CodeSymbol(
            name=f"node_{i}",
            kind=SymbolKind.FUNCTION,
            file_path=f"mod_{i}.py",
            start_line=1,
            end_line=5,
            signature=f"def node_{i}()",
            calls=[f"node_{i+1}"],
        )
        graph.add_symbol(sym)

    terminal = CodeSymbol(
        name=f"node_{chain_len-1}",
        kind=SymbolKind.FUNCTION,
        file_path=f"mod_{chain_len-1}.py",
        start_line=1,
        end_line=5,
        signature=f"def node_{chain_len-1}()",
        calls=[],
    )
    graph.add_symbol(terminal)

    # Forward trace
    fwd = graph.trace_data_flow("node_0", max_depth=chain_len, direction="forward")
    assert fwd["name"] == "node_0"

    # Backward trace from terminal
    bwd = graph.trace_data_flow(f"node_{chain_len-1}", max_depth=chain_len, direction="backward")
    assert bwd["name"] == f"node_{chain_len-1}"


# =========================================================================
# Diamond Dependency Graph (A -> B, A -> C, B -> D, C -> D)
# =========================================================================

def test_diamond_dependency_graph():
    graph = CodeGraph()
    graph.add_file_import("app.py", "service_b.py")
    graph.add_file_import("app.py", "service_c.py")
    graph.add_file_import("service_b.py", "db_kernel.py")
    graph.add_file_import("service_c.py", "db_kernel.py")

    # Diamond has no circular imports
    assert graph.detect_circular_imports() == []

    # db_kernel is imported by both B and C, so it should rank at the top
    ranks = graph.rank_central_files()
    top_file, _ = ranks[0]
    assert top_file == "db_kernel.py"


# =========================================================================
# Multi-Cycle Intersecting Graph Matrix
# =========================================================================

def test_figure_eight_intersecting_cycles():
    graph = CodeGraph()
    # Left loop: a -> b -> hub -> a
    graph.add_file_import("left_a.py", "left_b.py")
    graph.add_file_import("left_b.py", "hub.py")
    graph.add_file_import("hub.py", "left_a.py")

    # Right loop: right_x -> right_y -> hub -> right_x
    graph.add_file_import("right_x.py", "right_y.py")
    graph.add_file_import("right_y.py", "hub.py")
    graph.add_file_import("hub.py", "right_x.py")

    cycles = graph.detect_circular_imports()
    # Expect at least both cycles detected
    assert len(cycles) >= 2
    assert any("left_a.py" in c for c in cycles)
    assert any("right_x.py" in c for c in cycles)
