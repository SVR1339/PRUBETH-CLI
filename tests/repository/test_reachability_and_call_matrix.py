"""Tests for CodeGraph Transitive Closures, Reachability Matrices, and Multi-Level Invocations."""

import pytest
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind
from prubeth.repository.graph import CodeGraph


# =========================================================================
# Transitive Callee Set Computation Tests
# =========================================================================

def compute_transitive_callees(graph: CodeGraph, root: str) -> set:
    """Helper computing full transitive callee reachability set using BFS."""
    visited = set()
    queue = [root]
    while queue:
        curr = queue.pop(0)
        callees = graph.find_callees(curr)
        for c in callees:
            target = c["callee_name"]
            if target not in visited:
                visited.add(target)
                queue.append(target)
    return visited


def compute_transitive_callers(graph: CodeGraph, target_name: str) -> set:
    """Helper computing full transitive caller reachability set using BFS."""
    visited = set()
    queue = [target_name]
    while queue:
        curr = queue.pop(0)
        callers = graph.find_callers(curr)
        for c in callers:
            if c.name not in visited:
                visited.add(c.name)
                queue.append(c.name)
    return visited


# =========================================================================
# Linear Chain Transitive Reachability Matrix
# =========================================================================

LINEAR_REACHABILITY_SIZES = [3, 5, 10, 15]

@pytest.mark.parametrize("length", LINEAR_REACHABILITY_SIZES)
def test_linear_chain_reachability_matrix(length):
    graph = CodeGraph()
    for i in range(length - 1):
        sym = CodeSymbol(
            name=f"step_{i}",
            kind=SymbolKind.FUNCTION,
            file_path=f"step_{i}.py",
            start_line=1,
            end_line=5,
            signature=f"def step_{i}()",
            calls=[f"step_{i+1}"],
        )
        graph.add_symbol(sym)

    last_sym = CodeSymbol(
        name=f"step_{length-1}",
        kind=SymbolKind.FUNCTION,
        file_path=f"step_{length-1}.py",
        start_line=1,
        end_line=5,
        signature=f"def step_{length-1}()",
        calls=[],
    )
    graph.add_symbol(last_sym)

    # Transitive callees from root must include all subsequent steps
    callees = compute_transitive_callees(graph, "step_0")
    assert len(callees) == length - 1
    for k in range(1, length):
        assert f"step_{k}" in callees

    # Transitive callers of terminal must include all preceding steps
    callers = compute_transitive_callers(graph, f"step_{length-1}")
    assert len(callers) == length - 1
    for k in range(length - 1):
        assert f"step_{k}" in callers


# =========================================================================
# Binary Call Tree Reachability Matrix
# =========================================================================

TREE_DEPTHS = [2, 3, 4]

@pytest.mark.parametrize("depth", TREE_DEPTHS)
def test_binary_call_tree_reachability(depth):
    graph = CodeGraph()
    total_nodes = (2 ** depth) - 1

    for i in range(total_nodes):
        left_child = 2 * i + 1
        right_child = 2 * i + 2
        calls = []
        if left_child < total_nodes:
            calls.append(f"tree_node_{left_child}")
        if right_child < total_nodes:
            calls.append(f"tree_node_{right_child}")

        sym = CodeSymbol(
            name=f"tree_node_{i}",
            kind=SymbolKind.FUNCTION,
            file_path=f"tree_{i}.py",
            start_line=1,
            end_line=5,
            signature=f"def tree_node_{i}()",
            calls=calls,
        )
        graph.add_symbol(sym)

    # All nodes except root must be in root's transitive callee set
    callees = compute_transitive_callees(graph, "tree_node_0")
    assert len(callees) == total_nodes - 1


# =========================================================================
# Mutual Recursion and Cycle Reachability Tests
# =========================================================================

MUTUAL_RECURSION_PAIRS = [
    (f"rec_a_{i}", f"rec_b_{i}")
    for i in range(25)
]

@pytest.mark.parametrize("fn_a,fn_b", MUTUAL_RECURSION_PAIRS)
def test_mutual_recursion_reachability(fn_a, fn_b):
    graph = CodeGraph()
    sym_a = CodeSymbol(
        name=fn_a,
        kind=SymbolKind.FUNCTION,
        file_path="rec.py",
        start_line=1,
        end_line=5,
        signature=f"def {fn_a}()",
        calls=[fn_b],
    )
    sym_b = CodeSymbol(
        name=fn_b,
        kind=SymbolKind.FUNCTION,
        file_path="rec.py",
        start_line=6,
        end_line=10,
        signature=f"def {fn_b}()",
        calls=[fn_a],
    )
    graph.add_symbol(sym_a)
    graph.add_symbol(sym_b)

    # Mutual recursion must terminate cleanly without infinite loop
    callees_a = compute_transitive_callees(graph, fn_a)
    assert fn_b in callees_a

    callees_b = compute_transitive_callees(graph, fn_b)
    assert fn_a in callees_b


# =========================================================================
# Dense Fan-Out Reachability Matrix
# =========================================================================

FAN_OUT_WIDTHS = [5, 10, 25, 50]

@pytest.mark.parametrize("width", FAN_OUT_WIDTHS)
def test_dense_fan_out_reachability(width):
    graph = CodeGraph()
    worker_names = [f"worker_task_{w}" for w in range(width)]

    dispatcher = CodeSymbol(
        name="dispatch_all",
        kind=SymbolKind.FUNCTION,
        file_path="dispatch.py",
        start_line=1,
        end_line=5,
        signature="def dispatch_all()",
        calls=worker_names,
    )
    graph.add_symbol(dispatcher)

    for w_name in worker_names:
        worker = CodeSymbol(
            name=w_name,
            kind=SymbolKind.FUNCTION,
            file_path=f"{w_name}.py",
            start_line=1,
            end_line=5,
            signature=f"def {w_name}()",
            calls=[],
        )
        graph.add_symbol(worker)

    callees = compute_transitive_callees(graph, "dispatch_all")
    assert len(callees) == width
    for w in worker_names:
        assert w in callees
