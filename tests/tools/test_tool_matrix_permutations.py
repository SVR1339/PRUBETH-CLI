"""Matrix permutation and property-based invariant test suite across all 15 PRUBETH core tools."""

import re
import pytest
from typing import Type

from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult
from prubeth.tools.core import (
    ALL_CORE_TOOLS,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirTool,
    DeleteFileTool,
    CopyFileTool,
    MoveFileTool,
    GrepSearchTool,
    GlobSearchTool,
    RunShellTool,
    RunPythonTool,
    GitStatusTool,
    GitDiffTool,
    GitCommitTool,
    GitLogTool,
)
from prubeth.tools.registry import ToolRegistry


# =========================================================================
# Invariant Tests for ALL 15 Tools
# =========================================================================

def test_core_tools_count():
    assert len(ALL_CORE_TOOLS) == 15


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_tool_naming_conventions(tool_cls: Type[BaseTool]):
    tool = tool_cls()
    assert tool.name, f"{tool_cls.__name__} has an empty name"
    assert re.match(r"^[a-z]+(_[a-z]+)*$", tool.name), f"{tool.name} violates snake_case convention"
    assert len(tool.description) >= 15, f"{tool.name} description is too terse (< 15 chars)"


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_tool_clearance_level_validity(tool_cls: Type[BaseTool]):
    tool = tool_cls()
    assert isinstance(tool.clearance_level, ToolClearanceLevel)


def test_clearance_level_distribution():
    read_only = [t for t in ALL_CORE_TOOLS if t.clearance_level == ToolClearanceLevel.READ_ONLY]
    mutation = [t for t in ALL_CORE_TOOLS if t.clearance_level == ToolClearanceLevel.WORKSPACE_MUTATION]
    execution = [t for t in ALL_CORE_TOOLS if t.clearance_level == ToolClearanceLevel.SYSTEM_EXECUTION]

    assert len(read_only) == 7  # read_file, list_dir, grep_search, glob_search, git_status, git_diff, git_log
    assert len(mutation) == 6   # write_file, edit_file, delete_file, copy_file, move_file, git_commit
    assert len(execution) == 2  # run_shell, run_python


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_tool_parameter_invariants(tool_cls: Type[BaseTool]):
    tool = tool_cls()
    param_names = set()
    valid_types = {"string", "integer", "number", "boolean", "array", "object"}

    for p in tool.parameters:
        assert isinstance(p, ToolParameter)
        assert p.name, f"Parameter in {tool.name} has no name"
        assert p.name not in param_names, f"Duplicate parameter '{p.name}' in {tool.name}"
        param_names.add(p.name)
        assert p.type in valid_types, f"Invalid type '{p.type}' for parameter '{p.name}' in {tool.name}"
        assert len(p.description) >= 5, f"Description for '{p.name}' in {tool.name} is too short"


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_tool_openai_schema_conformance(tool_cls: Type[BaseTool]):
    tool = tool_cls()
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == tool.name
    assert fn["description"] == tool.description
    assert fn["parameters"]["type"] == "object"
    props = fn["parameters"]["properties"]

    for p in tool.parameters:
        assert p.name in props
        assert props[p.name]["type"] == p.type
        assert props[p.name]["description"] == p.description
        if p.required:
            assert p.name in fn["parameters"]["required"]


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_tool_gemini_schema_conformance(tool_cls: Type[BaseTool]):
    tool = tool_cls()
    schema = tool.to_gemini_schema()
    assert schema["name"] == tool.name
    assert schema["description"] == tool.description
    assert schema["parameters"]["type"] == "OBJECT"
    props = schema["parameters"]["properties"]

    for p in tool.parameters:
        assert p.name in props
        # Gemini OpenAPI types are uppercase
        expected_type = p.type.upper()
        assert props[p.name]["type"] == expected_type
        if p.required:
            assert p.name in schema["parameters"]["required"]


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_tool_anthropic_schema_conformance(tool_cls: Type[BaseTool]):
    tool = tool_cls()
    schema = tool.to_anthropic_schema()
    assert schema["name"] == tool.name
    assert schema["description"] == tool.description
    assert schema["input_schema"]["type"] == "object"
    props = schema["input_schema"]["properties"]

    for p in tool.parameters:
        assert p.name in props
        assert props[p.name]["type"] == p.type
        if p.required:
            assert p.name in schema["input_schema"]["required"]


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_tool_rejects_non_dict_arguments(tool_cls: Type[BaseTool]):
    tool = tool_cls()
    ok, err = tool.validate_args("not_a_dict")  # type: ignore
    assert ok is False
    assert "Expected arguments dictionary" in err

    ok2, err2 = tool.validate_args([1, 2, 3])  # type: ignore
    assert ok2 is False
    assert "Expected arguments dictionary" in err2


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_tool_type_validation_rejects_wrong_types(tool_cls: Type[BaseTool]):
    tool = tool_cls()
    for p in tool.parameters:
        # Create an argument dictionary with an invalid type for parameter p
        if p.type == "string":
            bad_val = 99999
        elif p.type == "integer":
            bad_val = "not_an_int"
        elif p.type == "boolean":
            bad_val = 1234
        elif p.type == "array":
            bad_val = "not_a_list"
        else:
            continue

        # Populate valid dummy values for all required parameters
        test_args = {}
        for req_p in tool.parameters:
            if req_p.required:
                if req_p.type == "string":
                    test_args[req_p.name] = "dummy_val"
                elif req_p.type == "integer":
                    test_args[req_p.name] = 1
                elif req_p.type == "boolean":
                    test_args[req_p.name] = True
                elif req_p.type == "array":
                    test_args[req_p.name] = ["dummy"]
                elif req_p.type == "object":
                    test_args[req_p.name] = {"dummy": "val"}

        test_args[p.name] = bad_val
        ok, err = tool.validate_args(test_args)
        assert ok is False
        assert f"Parameter '{p.name}'" in err


