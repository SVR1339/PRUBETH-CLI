"""PRUBETH Conversation DAG Matrix Tests.

Verifies non-linear dialogue branching, tree traversal, branch switching,
linear path reconstruction, and serialization safety.
"""

from __future__ import annotations

import pytest
from prubeth.persistence.dag import ConversationDAG, ConversationNode


@pytest.fixture
def dag():
    return ConversationDAG()


def test_dag_initial_state(dag):
    assert dag.root_node_id is None
    assert dag.current_node_id is None
    assert dag.active_branch == "main"
    assert len(dag.nodes) == 0


def test_dag_linear_turn_sequence(dag):
    n1 = dag.add_turn("user", "Hello")
    n2 = dag.add_turn("assistant", "Hi there")
    n3 = dag.add_turn("user", "Explain AST")

    assert dag.root_node_id == n1
    assert dag.current_node_id == n3
    assert len(dag.nodes) == 3

    # Check linear path
    path = dag.get_active_path()
    assert len(path) == 3
    assert [n.node_id for n in path] == [n1, n2, n3]

    # Check provider format
    msgs = dag.export_linear_messages()
    assert len(msgs) == 3
    assert msgs[0] == {"role": "user", "content": "Hello"}
    assert msgs[1] == {"role": "assistant", "content": "Hi there"}
    assert msgs[2] == {"role": "user", "content": "Explain AST"}


def test_dag_branching_and_switching(dag):
    # Main branch: Turn 1 -> Turn 2
    n1 = dag.add_turn("user", "Initial problem")
    n2 = dag.add_turn("assistant", "Plan A approach")

    # Create Branch "plan_b" from n1
    dag.create_branch("plan_b", from_node_id=n1)
    assert dag.active_branch == "plan_b"
    assert dag.current_node_id == n1

    # Add turn in plan_b branch
    n3 = dag.add_turn("assistant", "Plan B alternative approach")
    assert dag.nodes[n3].parent_id == n1

    # Active path in plan_b should be n1 -> n3
    path_b = dag.get_active_path()
    assert [n.node_id for n in path_b] == [n1, n3]

    # Switch back to main branch
    assert dag.switch_branch("main") is True
    assert dag.current_node_id == n2
    path_main = dag.get_active_path()
    assert [n.node_id for n in path_main] == [n1, n2]


def test_dag_multiple_divergent_hypotheses(dag):
    root = dag.add_turn("user", "Which database?")
    # Branch 1: Postgres
    dag.create_branch("hypothesis_postgres", from_node_id=root)
    p1 = dag.add_turn("assistant", "PostgreSQL provides ACID and relational robustness.")

    # Branch 2: SQLite
    dag.create_branch("hypothesis_sqlite", from_node_id=root)
    s1 = dag.add_turn("assistant", "SQLite requires zero background daemons.")

    # Branch 3: Redis
    dag.create_branch("hypothesis_redis", from_node_id=root)
    r1 = dag.add_turn("assistant", "Redis provides in-memory sub-millisecond lookups.")

    assert len(dag.branches) == 4  # main + 3 hypotheses
    assert len(dag.nodes[root].children_ids) == 3

    # Verify switching
    dag.switch_branch("hypothesis_sqlite")
    msgs = dag.export_linear_messages()
    assert len(msgs) == 2
    assert "zero background daemons" in msgs[1]["content"]


def test_dag_serialization_round_trip(dag):
    n1 = dag.add_turn("user", "Start task")
    n2 = dag.add_turn("assistant", "Working on it", tool_calls=[{"name": "read_file", "args": {"path": "a.py"}}])
    dag.create_branch("experiment", from_node_id=n1)
    dag.add_turn("assistant", "Experimental path")

    data = dag.to_dict()
    restored = ConversationDAG.from_dict(data)

    assert restored.root_node_id == dag.root_node_id
    assert restored.active_branch == "experiment"
    assert len(restored.nodes) == len(dag.nodes)
    assert len(restored.branches) == len(dag.branches)
    assert restored.nodes[n2].tool_calls == [{"name": "read_file", "args": {"path": "a.py"}}]


@pytest.mark.parametrize("depth", [2, 5, 10, 20])
def test_dag_deep_linear_chain(dag, depth):
    for i in range(depth):
        dag.add_turn("user" if i % 2 == 0 else "assistant", f"Turn {i}")

    path = dag.get_active_path()
    assert len(path) == depth
    assert path[0].node_id == dag.root_node_id
    assert path[-1].node_id == dag.current_node_id
