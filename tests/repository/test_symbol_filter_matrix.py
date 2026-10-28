"""Tests for Incremental SQLite Index Symbol Queries, Kind Filters, and Limit Pagination."""

import pytest
from pathlib import Path
from prubeth.repository.incremental_index import IncrementalCodeIndex
from prubeth.repository.ast_parser import SymbolKind


@pytest.fixture
def indexed_workspace(tmp_path):
    """Sets up a workspace with diverse symbol kinds and names for query benchmarking."""
    # Create 20 service files with distinct kinds
    for i in range(20):
        (tmp_path / f"service_{i}.py").write_text(f'''
class ServiceClass_{i}:
    """Class docstring {i}."""
    def method_{i}(self) -> int:
        return {i}

def standalone_func_{i}(param: str) -> str:
    """Function docstring {i}."""
    return param
''', encoding="utf-8")

    index = IncrementalCodeIndex(workspace_root=tmp_path)
    index.sync_index()
    return index


# =========================================================================
# Exact Name Search Matrix (20 Classes)
# =========================================================================

CLASS_NAMES = [f"ServiceClass_{i}" for i in range(20)]

@pytest.mark.parametrize("class_name", CLASS_NAMES)
def test_exact_class_search_matrix(indexed_workspace, class_name):
    matches = indexed_workspace.search_symbols(class_name, exact=True)
    assert len(matches) == 1
    assert matches[0].name == class_name
    assert matches[0].kind == SymbolKind.CLASS


# =========================================================================
# Exact Function Search Matrix (20 Functions)
# =========================================================================

FUNC_NAMES = [f"standalone_func_{i}" for i in range(20)]

@pytest.mark.parametrize("func_name", FUNC_NAMES)
def test_exact_function_search_matrix(indexed_workspace, func_name):
    matches = indexed_workspace.search_symbols(func_name, exact=True)
    assert len(matches) == 1
    assert matches[0].name == func_name
    assert matches[0].kind == SymbolKind.FUNCTION


# =========================================================================
# Method Search Matrix (20 Methods)
# =========================================================================

METHOD_NAMES = [f"method_{i}" for i in range(20)]

@pytest.mark.parametrize("method_name", METHOD_NAMES)
def test_exact_method_search_matrix(indexed_workspace, method_name):
    matches = indexed_workspace.search_symbols(method_name, exact=True)
    assert len(matches) == 1
    assert matches[0].name == method_name
    assert matches[0].kind == SymbolKind.METHOD


# =========================================================================
# Kind Filter Matrix
# =========================================================================

KINDS = ["class", "function", "method"]

@pytest.mark.parametrize("kind_val", KINDS)
def test_kind_filter_isolation(indexed_workspace, kind_val):
    matches = indexed_workspace.search_symbols("", kind=kind_val, limit=100)
    assert len(matches) == 20
    assert all(m.kind.value == kind_val for m in matches)


# =========================================================================
# Limit Pagination Matrix
# =========================================================================

LIMIT_BOUNDS = [1, 2, 5, 10, 15, 20, 25, 30]

@pytest.mark.parametrize("limit_val", LIMIT_BOUNDS)
def test_limit_pagination_bounds(indexed_workspace, limit_val):
    matches = indexed_workspace.search_symbols("", limit=limit_val)
    expected_count = min(limit_val, 60)  # 20 classes + 20 methods + 20 functions = 60
    assert len(matches) == expected_count


# =========================================================================
# Prefix Substring Search Matrix
# =========================================================================

PREFIX_QUERIES = [
    ("Service", 20),
    ("standalone", 20),
    ("method", 20),
    ("ServiceClass_1", 11),  # ServiceClass_1, 10..19
]

@pytest.mark.parametrize("query,expected_min", PREFIX_QUERIES)
def test_prefix_substring_searches(indexed_workspace, query, expected_min):
    matches = indexed_workspace.search_symbols(query, limit=50)
    assert len(matches) >= expected_min


# =========================================================================
# Empty and Nonexistent Symbol Edge Cases
# =========================================================================

@pytest.mark.parametrize("missing_query", ["NoSuchClass", "ghost_func", "404", "xyz_abc_123"])
def test_nonexistent_queries_return_empty(indexed_workspace, missing_query):
    assert indexed_workspace.search_symbols(missing_query) == []
