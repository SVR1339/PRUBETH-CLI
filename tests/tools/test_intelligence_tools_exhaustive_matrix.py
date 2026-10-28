"""Exhaustive parameter permutation matrix for PRUBETH Wave 2 Intelligence Tools."""

import pytest
from pathlib import Path
from prubeth.tools.intelligence import (
    CodeStructureTool,
    FindCallersTool,
    FindCalleesTool,
    FindTypeDefinitionTool,
    FindImplementationsTool,
    DetectCircularImportsTool,
    TraceDataFlowTool,
    FindDeadCodeTool,
    RankCentralFilesTool,
    ExplainSymbolTool,
    ALL_INTELLIGENCE_TOOLS,
)
from prubeth.tools.base import ToolClearanceLevel, ToolResult


@pytest.fixture
def complex_workspace(tmp_path):
    """Sets up a comprehensive workspace with classes, callers, callees, and modules."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)

    # Core base class
    (src / "base_agent.py").write_text('''
class BaseAgent:
    """Foundational agent interface."""
    def __init__(self, name: str):
        self.name = name

    def step(self) -> bool:
        return True
''', encoding="utf-8")

    # Specialized derived classes
    (src / "coder_agent.py").write_text('''
from src.base_agent import BaseAgent

class CoderAgent(BaseAgent):
    """Generates code patches."""
    def step(self) -> bool:
        self.execute_edit()
        return True

    def execute_edit(self):
        pass
''', encoding="utf-8")

    (src / "tester_agent.py").write_text('''
from src.base_agent import BaseAgent

class TesterAgent(BaseAgent):
    """Executes automated test suites."""
    def step(self) -> bool:
        return True
''', encoding="utf-8")

    # Orchestrator
    (src / "coordinator.py").write_text('''
from src.coder_agent import CoderAgent
from src.tester_agent import TesterAgent

def coordinate_workflow():
    c = CoderAgent("coder")
    t = TesterAgent("tester")
    c.step()
    t.step()
''', encoding="utf-8")

    return tmp_path


# =========================================================================
# TraceDataFlow Depth and Direction Permutation Matrix
# =========================================================================

TRACE_PERMUTATIONS = [
    ("coordinate_workflow", d, dir_val)
    for d in [1, 2, 3, 5]
    for dir_val in ["forward", "backward"]
]

@pytest.mark.parametrize("sym_name,depth,direction", TRACE_PERMUTATIONS)
def test_trace_data_flow_matrix(complex_workspace, sym_name, depth, direction):
    tool = TraceDataFlowTool(workspace_root=complex_workspace)
    res = tool.execute({"symbol_name": sym_name, "depth": depth, "direction": direction})
    assert res.success is True
    assert res.metadata["depth"] == depth
    assert res.metadata["direction"] == direction
    assert "===" in res.output


# =========================================================================
# RankCentralFiles Damping and Limit Permutation Matrix
# =========================================================================

RANK_PERMUTATIONS = [
    (limit, damping)
    for limit in [1, 3, 5, 10]
    for damping in [0.25, 0.50, 0.85, 0.95]
]

@pytest.mark.parametrize("limit,damping", RANK_PERMUTATIONS)
def test_rank_central_files_matrix(complex_workspace, limit, damping):
    tool = RankCentralFilesTool(workspace_root=complex_workspace)
    res = tool.execute({"limit": limit, "damping": damping})
    assert res.success is True
    assert res.metadata["ranked_count"] >= 3
    assert len(res.metadata["top_ranked"]) <= limit


# =========================================================================
# FindDeadCode Flag Permutations
# =========================================================================

DEAD_CODE_PERMUTATIONS = [
    (True, True),
    (True, False),
    (False, True),
    (False, False),
]

@pytest.mark.parametrize("ignore_tests,ignore_entrypoints", DEAD_CODE_PERMUTATIONS)
def test_find_dead_code_flag_matrix(complex_workspace, ignore_tests, ignore_entrypoints):
    tool = FindDeadCodeTool(workspace_root=complex_workspace)
    res = tool.execute({"ignore_tests": ignore_tests, "ignore_entrypoints": ignore_entrypoints})
    assert res.success is True
    assert "dead_symbols_count" in res.metadata


# =========================================================================
# ExplainSymbol Dossier Permutation Matrix
# =========================================================================

EXPLAIN_TARGETS = [
    "BaseAgent",
    "CoderAgent",
    "TesterAgent",
    "coordinate_workflow",
]

@pytest.mark.parametrize("target", EXPLAIN_TARGETS)
def test_explain_symbol_matrix(complex_workspace, target):
    tool = ExplainSymbolTool(workspace_root=complex_workspace)
    res = tool.execute({"symbol_name": target})
    assert res.success is True
    assert f"Symbol Dossier: '{target}'" in res.output
    assert "Location:" in res.output
    assert "Signature:" in res.output


# =========================================================================
# CodeStructure File vs Project Permutation Matrix
# =========================================================================

STRUCTURE_TARGETS = [
    "src/base_agent.py",
    "src/coder_agent.py",
    "src/tester_agent.py",
    "src/coordinator.py",
    "",  # whole project
]

@pytest.mark.parametrize("path", STRUCTURE_TARGETS)
def test_code_structure_matrix(complex_workspace, path):
    tool = CodeStructureTool(workspace_root=complex_workspace)
    res = tool.execute({"file_path": path} if path else {})
    assert res.success is True
    assert res.metadata["count"] >= 1


# =========================================================================
# FindImplementations Permutation Matrix
# =========================================================================

def test_find_implementations_multiple_derived(complex_workspace):
    tool = FindImplementationsTool(workspace_root=complex_workspace)
    res = tool.execute({"symbol_name": "BaseAgent"})
    assert res.success is True
    assert res.metadata["count"] == 2
    names = [i["name"] for i in res.metadata["implementations"]]
    assert "CoderAgent" in names
    assert "TesterAgent" in names


# =========================================================================
# Invalid and Edge-Case Input Matrix for All 10 Tools
# =========================================================================

@pytest.mark.parametrize("tool_cls", ALL_INTELLIGENCE_TOOLS)
def test_tools_graceful_handling_of_empty_dict(complex_workspace, tool_cls):
    tool = tool_cls(workspace_root=complex_workspace)
    # Executing with empty arguments should never crash or raise unhandled exception
    res = tool.execute({})
    assert isinstance(res, ToolResult)
    assert isinstance(res.output, str)
    assert isinstance(res.success, bool)
