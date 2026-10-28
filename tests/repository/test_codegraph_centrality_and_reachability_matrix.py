"""PRUBETH Code Graph PageRank Centrality, Reachability & Cycle Detection Matrix.

Exhaustively verifies:
1. PageRank architectural centrality across star, chain, tree, and mesh graph topologies.
2. Damping factor and convergence tolerances in iterative power method.
3. DFS circular import detection with canonicalised cycle path representations.
4. Dead code identification with entrypoint, test suite, and dunder method exclusions.
5. Bidirectional data flow tracing (forward callees vs backward callers) across varied depths.
6. Class inheritance and interface implementation resolution hierarchies.
"""

from __future__ import annotations

import pytest
from prubeth.repository.graph import CodeGraph, GraphEdge
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind


# ============================================================================
# 1. PageRank Centrality: Star Topology (Hub & Spokes)
# ============================================================================

@pytest.mark.parametrize("spoke_count", [2, 3, 5, 8, 12, 16])
def test_pagerank_star_topology_hub_is_most_central(spoke_count: int):
    graph = CodeGraph()
    hub = "src/core/hub.py"
    for i in range(spoke_count):
        spoke = f"src/modules/spoke_{i}.py"
        # Spoke imports hub
        graph.add_file_import(spoke, hub)

    ranked = graph.rank_central_files(damping=0.85)
    assert len(ranked) == spoke_count + 1
    # Hub must be top-ranked with the highest PageRank score
    top_file, top_score = ranked[0]
    assert top_file == hub
    # Every spoke must have a lower score than the hub
    for f, score in ranked[1:]:
        assert score < top_score


# ============================================================================
# 2. PageRank Centrality: Linear Chain Hierarchy (A -> B -> C -> D)
# ============================================================================

@pytest.mark.parametrize("chain_length", [3, 4, 5, 7, 10])
def test_pagerank_linear_chain_sink_accumulates_rank(chain_length: int):
    graph = CodeGraph()
    files = [f"mod_{i}.py" for i in range(chain_length)]
    # mod_0 -> mod_1 -> ... -> mod_N-1
    for i in range(chain_length - 1):
        graph.add_file_import(files[i], files[i + 1])

    ranked = graph.rank_central_files(damping=0.85)
    assert len(ranked) == chain_length
    # In a directed pipeline A -> B -> C, the deepest sinks receive downstream rank
    scores_by_file = dict(ranked)
    assert scores_by_file[files[-1]] > scores_by_file[files[0]]


# ============================================================================
# 3. PageRank Damping Factor Permutations (0.10 to 0.95)
# ============================================================================

@pytest.mark.parametrize("damping", [0.10, 0.30, 0.50, 0.75, 0.85, 0.95])
def test_pagerank_damping_factors(damping: float):
    graph = CodeGraph()
    graph.add_file_import("a.py", "b.py")
    graph.add_file_import("c.py", "b.py")
    graph.add_file_import("b.py", "d.py")

    ranked = graph.rank_central_files(damping=damping)
    assert len(ranked) == 4
    # Total sum of PageRank scores across all nodes must be approx 1.0
    total_score = sum(s for _, s in ranked)
    assert pytest.approx(total_score, rel=1e-2) == 1.0


# ============================================================================
# 4. Circular Import Detection: 2-Cycle, 3-Cycle, 4-Cycle Permutations
# ============================================================================

