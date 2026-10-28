"""Tests for Intelligence Tools Registry Dispatch, Security Clearance, and Execution Engine integration."""

import pytest
from pathlib import Path
from prubeth.security.permissions import SecurityEngine, PermissionLevel
from prubeth.persistence.database import TaskDatabase
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.tools.registry import ToolRegistry, get_default_registry
from prubeth.tools.intelligence import ALL_INTELLIGENCE_TOOLS
from prubeth.tools.base import ToolClearanceLevel


@pytest.fixture
def execution_env(tmp_path):
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "service.py").write_text('''
class PipelineManager:
    """Orchestrates compute pipelines."""
    def run_pipeline(self) -> bool:
        return True

def trigger_job():
    pm = PipelineManager()
    return pm.run_pipeline()
''', encoding="utf-8")

    db_path = tmp_path / "test_tasks.db"
    db = TaskDatabase(str(db_path))
    task_id = "test-task-1"
    db.create_task(task_id, "Integration test task")
    security = SecurityEngine(workspace_root=str(tmp_path), auto_approve_all=True)
    engine = ToolExecutionEngine(security, db, task_id)
    return {
        "workspace": tmp_path,
        "db": db,
        "task_id": task_id,
        "security": security,
        "engine": engine,
    }


# =========================================================================
# Registry Population and Filtering Tests
# =========================================================================

def test_registry_has_all_25_tools():
    reg = ToolRegistry(populate_defaults=True)
    # Registry has grown: 15 core + 10 intelligence + 12 verification/domain = 37 total
    assert len(reg) >= 25

    # 15 Core Tools
    core_names = [
        "read_file", "write_file", "edit_file", "list_dir", "delete_file",
        "copy_file", "move_file", "grep_search", "glob_search", "run_shell",
        "run_python", "git_status", "git_diff", "git_commit", "git_log"
    ]
    for name in core_names:
        assert reg.has(name)

    # 10 Intelligence Tools
    intel_names = [
        "code_structure", "find_callers", "find_callees", "find_type_definition",
        "find_implementations", "detect_circular_imports", "trace_data_flow",
        "find_dead_code", "rank_central_files", "explain_symbol"
    ]
    for name in intel_names:
        assert reg.has(name)


def test_registry_clearance_filtering():
    reg = ToolRegistry(populate_defaults=True)
    read_only_tools = reg.list_tools(ToolClearanceLevel.READ_ONLY)
    read_only_names = [t.name for t in read_only_tools]

    # All 10 intelligence tools must be strictly READ_ONLY
    for tool_cls in ALL_INTELLIGENCE_TOOLS:
        assert tool_cls.name in read_only_names


def test_registry_multi_provider_schema_exports():
    reg = ToolRegistry(populate_defaults=True)

    openai_tools = reg.to_openai_tools()
    assert len(openai_tools) >= 25
    assert all(t["type"] == "function" for t in openai_tools)

    gemini_tools = reg.to_gemini_tools()
    assert len(gemini_tools) == 1
    assert len(gemini_tools[0]["functionDeclarations"]) >= 25

    anthropic_tools = reg.to_anthropic_tools()
    assert len(anthropic_tools) >= 25
    assert all("input_schema" in t for t in anthropic_tools)


# =========================================================================
# ToolExecutionEngine Integration and Security Clearance Tests
# =========================================================================

@pytest.mark.parametrize("tool_name,args", [
    ("code_structure", {"file_path": "src/service.py"}),
    ("find_callers", {"symbol_name": "run_pipeline"}),
    ("find_callees", {"symbol_name": "trigger_job"}),
    ("find_type_definition", {"symbol_name": "PipelineManager"}),
    ("find_implementations", {"symbol_name": "PipelineManager"}),
    ("detect_circular_imports", {}),
    ("trace_data_flow", {"symbol_name": "trigger_job", "depth": 2}),
    ("find_dead_code", {"ignore_tests": True}),
    ("rank_central_files", {"limit": 5}),
    ("explain_symbol", {"symbol_name": "PipelineManager"}),
])
def test_dispatch_intelligence_tools_through_engine(execution_env, tool_name, args):
    engine = execution_env["engine"]
    success, output = engine.execute_tool(tool_name, args)
    assert success is True
    assert output != ""
    assert "Error" not in output or "not found" not in output


def test_intelligence_tools_are_auto_allowed_by_security(execution_env):
    security = execution_env["security"]
    for tool_cls in ALL_INTELLIGENCE_TOOLS:
        action = tool_cls.name
        # Should be ALLOW even if auto_approve_all is False
        policy = security.tool_policies.get(action)
        assert policy == PermissionLevel.ALLOW


def test_intelligence_tool_executions_logged_in_audit_database(execution_env):
    engine = execution_env["engine"]
    db = execution_env["db"]
    task_id = execution_env["task_id"]

    success, out = engine.execute_tool("code_structure", {"file_path": "src/service.py"})
    assert success is True

    # Verify execution was recorded in DB
    executions = db.get_task_tool_executions(task_id)
    assert len(executions) >= 1
    latest = executions[-1]
    assert latest["tool_name"] == "code_structure"
    assert latest["exit_code"] == 0


# =========================================================================
# Matrix Permutations Across All 25 Registered Tools
# =========================================================================

ALL_TOOL_NAMES = [
    "read_file", "write_file", "edit_file", "list_dir", "delete_file",
    "copy_file", "move_file", "grep_search", "glob_search", "run_shell",
    "run_python", "git_status", "git_diff", "git_commit", "git_log",
    "code_structure", "find_callers", "find_callees", "find_type_definition",
    "find_implementations", "detect_circular_imports", "trace_data_flow",
    "find_dead_code", "rank_central_files", "explain_symbol"
]

@pytest.mark.parametrize("name", ALL_TOOL_NAMES)
def test_all_25_tools_registered_in_default_registry(name):
    reg = get_default_registry()
    assert reg.has(name)
    tool = reg.get(name)
    assert tool is not None
    assert tool.name == name
    assert len(tool.description) > 10
