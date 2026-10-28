"""Exhaustive Schema, Specification, and Dispatch Matrix across all 37 PRUBETH Registered Tools."""

import pytest
import json
from prubeth.tools.registry import ToolRegistry, get_default_registry
from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolResult


@pytest.fixture
def registry():
    return ToolRegistry(populate_defaults=True)


def test_registry_contains_exactly_37_tools(registry):
    all_tools = registry.list_tools()
    assert len(all_tools) == 37, f"Expected 37 registered tools, found {len(all_tools)}"


# =========================================================================
# Matrix: OpenAI Function Calling Schema Export (37 Tools)
# =========================================================================

def test_all_37_tools_export_valid_openai_schemas(registry):
    tools = registry.list_tools()
    assert len(tools) == 37

    for tool in tools:
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        fn = schema["function"]
        assert fn["name"] == tool.name
        assert isinstance(fn["description"], str)
        assert len(fn["description"]) > 0
        assert fn["parameters"]["type"] == "object"
        # Validate that schema is strictly JSON serializable
        serialized = json.dumps(schema)
        assert len(serialized) > 20


# =========================================================================
# Matrix: Google Gemini FunctionDeclaration Export (37 Tools)
# =========================================================================

def test_all_37_tools_export_valid_gemini_schemas(registry):
    tools = registry.list_tools()
    assert len(tools) == 37

    for tool in tools:
        schema = tool.to_gemini_schema()
        assert schema["name"] == tool.name
        assert isinstance(schema["description"], str)
        assert schema["parameters"]["type"] == "OBJECT"
        # Gemini schema requires UPPERCASE types
        for prop in schema["parameters"].get("properties", {}).values():
            assert prop["type"] in ("STRING", "INTEGER", "NUMBER", "BOOLEAN", "ARRAY", "OBJECT")
        # Validate that schema is strictly JSON serializable
        serialized = json.dumps(schema)
        assert len(serialized) > 20


# =========================================================================
# Matrix: Anthropic Claude Tool Specification Export (37 Tools)
# =========================================================================

def test_all_37_tools_export_valid_anthropic_schemas(registry):
    tools = registry.list_tools()
    assert len(tools) == 37

    for tool in tools:
        schema = tool.to_anthropic_schema()
        assert schema["name"] == tool.name
        assert isinstance(schema["description"], str)
        assert schema["input_schema"]["type"] == "object"
        # Validate that schema is strictly JSON serializable
        serialized = json.dumps(schema)
        assert len(serialized) > 20


# =========================================================================
# Matrix: Clearance Level Coverage (37 Tools)
# =========================================================================

def test_all_37_tools_have_assigned_clearance(registry):
    tools = registry.list_tools()
    read_only = registry.list_tools(ToolClearanceLevel.READ_ONLY)
    mutation = registry.list_tools(ToolClearanceLevel.WORKSPACE_MUTATION)
    execution = registry.list_tools(ToolClearanceLevel.SYSTEM_EXECUTION)

    assert len(read_only) == 26
    assert len(mutation) == 7
    assert len(execution) == 4
    assert len(read_only) + len(mutation) + len(execution) == 37


# =========================================================================
# Matrix: Default Registry Global Invariants
# =========================================================================

def test_default_registry_has_all_expected_tool_names():
    reg = get_default_registry()

    expected_core = [
        "read_file", "write_file", "edit_file", "list_dir", "delete_file",
        "copy_file", "move_file", "grep_search", "glob_search", "run_shell",
        "run_python", "git_status", "git_diff", "git_commit", "git_log"
    ]
    expected_intel = [
        "code_structure", "find_callers", "find_callees", "find_type_definition",
        "find_implementations", "detect_circular_imports", "trace_data_flow",
        "find_dead_code", "rank_central_files", "explain_symbol"
    ]
    expected_verif = [
        "test_runner", "lint_checker", "type_checker", "coverage_analyser", "patch_verifier"
    ]
    expected_domain = [
        "todo", "test_gen", "security_linter", "crash_debugger", "benchmark", "heal", "spec_contract"
    ]

    all_expected = expected_core + expected_intel + expected_verif + expected_domain
    assert len(all_expected) == 37

    for name in all_expected:
        assert reg.has(name) is True, f"Tool '{name}' missing from global registry"
        tool = reg.get(name)
        assert tool is not None
        assert tool.name == name
