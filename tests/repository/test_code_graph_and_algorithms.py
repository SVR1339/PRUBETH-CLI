"""Tests for PRUBETH In-Memory Code Call Graph, Cycle Detection, and PageRank Centrality."""

import pytest
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind
from prubeth.repository.graph import CodeGraph, GraphEdge


@pytest.fixture
def graph():
    return CodeGraph()


# =========================================================================
# Symbol Addition and Retrieval Tests
# =========================================================================

def test_add_and_lookup_symbols(graph):
    sym1 = CodeSymbol(
        name="authenticate_user",
        kind=SymbolKind.FUNCTION,
        file_path="src/auth.py",
        start_line=10,
        end_line=25,
        signature="def authenticate_user(token: str) -> bool",
        calls=["verify_jwt", "log_event"],
        imports=[{"module": "jwt"}],
    )
    sym_id = graph.add_symbol(sym1)
    assert sym_id == "src/auth.py::authenticate_user"
    assert graph.symbols[sym_id] == sym1
    assert "src/auth.py::authenticate_user" in graph.file_symbols["src/auth.py"]
    assert "src/auth.py::authenticate_user" in graph.name_to_ids["authenticate_user"]


def test_find_callers_and_callees(graph):
    # Setup call chain: controller -> authenticate_user -> verify_jwt
    sym_ctrl = CodeSymbol(
        name="login_handler",
        kind=SymbolKind.FUNCTION,
        file_path="src/controller.py",
        start_line=5,
        end_line=15,
        signature="def login_handler()",
        calls=["authenticate_user"],
    )
    sym_auth = CodeSymbol(
        name="authenticate_user",
        kind=SymbolKind.FUNCTION,
        file_path="src/auth.py",
        start_line=10,
        end_line=20,
        signature="def authenticate_user()",
        calls=["verify_jwt"],
    )
    sym_jwt = CodeSymbol(
        name="verify_jwt",
        kind=SymbolKind.FUNCTION,
        file_path="src/crypto.py",
        start_line=1,
        end_line=10,
        signature="def verify_jwt()",
        calls=[],
    )

    graph.add_symbol(sym_ctrl)
    graph.add_symbol(sym_auth)
    graph.add_symbol(sym_jwt)

    # 1. Test find_callers
    auth_callers = graph.find_callers("authenticate_user")
    assert len(auth_callers) == 1
    assert auth_callers[0].name == "login_handler"

    jwt_callers = graph.find_callers("verify_jwt")
    assert len(jwt_callers) == 1
    assert jwt_callers[0].name == "authenticate_user"

    ctrl_callers = graph.find_callers("login_handler")
    assert len(ctrl_callers) == 0

    # 2. Test find_callees
    ctrl_callees = graph.find_callees("login_handler")
    assert len(ctrl_callees) == 1
    assert ctrl_callees[0]["callee_name"] == "authenticate_user"
    assert not ctrl_callees[0]["is_external"]
    assert ctrl_callees[0]["resolved"][0]["name"] == "authenticate_user"

    auth_callees = graph.find_callees("authenticate_user")
    assert len(auth_callees) == 1
    assert auth_callees[0]["callee_name"] == "verify_jwt"

    jwt_callees = graph.find_callees("verify_jwt")
    assert len(jwt_callees) == 0


def test_find_implementations_and_inheritance(graph):
    base_class = CodeSymbol(
        name="BaseRepository",
        kind=SymbolKind.CLASS,
        file_path="src/repo/base.py",
        start_line=1,
        end_line=20,
        signature="class BaseRepository",
        bases=[],
    )
    impl_sql = CodeSymbol(
        name="SQLRepository",
        kind=SymbolKind.CLASS,
        file_path="src/repo/sql.py",
        start_line=1,
        end_line=50,
        signature="class SQLRepository(BaseRepository)",
        bases=["BaseRepository"],
    )
    impl_memory = CodeSymbol(
        name="InMemoryRepository",
        kind=SymbolKind.CLASS,
        file_path="src/repo/memory.py",
        start_line=1,
        end_line=30,
        signature="class InMemoryRepository(BaseRepository)",
        bases=["BaseRepository"],
    )

    graph.add_symbol(base_class)
    graph.add_symbol(impl_sql)
    graph.add_symbol(impl_memory)

    implementations = graph.find_implementations("BaseRepository")
    impl_names = [i.name for i in implementations]
    assert len(implementations) == 2
    assert "SQLRepository" in impl_names
    assert "InMemoryRepository" in impl_names


def test_find_type_definition(graph):
    sym = CodeSymbol(
        name="SessionContext",
        kind=SymbolKind.CLASS,
        file_path="src/context.py",
        start_line=15,
        end_line=45,
        signature="class SessionContext",
    )
    graph.add_symbol(sym)

    defs = graph.find_type_definition("SessionContext")
    assert len(defs) == 1
    assert defs[0].file_path == "src/context.py"
    assert defs[0].start_line == 15

    assert graph.find_type_definition("NonExistent") == []