def test_detect_2_cycle():
    graph = CodeGraph()
    graph.add_file_import("a.py", "b.py")
    graph.add_file_import("b.py", "a.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 1
    cycle = cycles[0]
    assert cycle == ["a.py", "b.py", "a.py"]


def test_detect_3_cycle():
    graph = CodeGraph()
    graph.add_file_import("a.py", "b.py")
    graph.add_file_import("b.py", "c.py")
    graph.add_file_import("c.py", "a.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 1
    assert cycles[0] == ["a.py", "b.py", "c.py", "a.py"]


def test_detect_4_cycle():
    graph = CodeGraph()
    graph.add_file_import("a.py", "b.py")
    graph.add_file_import("b.py", "c.py")
    graph.add_file_import("c.py", "d.py")
    graph.add_file_import("d.py", "a.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 1
    assert cycles[0] == ["a.py", "b.py", "c.py", "d.py", "a.py"]


def test_detect_multiple_disjoint_cycles():
    graph = CodeGraph()
    # Cycle 1: a -> b -> a
    graph.add_file_import("a.py", "b.py")
    graph.add_file_import("b.py", "a.py")
    # Cycle 2: x -> y -> z -> x
    graph.add_file_import("x.py", "y.py")
    graph.add_file_import("y.py", "z.py")
    graph.add_file_import("z.py", "x.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 2


def test_detect_dag_has_zero_cycles():
    graph = CodeGraph()
    graph.add_file_import("main.py", "service.py")
    graph.add_file_import("service.py", "repository.py")
    graph.add_file_import("repository.py", "db.py")
    graph.add_file_import("service.py", "utils.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 0


# ============================================================================
# 5. Dead Code Identification & Entrypoint Whitelisting
# ============================================================================

ENTRYPOINTS = ["main", "run", "cli", "app", "start", "handler", "execute", "entrypoint"]

@pytest.mark.parametrize("entrypoint_name", ENTRYPOINTS)
def test_dead_code_ignores_standard_entrypoints(entrypoint_name: str):
    graph = CodeGraph()
    sym = CodeSymbol(
        name=entrypoint_name,
        kind=SymbolKind.FUNCTION,
        file_path="src/bootstrap.py",
        start_line=1,
        end_line=10,
        signature=f"def {entrypoint_name}(): pass",
    )
    graph.add_symbol(sym)
    dead = graph.find_dead_code(ignore_entrypoints=True)
    assert len(dead) == 0


@pytest.mark.parametrize("dunder_name", ["__init__", "__repr__", "__enter__", "__exit__", "__call__"])
def test_dead_code_ignores_dunder_methods(dunder_name: str):
    graph = CodeGraph()
    sym = CodeSymbol(
        name=dunder_name,
        kind=SymbolKind.METHOD,
        file_path="src/model.py",
        start_line=5,
        end_line=15,
        signature=f"def {dunder_name}(self): pass",
    )
    graph.add_symbol(sym)
    dead = graph.find_dead_code(ignore_entrypoints=True)
    assert len(dead) == 0


@pytest.mark.parametrize("test_path", [
    "tests/test_gateway.py",
    "tests/unit/test_auth.py",
    "src/service_test.py",
    "web/components/Button.spec.ts",
])
def test_dead_code_ignores_test_files(test_path: str):
    graph = CodeGraph()
    sym = CodeSymbol(
        name="test_helper_util",
        kind=SymbolKind.FUNCTION,
        file_path=test_path,
        start_line=1,
        end_line=10,
        signature="def test_helper_util(): pass",
    )
    graph.add_symbol(sym)
    dead = graph.find_dead_code(ignore_tests=True)
    assert len(dead) == 0


def test_dead_code_flags_uncalled_business_logic():
    graph = CodeGraph()
    used_sym = CodeSymbol(
        name="calculate_tax",
        kind=SymbolKind.FUNCTION,
        file_path="src/billing.py",
        start_line=1,
        end_line=10,
        signature="def calculate_tax(): pass",
    )
    caller_sym = CodeSymbol(
        name="process_order",
        kind=SymbolKind.FUNCTION,
        file_path="src/order.py",
        start_line=1,
        end_line=15,
        signature="def process_order(): pass",
        calls=["calculate_tax"],
    )
    orphaned_sym = CodeSymbol(
        name="deprecated_legacy_export",
        kind=SymbolKind.FUNCTION,
        file_path="src/export.py",
        start_line=1,
        end_line=20,
        signature="def deprecated_legacy_export(): pass",
    )
    graph.add_symbol(used_sym)
    graph.add_symbol(caller_sym)
    graph.add_symbol(orphaned_sym)

    dead = graph.find_dead_code()
    dead_names = [d.name for d in dead]
    assert "deprecated_legacy_export" in dead_names
    assert "calculate_tax" not in dead_names


# ============================================================================
# 6. Data Flow Hierarchy Traversal (Forward Callees & Backward Callers)
# ============================================================================

@pytest.mark.parametrize("depth", [1, 2, 3, 4])
def test_trace_data_flow_forward(depth: int):
    graph = CodeGraph()
    # a calls b, b calls c, c calls d, d calls e
    sym_a = CodeSymbol(name="fn_a", kind=SymbolKind.FUNCTION, file_path="f.py", start_line=1, end_line=5, signature="def fn_a(): pass", calls=["fn_b"])
    sym_b = CodeSymbol(name="fn_b", kind=SymbolKind.FUNCTION, file_path="f.py", start_line=6, end_line=10, signature="def fn_b(): pass", calls=["fn_c"])
    sym_c = CodeSymbol(name="fn_c", kind=SymbolKind.FUNCTION, file_path="f.py", start_line=11, end_line=15, signature="def fn_c(): pass", calls=["fn_d"])
    sym_d = CodeSymbol(name="fn_d", kind=SymbolKind.FUNCTION, file_path="f.py", start_line=16, end_line=20, signature="def fn_d(): pass", calls=["fn_e"])
    sym_e = CodeSymbol(name="fn_e", kind=SymbolKind.FUNCTION, file_path="f.py", start_line=21, end_line=25, signature="def fn_e(): pass")

    for s in [sym_a, sym_b, sym_c, sym_d, sym_e]:
        graph.add_symbol(s)

    flow = graph.trace_data_flow("fn_a", max_depth=depth, direction="forward")
    assert flow["name"] == "fn_a"
    assert flow["depth"] == 0

    curr = flow
    visited_depth = 0
    while curr["nodes"] and visited_depth < depth:
        curr = curr["nodes"][0]
        visited_depth += 1

    assert visited_depth == min(depth, 4)


def test_trace_data_flow_backward_callers():
    graph = CodeGraph()
    sym_target = CodeSymbol(name="db_query", kind=SymbolKind.FUNCTION, file_path="db.py", start_line=1, end_line=5, signature="def db_query(): pass")
    sym_service = CodeSymbol(name="get_users", kind=SymbolKind.FUNCTION, file_path="svc.py", start_line=1, end_line=5, signature="def get_users(): pass", calls=["db_query"])
    sym_api = CodeSymbol(name="handle_req", kind=SymbolKind.FUNCTION, file_path="api.py", start_line=1, end_line=5, signature="def handle_req(): pass", calls=["get_users"])

    graph.add_symbol(sym_target)
    graph.add_symbol(sym_service)
    graph.add_symbol(sym_api)

    flow = graph.trace_data_flow("db_query", max_depth=2, direction="backward")
    assert flow["name"] == "db_query"
    assert len(flow["nodes"]) == 1
    assert flow["nodes"][0]["name"] == "get_users"
    assert len(flow["nodes"][0]["nodes"]) == 1
    assert flow["nodes"][0]["nodes"][0]["name"] == "handle_req"


# ============================================================================
# 7. Class Inheritance & Interface Implementation Resolution
# ============================================================================

def test_find_implementations_single_and_multiple():
    graph = CodeGraph()
    base = CodeSymbol(name="BasePlugin", kind=SymbolKind.CLASS, file_path="base.py", start_line=1, end_line=10, signature="class BasePlugin: pass")
    child1 = CodeSymbol(name="GitPlugin", kind=SymbolKind.CLASS, file_path="git.py", start_line=1, end_line=15, signature="class GitPlugin(BasePlugin): pass", bases=["BasePlugin"])
    child2 = CodeSymbol(name="DockerPlugin", kind=SymbolKind.CLASS, file_path="docker.py", start_line=1, end_line=15, signature="class DockerPlugin(BasePlugin): pass", bases=["BasePlugin"])

    graph.add_symbol(base)
    graph.add_symbol(child1)
    graph.add_symbol(child2)

    impls = graph.find_implementations("BasePlugin")
    assert len(impls) == 2
    impl_names = {s.name for s in impls}
    assert "GitPlugin" in impl_names
    assert "DockerPlugin" in impl_names


# ============================================================================
# 8. PageRank Centrality: Complete Mesh Graph (K_n Symmetric Invariance)
# ============================================================================

@pytest.mark.parametrize("n_nodes", [2, 3, 4, 5, 6, 8, 10])
def test_pagerank_complete_mesh_symmetry(n_nodes: int):
    graph = CodeGraph()
    nodes = [f"peer_{i}.py" for i in range(n_nodes)]
    # Every node imports every other node
    for i in range(n_nodes):
        for j in range(n_nodes):
            if i != j:
                graph.add_file_import(nodes[i], nodes[j])

    ranked = graph.rank_central_files(damping=0.85)
    assert len(ranked) == n_nodes
    # In a fully symmetric complete mesh, all nodes receive identical PageRank scores
    scores = [s for _, s in ranked]
    expected_score = round(1.0 / n_nodes, 6)
    for s in scores:
        assert pytest.approx(s, rel=1e-3) == expected_score


# ============================================================================
# 9. PageRank Centrality: Diamond Dependency Hierarchies
# ============================================================================

@pytest.mark.parametrize("scale", [1, 2, 3, 4, 5])
def test_pagerank_diamond_topology(scale: int):
    graph = CodeGraph()
    # Diamond: source -> b, c -> sink
    source = "src/main.py"
    sink = "src/common/db.py"
    for i in range(scale):
        b = f"src/services/service_b_{i}.py"
        c = f"src/services/service_c_{i}.py"
        graph.add_file_import(source, b)
        graph.add_file_import(source, c)
        graph.add_file_import(b, sink)
        graph.add_file_import(c, sink)

    ranked = graph.rank_central_files()
    scores_dict = dict(ranked)
    # The sink (imported by all intermediate services) must have higher centrality than the source
    assert scores_dict[sink] > scores_dict[source]


# ============================================================================
# 10. Type Definition Lookup Matrix across File Paths
# ============================================================================

@pytest.mark.parametrize("sym_name,kind", [
    ("TaskExecutor", SymbolKind.CLASS),
    ("dispatch_task", SymbolKind.FUNCTION),
    ("TaskState", SymbolKind.ENUM),
    ("ITaskWorker", SymbolKind.INTERFACE),
    ("WorkerConfig", SymbolKind.STRUCT),
])
def test_find_type_definition_across_graph(sym_name: str, kind: SymbolKind):
    graph = CodeGraph()
    sym1 = CodeSymbol(name=sym_name, kind=kind, file_path="pkg/a.py", start_line=1, end_line=10, signature=f"def {sym_name}(): pass")
    sym2 = CodeSymbol(name=sym_name, kind=kind, file_path="pkg/b.py", start_line=5, end_line=15, signature=f"def {sym_name}(): pass")
    graph.add_symbol(sym1)
    graph.add_symbol(sym2)

    found = graph.find_type_definition(sym_name)
    assert len(found) == 2
    assert {s.file_path for s in found} == {"pkg/a.py", "pkg/b.py"}


# ============================================================================
# 11. Callee Resolution: Internal vs External Calls
# ============================================================================

@pytest.mark.parametrize("external_fn", ["print", "os.getenv", "json.loads", "math.sqrt", "requests.get"])
def test_callees_marks_external_unresolved_calls(external_fn: str):
    graph = CodeGraph()
    sym = CodeSymbol(
        name="caller_func",
        kind=SymbolKind.FUNCTION,
        file_path="src/util.py",
        start_line=1,
        end_line=10,
        signature="def caller_func(): pass",
        calls=[external_fn],
    )
    graph.add_symbol(sym)
    callees = graph.find_callees("caller_func")
    assert len(callees) == 1
    assert callees[0]["callee_name"] == external_fn
    assert callees[0]["is_external"] is True
    assert len(callees[0]["resolved"]) == 0


# ============================================================================
# 12. Complete Binary Tree Topologies (Depths 1 to 6)
# ============================================================================

@pytest.mark.parametrize("depth", [1, 2, 3, 4, 5, 6])
def test_pagerank_binary_tree_centrality(depth: int):
    graph = CodeGraph()
    # Tree where children import their parents (dependency flowing towards root)
    total_nodes = (2 ** (depth + 1)) - 1
    for i in range(1, total_nodes):
        parent = (i - 1) // 2
        graph.add_file_import(f"node_{i}.py", f"node_{parent}.py")

    ranked = graph.rank_central_files()
    assert len(ranked) == total_nodes
    scores_dict = dict(ranked)
    # Root node (node_0.py) is imported directly or indirectly by all nodes -> highest rank
    assert scores_dict["node_0.py"] == max(scores_dict.values())


# ============================================================================
# 13. Disconnected Component Clusters Matrix
# ============================================================================

@pytest.mark.parametrize("cluster_count", [2, 3, 4, 5])
def test_pagerank_disconnected_clusters(cluster_count: int):
    graph = CodeGraph()
    for c in range(cluster_count):
        hub = f"cluster_{c}_hub.py"
        spoke1 = f"cluster_{c}_spoke_1.py"
        spoke2 = f"cluster_{c}_spoke_2.py"
        graph.add_file_import(spoke1, hub)
        graph.add_file_import(spoke2, hub)

    ranked = graph.rank_central_files()
    assert len(ranked) == cluster_count * 3
    # Each hub must have identical scores due to component symmetry
    scores_dict = dict(ranked)
    hub_scores = [scores_dict[f"cluster_{c}_hub.py"] for c in range(cluster_count)]
    for s in hub_scores:
        assert pytest.approx(s, rel=1e-3) == hub_scores[0]


# ============================================================================
# 14. GraphEdge Data Invariants Matrix
# ============================================================================

EDGE_KINDS = ["calls", "imports", "inherits", "contains"]

@pytest.mark.parametrize("kind", EDGE_KINDS)
@pytest.mark.parametrize("weight", [0.5, 1.0, 2.5, 10.0])
def test_graph_edge_properties(kind: str, weight: float):
    edge = GraphEdge(source="src/a.py", target="src/b.py", kind=kind, weight=weight)
    assert edge.source == "src/a.py"
    assert edge.target == "src/b.py"
    assert edge.kind == kind
    assert edge.weight == weight


# ============================================================================
# 15. Cycle Canonicalisation Normalisation Invariants
# ============================================================================

CYCLES_TO_CANONICALISE = [
    (["b.py", "c.py", "a.py", "b.py"], ["a.py", "b.py", "c.py", "a.py"]),
    (["c.py", "a.py", "b.py", "c.py"], ["a.py", "b.py", "c.py", "a.py"]),
    (["z.py", "x.py", "y.py", "z.py"], ["x.py", "y.py", "z.py", "x.py"]),
    (["beta.py", "alpha.py", "beta.py"], ["alpha.py", "beta.py", "alpha.py"]),
]

@pytest.mark.parametrize("raw_cycle,expected_canonical", CYCLES_TO_CANONICALISE)
def test_cycle_canonicalisation(raw_cycle: list[str], expected_canonical: list[str]):
    canonical = CodeGraph._canonicalise_cycle(raw_cycle)
    assert canonical == expected_canonical


# ============================================================================
# 16. Dead Code Polyglot Extension Filters
# ============================================================================

POLYGLOT_EXTENSIONS = [
    (".py", "def unused(): pass"),
    (".ts", "function unused() {}"),
    (".js", "function unused() {}"),
    (".go", "func Unused() {}"),
    (".rs", "fn unused() {}"),
    (".java", "class UnusedClass {}"),
    (".cs", "class UnusedService {}"),
]

@pytest.mark.parametrize("ext,code_sig", POLYGLOT_EXTENSIONS)
def test_dead_code_polyglot_extensions(ext: str, code_sig: str):
    graph = CodeGraph()
    sym = CodeSymbol(
        name="unused",
        kind=SymbolKind.FUNCTION if "func" in code_sig or "def" in code_sig or "fn" in code_sig else SymbolKind.CLASS,
        file_path=f"src/module{ext}",
        start_line=1,
        end_line=5,
        signature=code_sig,
    )
    graph.add_symbol(sym)
    dead = graph.find_dead_code()
    assert len(dead) == 1
    assert dead[0].name == "unused"