# =========================================================================
# Registry Population & Clearance Filtering Matrix
# =========================================================================

def test_registry_contains_all_15_tools():
    reg = ToolRegistry(populate_defaults=True)
    # Registry has grown from 15 → 37 tools across Phases 1–5 (22 Intelligence + Domain tools added)
    assert len(reg) >= 15
    for tool_cls in ALL_CORE_TOOLS:
        name = tool_cls.name
        assert reg.has(name)
        assert reg.get(name) is not None
        assert reg.get(name).name == name


def test_registry_clearance_filtering():
    reg = ToolRegistry(populate_defaults=True)
    ro_list = reg.list_tools(ToolClearanceLevel.READ_ONLY)
    # READ_ONLY tools: original 7 core + intelligence/domain read tools (now >= 7)
    assert len(ro_list) >= 7
    assert all(t.clearance_level == ToolClearanceLevel.READ_ONLY for t in ro_list)

    wm_list = reg.list_tools(ToolClearanceLevel.WORKSPACE_MUTATION)
    assert len(wm_list) >= 6
    assert all(t.clearance_level == ToolClearanceLevel.WORKSPACE_MUTATION for t in wm_list)

    se_list = reg.list_tools(ToolClearanceLevel.SYSTEM_EXECUTION)
    assert len(se_list) >= 2
    assert all(t.clearance_level == ToolClearanceLevel.SYSTEM_EXECUTION for t in se_list)


def test_registry_provider_export_counts():
    reg = ToolRegistry(populate_defaults=True)
    openai_tools = reg.to_openai_tools()
    # All 37 tools exported to each provider schema
    assert len(openai_tools) >= 15

    gemini_tools = reg.to_gemini_tools()
    assert len(gemini_tools) == 1
    assert len(gemini_tools[0]["functionDeclarations"]) >= 15

    claude_tools = reg.to_anthropic_tools()
    assert len(claude_tools) >= 15
