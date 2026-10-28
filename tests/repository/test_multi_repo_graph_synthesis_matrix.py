"""Tests for Monorepo Package Graphs, Critical Path Analysis, and Namespace Disambiguation."""

import pytest
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind
from prubeth.repository.graph import CodeGraph


# =========================================================================
# Monorepo Subpackage Architecture Graph
# =========================================================================

def test_monorepo_multi_package_inter_dependencies():
    graph = CodeGraph()

    # Package 1: packages/core
    sym_core = CodeSymbol(
        name="core_kernel",
        kind=SymbolKind.FUNCTION,
        file_path="packages/core/src/kernel.py",
        start_line=1,
        end_line=10,
        signature="def core_kernel()",
    )
    graph.add_symbol(sym_core)

    # Package 2: packages/client (imports core)
    sym_client = CodeSymbol(
        name="api_client",
        kind=SymbolKind.FUNCTION,
        file_path="packages/client/src/client.py",
        start_line=1,
        end_line=15,
        signature="def api_client()",
        calls=["core_kernel"],
    )
    graph.add_symbol(sym_client)
    graph.add_file_import("packages/client/src/client.py", "packages/core/src/kernel.py")

    # Package 3: packages/cli (imports client)
    sym_cli = CodeSymbol(
        name="cli_entry",
        kind=SymbolKind.FUNCTION,
        file_path="packages/cli/src/main.py",
        start_line=1,
        end_line=20,
        signature="def cli_entry()",
        calls=["api_client"],
    )
    graph.add_symbol(sym_cli)
    graph.add_file_import("packages/cli/src/main.py", "packages/client/src/client.py")

    # Verify cross-package caller resolution
    core_callers = graph.find_callers("core_kernel")
    assert len(core_callers) == 1
    assert core_callers[0].file_path == "packages/client/src/client.py"

    client_callers = graph.find_callers("api_client")
    assert len(client_callers) == 1
    assert client_callers[0].file_path == "packages/cli/src/main.py"

    # Verify PageRank architectural ranking in monorepo
    ranks = graph.rank_central_files()
    assert ranks[0][0] == "packages/core/src/kernel.py"


# =========================================================================
# Namespace Disambiguation Matrix (Same Symbol Name across 25 Modules)
# =========================================================================

SHADOW_MODULES = [f"module_{i}" for i in range(25)]

@pytest.mark.parametrize("mod", SHADOW_MODULES)
def test_symbol_shadowing_disambiguation(mod):
    graph = CodeGraph()
    # Add identical symbol name in 25 different modules
    for m in SHADOW_MODULES:
        sym = CodeSymbol(
            name="initialise_context",
            kind=SymbolKind.FUNCTION,
            file_path=f"src/{m}/context.py",
            start_line=10,
            end_line=20,
            signature="def initialise_context()",
        )
        graph.add_symbol(sym)

    # find_type_definition should return all 25 distinct occurrences
    defs = graph.find_type_definition("initialise_context")
    assert len(defs) == 25
    paths = [d.file_path for d in defs]
    assert f"src/{mod}/context.py" in paths


# =========================================================================
# Critical Path Longest Chain Matrix
# =========================================================================

def compute_critical_path_length(graph: CodeGraph, start_file: str) -> int:
    """Computes the length of the longest dependency path from start_file using memoized DFS."""
    memo = {}

    def dfs(node: str) -> int:
        if node in memo:
            return memo[node]
        neighbors = graph.file_imports.get(node, set())
        if not neighbors:
            return 1
        max_child = max(dfs(nbr) for nbr in neighbors)
        memo[node] = 1 + max_child
        return memo[node]

    return dfs(start_file)


CRITICAL_PATH_SIZES = [5, 10, 15, 20]

@pytest.mark.parametrize("depth", CRITICAL_PATH_SIZES)
def test_critical_path_dependency_depth(depth):
    graph = CodeGraph()
    for i in range(depth - 1):
        graph.add_file_import(f"layer_{i}.py", f"layer_{i+1}.py")

    path_len = compute_critical_path_length(graph, "layer_0.py")
    assert path_len == depth


# =========================================================================
# Scale Tree Hierarchy Matrix
# =========================================================================

HIERARCHY_LEVELS = [
    (1, 4),
    (2, 8),
    (3, 12),
    (4, 16),
]

@pytest.mark.parametrize("tier,width", HIERARCHY_LEVELS)
def test_multi_tier_hierarchy_resolution(tier, width):
    graph = CodeGraph()
    base_class = CodeSymbol(
        name=f"BaseEngine_T{tier}",
        kind=SymbolKind.CLASS,
        file_path=f"tier_{tier}/base.py",
        start_line=1,
        end_line=10,
        signature=f"class BaseEngine_T{tier}",
    )
    graph.add_symbol(base_class)

    for w in range(width):
        derived = CodeSymbol(
            name=f"Derived_T{tier}_W{w}",
            kind=SymbolKind.CLASS,
            file_path=f"tier_{tier}/worker_{w}.py",
            start_line=1,
            end_line=20,
            signature=f"class Derived_T{tier}_W{w}(BaseEngine_T{tier})",
            bases=[f"BaseEngine_T{tier}"],
        )
        graph.add_symbol(derived)

    implementations = graph.find_implementations(f"BaseEngine_T{tier}")
    assert len(implementations) == width


# =========================================================================
# Multiple Callers to Common Utility Scale Matrix
# =========================================================================

UTILITY_CALLER_SIZES = [10, 25, 50]

@pytest.mark.parametrize("callers_count", UTILITY_CALLER_SIZES)
def test_utility_callers_scale_matrix(callers_count):
    graph = CodeGraph()
    util = CodeSymbol(
        name="shared_logger",
        kind=SymbolKind.FUNCTION,
        file_path="src/log.py",
        start_line=1,
        end_line=5,
        signature="def shared_logger(msg: str)",
    )
    graph.add_symbol(util)

    for i in range(callers_count):
        caller = CodeSymbol(
            name=f"subsystem_worker_{i}",
            kind=SymbolKind.FUNCTION,
            file_path=f"src/sub_{i}.py",
            start_line=1,
            end_line=10,
            signature=f"def subsystem_worker_{i}()",
            calls=["shared_logger"],
        )
        graph.add_symbol(caller)

    recorded_callers = graph.find_callers("shared_logger")
    assert len(recorded_callers) == callers_count


# =========================================================================
# Circular Import Self-Loop Edge Cases
# =========================================================================

def test_self_import_loop_detected():
    graph = CodeGraph()
    # A file importing itself
    graph.add_file_import("self_loop.py", "self_loop.py")
    cycles = graph.detect_circular_imports()
    assert len(cycles) == 1
    assert cycles[0] == ["self_loop.py", "self_loop.py"]


# =========================================================================
# Empty Graph Call Query Edge Cases
# =========================================================================

@pytest.mark.parametrize("query", ["", "nonexistent", "___", "123", "!@#"])
def test_empty_graph_queries_return_empty(query):
    graph = CodeGraph()
    assert graph.find_callers(query) == []
    assert graph.find_callees(query) == []
    assert graph.find_implementations(query) == []
    assert graph.find_type_definition(query) == []
