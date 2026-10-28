"""Tests for Wave 2 Repository Intelligence Tools (10 tools)."""

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
def repo_workspace(tmp_path):
    """Sets up a realistic workspace for tool execution tests."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)

    # Core module
    (src / "kernel.py").write_text('''
class MicroKernel:
    """Core executive kernel."""
    def __init__(self, mode: str = "fast"):
        self.mode = mode

    def boot(self) -> bool:
        return True

def bootstrap_system() -> MicroKernel:
    k = MicroKernel()
    k.boot()
    return k
''', encoding="utf-8")

    # Controller module
    (src / "controller.py").write_text('''
from src.kernel import bootstrap_system

def start_server():
    kernel = bootstrap_system()
    return kernel.boot()
''', encoding="utf-8")

    # Orphaned dead code module
    (src / "orphaned.py").write_text('''
def obsolete_routine():
    return "legacy"
''', encoding="utf-8")

    return tmp_path


# =========================================================================
# Tool Metadata and Schema Invariant Tests
# =========================================================================

@pytest.mark.parametrize("tool_cls", ALL_INTELLIGENCE_TOOLS)
def test_intelligence_tools_clearance_and_schemas(tool_cls):
    tool = tool_cls()
    assert tool.name != ""
    assert tool.description != ""
    assert tool.clearance_level == ToolClearanceLevel.READ_ONLY

    # OpenAI schema
    oai = tool.to_openai_schema()
    assert oai["type"] == "function"
    assert oai["function"]["name"] == tool.name

    # Gemini schema
    gem = tool.to_gemini_schema()
    assert gem["name"] == tool.name
    assert "parameters" in gem

    # Anthropic schema
    ant = tool.to_anthropic_schema()
    assert ant["name"] == tool.name
    assert "input_schema" in ant


# =========================================================================
# Tool Execution Tests
# =========================================================================

def test_code_structure_tool(repo_workspace):
    tool = CodeStructureTool(workspace_root=repo_workspace)

    # 1. Specific file
    res = tool.execute({"file_path": "src/kernel.py"})
    assert res.success is True
    assert "Structure of src/kernel.py:" in res.output
    assert "MicroKernel" in res.output
    assert "bootstrap_system" in res.output

    # 2. Non-existent file
    res_err = tool.execute({"file_path": "src/missing.py"})
    assert res_err.success is False
    assert "File not found" in res_err.output

    # 3. Whole workspace
    res_ws = tool.execute({})
    assert res_ws.success is True
    assert "Repository Symbol Overview" in res_ws.output


def test_find_callers_tool(repo_workspace):
    tool = FindCallersTool(workspace_root=repo_workspace)

    # Empty symbol_name fails
    err = tool.execute({"symbol_name": ""})
    assert err.success is False

    # Find callers of bootstrap_system (start_server calls it)
    res = tool.execute({"symbol_name": "bootstrap_system"})
    assert res.success is True
    assert "start_server" in res.output

    # No callers
    res_none = tool.execute({"symbol_name": "start_server"})
    assert res_none.success is True
    assert "No callers found" in res_none.output


def test_find_callees_tool(repo_workspace):
    tool = FindCalleesTool(workspace_root=repo_workspace)

    # Empty symbol_name fails
    err = tool.execute({"symbol_name": ""})
    assert err.success is False

    # Find callees of bootstrap_system (calls MicroKernel and boot)
    res = tool.execute({"symbol_name": "bootstrap_system"})
    assert res.success is True
    assert "boot" in res.output or "MicroKernel" in res.output


def test_find_type_definition_tool(repo_workspace):
    tool = FindTypeDefinitionTool(workspace_root=repo_workspace)

    # Find MicroKernel definition
    res = tool.execute({"symbol_name": "MicroKernel"})
    assert res.success is True
    assert "MicroKernel" in res.output
    assert "src/kernel.py" in res.output
    assert "Core executive kernel" in res.output

    # Missing symbol
    res_miss = tool.execute({"symbol_name": "NonExistentClass"})
    assert res_miss.success is True
    assert "No type definition found" in res_miss.output


def test_find_implementations_tool(repo_workspace):
    # Add an implementation
    (repo_workspace / "src" / "subkernel.py").write_text('''
from src.kernel import MicroKernel

class FastKernel(MicroKernel):
    pass
''', encoding="utf-8")

    tool = FindImplementationsTool(workspace_root=repo_workspace)
    res = tool.execute({"symbol_name": "MicroKernel"})
    assert res.success is True
    assert "FastKernel" in res.output


def test_detect_circular_imports_tool_clean_and_cycle(repo_workspace):
    tool = DetectCircularImportsTool(workspace_root=repo_workspace)

    # 1. Clean repo
    res_clean = tool.execute({})
    assert res_clean.success is True
    assert "No circular import dependency cycles detected" in res_clean.output

    # 2. Introduce cycle: a -> b -> a
    (repo_workspace / "src" / "mod_a.py").write_text("import src.mod_b\n", encoding="utf-8")
    (repo_workspace / "src" / "mod_b.py").write_text("import src.mod_a\n", encoding="utf-8")

    res_cycle = tool.execute({})
    assert res_cycle.success is True
    assert "circular import cycle" in res_cycle.output


def test_trace_data_flow_tool(repo_workspace):
    tool = TraceDataFlowTool(workspace_root=repo_workspace)

    # Forward trace
    res_fwd = tool.execute({"symbol_name": "start_server", "depth": 3, "direction": "forward"})
    assert res_fwd.success is True
    assert "start_server" in res_fwd.output
    assert "bootstrap_system" in res_fwd.output

    # Backward trace
    res_bwd = tool.execute({"symbol_name": "bootstrap_system", "depth": 2, "direction": "backward"})
    assert res_bwd.success is True
    assert "start_server" in res_bwd.output


def test_find_dead_code_tool(repo_workspace):
    tool = FindDeadCodeTool(workspace_root=repo_workspace)
    res = tool.execute({"ignore_tests": True, "ignore_entrypoints": True})
    assert res.success is True
    assert "obsolete_routine" in res.output


def test_rank_central_files_tool(repo_workspace):
    tool = RankCentralFilesTool(workspace_root=repo_workspace)
    res = tool.execute({"limit": 10, "damping": 0.85})
    assert res.success is True
    assert "Architectural Centrality Ranking" in res.output


def test_explain_symbol_tool(repo_workspace):
    tool = ExplainSymbolTool(workspace_root=repo_workspace)

    res = tool.execute({"symbol_name": "MicroKernel"})
    assert res.success is True
    assert "Symbol Dossier: 'MicroKernel'" in res.output
    assert "Location:" in res.output
    assert "src/kernel.py" in res.output
    assert "Docstring:" in res.output

    # Missing symbol
    res_err = tool.execute({"symbol_name": "NonExistent"})
    assert res_err.success is False
    assert "not found" in res_err.output