# =========================================================================
# Circular Import Detection Tests
# =========================================================================

def test_detect_no_circular_imports_in_dag(graph):
    # A -> B -> C (No cycle)
    graph.add_file_import("src/a.py", "src/b.py")
    graph.add_file_import("src/b.py", "src/c.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 0


def test_detect_2_node_circular_import_cycle(graph):
    # A -> B -> A
    graph.add_file_import("src/a.py", "src/b.py")
    graph.add_file_import("src/b.py", "src/a.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 1
    cycle = cycles[0]
    assert cycle == ["src/a.py", "src/b.py", "src/a.py"]


def test_detect_3_node_circular_import_cycle(graph):
    # A -> B -> C -> A
    graph.add_file_import("src/a.py", "src/b.py")
    graph.add_file_import("src/b.py", "src/c.py")
    graph.add_file_import("src/c.py", "src/a.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 1
    assert cycles[0] == ["src/a.py", "src/b.py", "src/c.py", "src/a.py"]


def test_detect_multiple_independent_cycles(graph):
    # Cycle 1: a -> b -> a
    graph.add_file_import("src/a.py", "src/b.py")
    graph.add_file_import("src/b.py", "src/a.py")

    # Cycle 2: x -> y -> z -> x
    graph.add_file_import("src/x.py", "src/y.py")
    graph.add_file_import("src/y.py", "src/z.py")
    graph.add_file_import("src/z.py", "src/x.py")

    cycles = graph.detect_circular_imports()
    assert len(cycles) == 2


# =========================================================================
# PageRank Centrality Ranking Tests
# =========================================================================

def test_rank_central_files_star_network(graph):
    # 5 files all import 'src/core/kernel.py'
    # kernel.py should achieve the highest centrality score!
    for i in range(5):
        graph.add_file_import(f"src/module_{i}.py", "src/core/kernel.py")

    ranked = graph.rank_central_files()
    assert len(ranked) == 6
    top_file, top_score = ranked[0]
    assert top_file == "src/core/kernel.py"
    # kernel.py must strictly outrank all peripheral leaf modules
    assert top_score > ranked[1][1]


def test_rank_central_files_empty_graph(graph):
    assert graph.rank_central_files() == []


def test_rank_central_files_convergence_tolerances(graph):
    graph.add_file_import("a.py", "b.py")
    graph.add_file_import("b.py", "c.py")
    graph.add_file_import("c.py", "a.py")

    ranked = graph.rank_central_files(damping=0.85, max_iterations=100, tolerance=1e-6)
    assert len(ranked) == 3
    # In a symmetric 3-cycle, all ranks must converge to equal scores
    scores = [score for _, score in ranked]
    assert abs(scores[0] - scores[1]) < 0.01
    assert abs(scores[1] - scores[2]) < 0.01


# =========================================================================
# Dead Code Detection Tests
# =========================================================================

def test_find_dead_code_identifies_uncalled_functions(graph):
    used_fn = CodeSymbol(
        name="active_logic",
        kind=SymbolKind.FUNCTION,
        file_path="src/service.py",
        start_line=1,
        end_line=10,
        signature="def active_logic()",
    )
    dead_fn = CodeSymbol(
        name="orphaned_helper",
        kind=SymbolKind.FUNCTION,
        file_path="src/utils.py",
        start_line=1,
        end_line=10,
        signature="def orphaned_helper()",
    )
    caller_fn = CodeSymbol(
        name="entrypoint",
        kind=SymbolKind.FUNCTION,
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        signature="def entrypoint()",
        calls=["active_logic"],
    )

    graph.add_symbol(used_fn)
    graph.add_symbol(dead_fn)
    graph.add_symbol(caller_fn)

    dead_symbols = graph.find_dead_code(ignore_tests=True, ignore_entrypoints=True)
    dead_names = [s.name for s in dead_symbols]
    assert "orphaned_helper" in dead_names
    assert "active_logic" not in dead_names
    assert "entrypoint" not in dead_names  # Excluded by entrypoint filter


# =========================================================================
# Data Flow Traversal Tests
# =========================================================================

def test_trace_data_flow_forward_and_backward(graph):
    # Flow: a -> b -> c
    sym_a = CodeSymbol(name="fn_a", kind=SymbolKind.FUNCTION, file_path="a.py", start_line=1, end_line=5, signature="def fn_a()", calls=["fn_b"])
    sym_b = CodeSymbol(name="fn_b", kind=SymbolKind.FUNCTION, file_path="b.py", start_line=1, end_line=5, signature="def fn_b()", calls=["fn_c"])
    sym_c = CodeSymbol(name="fn_c", kind=SymbolKind.FUNCTION, file_path="c.py", start_line=1, end_line=5, signature="def fn_c()", calls=[])

    graph.add_symbol(sym_a)
    graph.add_symbol(sym_b)
    graph.add_symbol(sym_c)

    # Forward trace from fn_a
    forward_tree = graph.trace_data_flow("fn_a", max_depth=3, direction="forward")
    assert forward_tree["name"] == "fn_a"
    assert len(forward_tree["nodes"]) == 1
    assert forward_tree["nodes"][0]["name"] == "fn_b"
    assert forward_tree["nodes"][0]["nodes"][0]["name"] == "fn_c"

    # Backward trace from fn_c
    backward_tree = graph.trace_data_flow("fn_c", max_depth=3, direction="backward")
    assert backward_tree["name"] == "fn_c"
    assert len(backward_tree["nodes"]) == 1
    assert backward_tree["nodes"][0]["name"] == "fn_b"
    assert backward_tree["nodes"][0]["nodes"][0]["name"] == "fn_a"


# =========================================================================
# Parametrized Scale Graph Tests
# =========================================================================

SCALE_DAG_SIZES = [5, 10, 20, 30]

@pytest.mark.parametrize("n", SCALE_DAG_SIZES)
def test_scale_dag_no_cycles(graph, n):
    for i in range(n - 1):
        graph.add_file_import(f"file_{i}.py", f"file_{i+1}.py")
    assert graph.detect_circular_imports() == []


SCALE_CYCLE_SIZES = [2, 3, 5, 8]

@pytest.mark.parametrize("n", SCALE_CYCLE_SIZES)
def test_scale_ring_cycle_detection(graph, n):
    for i in range(n):
        nxt = (i + 1) % n
        graph.add_file_import(f"node_{i}.py", f"node_{nxt}.py")
    cycles = graph.detect_circular_imports()
    assert len(cycles) == 1
    assert len(cycles[0]) == n + 1


# =========================================================================
# Additional Relational and Topological Graph Suites
# =========================================================================

GRAPH_SHAPES = [
    (10, "linear"),
    (15, "tree"),
    (20, "dense"),
]

@pytest.mark.parametrize("size,shape", GRAPH_SHAPES)
def test_graph_pagerank_deterministic_ranking(graph, size, shape):
    if shape == "linear":
        for i in range(size - 1):
            graph.add_file_import(f"f_{i}.py", f"f_{i+1}.py")
    elif shape == "tree":
        for i in range(1, size):
            parent = (i - 1) // 2
            graph.add_file_import(f"f_{i}.py", f"f_{parent}.py")
    elif shape == "dense":
        for i in range(min(size, 8)):
            for j in range(i + 1, min(size, 8)):
                graph.add_file_import(f"f_{i}.py", f"f_{j}.py")

    ranks = graph.rank_central_files()
    assert len(ranks) > 0
    # Scores must sum approximately to 1.0
    total_score = sum(s for _, s in ranks)
    assert 0.90 <= total_score <= 1.10


@pytest.mark.parametrize("depth", [1, 2, 3, 4])
def test_trace_data_flow_depth_limits(graph, depth):
    # Setup chain: c0 -> c1 -> c2 -> c3 -> c4
    for i in range(4):
        sym = CodeSymbol(
            name=f"chain_{i}",
            kind=SymbolKind.FUNCTION,
            file_path=f"m_{i}.py",
            start_line=1,
            end_line=5,
            signature=f"def chain_{i}()",
            calls=[f"chain_{i+1}"],
        )
        graph.add_symbol(sym)
    sym_last = CodeSymbol(
        name="chain_4",
        kind=SymbolKind.FUNCTION,
        file_path="m_4.py",
        start_line=1,
        end_line=5,
        signature="def chain_4()",
        calls=[],
    )
    graph.add_symbol(sym_last)

    tree = graph.trace_data_flow("chain_0", max_depth=depth, direction="forward")

    # Measure actual depth reached
    def get_max_depth(node):
        d = node.get("depth", 0)
        children = node.get("nodes", [])
        if not children:
            return d
        return max(get_max_depth(c) for c in children)

    max_d = get_max_depth(tree)
    assert max_d <= depth


@pytest.mark.parametrize("num_callers", [1, 5, 10, 20])
def test_fan_in_callers_count(graph, num_callers):
    target = CodeSymbol(
        name="central_utility",
        kind=SymbolKind.FUNCTION,
        file_path="src/util.py",
        start_line=1,
        end_line=5,
        signature="def central_utility()",
    )
    graph.add_symbol(target)

    for i in range(num_callers):
        caller = CodeSymbol(
            name=f"caller_{i}",
            kind=SymbolKind.FUNCTION,
            file_path=f"src/caller_{i}.py",
            start_line=1,
            end_line=5,
            signature=f"def caller_{i}()",
            calls=["central_utility"],
        )
        graph.add_symbol(caller)

    callers = graph.find_callers("central_utility")
    assert len(callers) == num_callers
