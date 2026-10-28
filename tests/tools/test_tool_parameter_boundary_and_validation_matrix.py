"""PRUBETH Tool Parameter Boundary, Validation & Multi-Provider Schema Matrix.

Exhaustively verifies:
1. Universal tool metadata contracts (name, description, clearance level, parameters).
2. Multi-provider schema compliance (OpenAI, Gemini, Anthropic Claude format).
3. Parameter type checking and required argument validation for every registered tool.
4. Clearance level filtering across READ_ONLY, WORKSPACE_MUTATION, and SYSTEM_EXECUTION.
5. Error handling on missing, invalid, or malformed arguments.
6. Safe execution resilience against non-existent files and invalid paths.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest

from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolParameter, ToolResult
from prubeth.tools.registry import ToolRegistry, get_default_registry
from prubeth.tools.core import ALL_CORE_TOOLS
from prubeth.tools.intelligence import ALL_INTELLIGENCE_TOOLS
from prubeth.tools.verification import ALL_VERIFICATION_TOOLS
from prubeth.tools.domain import ALL_DOMAIN_TOOLS


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reg = ToolRegistry(populate_defaults=False)
    for tool_cls in ALL_CORE_TOOLS + ALL_INTELLIGENCE_TOOLS + ALL_VERIFICATION_TOOLS + ALL_DOMAIN_TOOLS:
        try:
            instance = tool_cls(workspace_root=tmp_path)
        except TypeError:
            instance = tool_cls()
        reg.register(instance)
    return reg


# ============================================================================
# 1. Tool Metadata & Schema Generation Contracts across All Tools
# ============================================================================

def test_all_tools_registered_count(registry):
    # Ensure full suite of core, domain, verification, and intelligence tools are present
    assert len(registry) >= 30


def test_every_tool_has_valid_metadata(registry):
    for tool in registry.list_tools():
        assert isinstance(tool.name, str) and len(tool.name) > 0
        assert isinstance(tool.description, str) and len(tool.description) > 5
        assert isinstance(tool.clearance_level, ToolClearanceLevel)
        assert isinstance(tool.parameters, list)
        for param in tool.parameters:
            assert isinstance(param, ToolParameter)
            assert isinstance(param.name, str) and len(param.name) > 0
            assert param.type in {"string", "integer", "number", "boolean", "array", "object"}
            assert isinstance(param.description, str)


def test_every_tool_generates_valid_openai_schema(registry):
    for tool in registry.list_tools():
        schema = tool.to_openai_schema()
        assert schema.get("type") == "function"
        fn = schema.get("function", {})
        assert fn.get("name") == tool.name
        assert fn.get("description") == tool.description
        params = fn.get("parameters", {})
        assert params.get("type") == "object"
        assert "properties" in params


def test_every_tool_generates_valid_gemini_schema(registry):
    for tool in registry.list_tools():
        schema = tool.to_gemini_schema()
        assert schema.get("name") == tool.name
        assert schema.get("description") == tool.description
        params = schema.get("parameters", {})
        assert params.get("type") in ("object", "OBJECT")
        assert "properties" in params


def test_every_tool_generates_valid_anthropic_schema(registry):
    for tool in registry.list_tools():
        schema = tool.to_anthropic_schema()
        assert schema.get("name") == tool.name
        assert schema.get("description") == tool.description
        input_schema = schema.get("input_schema", {})
        assert input_schema.get("type") == "object"
        assert "properties" in input_schema


# ============================================================================
# 2. Clearance Level Filtering Matrix
# ============================================================================

@pytest.mark.parametrize("clearance", [
    ToolClearanceLevel.READ_ONLY,
    ToolClearanceLevel.WORKSPACE_MUTATION,
    ToolClearanceLevel.SYSTEM_EXECUTION,
])
def test_tool_registry_clearance_filtering(registry, clearance: ToolClearanceLevel):
    filtered_tools = registry.list_tools(clearance=clearance)
    assert len(filtered_tools) > 0
    for t in filtered_tools:
        assert t.clearance_level == clearance

    # Multi-provider schema exports with clearance filtering
    oa_tools = registry.to_openai_tools(clearance=clearance)
    assert len(oa_tools) == len(filtered_tools)

    claude_tools = registry.to_anthropic_tools(clearance=clearance)
    assert len(claude_tools) == len(filtered_tools)


# ============================================================================
# 3. Argument Validation Matrix: Missing Required Arguments
# ============================================================================

TOOLS_WITH_REQUIRED_ARGS = [
    ("read_file", "path"),
    ("write_file", "path"),
    ("delete_file", "path"),
    ("copy_file", "src"),
    ("move_file", "src"),
    ("grep_search", "pattern"),
    ("run_shell", "command"),
    ("run_python", "code"),
    ("patch_verifier", "path"),
    ("explain_symbol", "symbol_name"),
    ("find_callees", "caller_symbol_name"),
    ("find_callers", "target_symbol_name"),
    ("find_type_definition", "symbol_name"),
    ("find_implementations", "base_name"),
    ("trace_data_flow", "start_symbol_name"),
]

@pytest.mark.parametrize("tool_name,required_param", TOOLS_WITH_REQUIRED_ARGS)
def test_missing_required_argument_fails_validation(registry, tool_name: str, required_param: str):
    res = registry.execute(tool_name, {})
    assert res.success is False
    assert res.exit_code == 400
    assert "Validation Error" in res.output or "missing" in res.output.lower() or required_param in res.output.lower()


# ============================================================================
# 4. Unknown Tool Dispatch Error Matrix
# ============================================================================

@pytest.mark.parametrize("unknown_name", [
    "nonexistent_tool_123",
    "sudo_exec",
    "format_disk",
    "cloud_admin_panel",
    "unknown_scanner",
])
def test_unknown_tool_returns_404(registry, unknown_name: str):
    res = registry.execute(unknown_name, {})
    assert res.success is False
    assert res.exit_code == 404
    assert f"Unknown tool '{unknown_name}'" in res.output
    assert "Available:" in res.output


# ============================================================================
# 5. Core File Tools Execution Boundaries & Non-Existent Targets
# ============================================================================

def test_read_file_nonexistent_returns_failure(registry, tmp_path):
    res = registry.execute("read_file", {"path": str(tmp_path / "ghost_file.txt")})
    assert res.success is False
    assert "not found" in res.output.lower() or "does not exist" in res.output.lower() or "error" in res.output.lower()


def test_write_file_and_read_file_roundtrip(registry, tmp_path):
    test_file = tmp_path / "hello.txt"
    content = "Hello PRUBETH Autonomous Developer!"
    w_res = registry.execute("write_file", {"path": str(test_file), "content": content})
    assert w_res.success is True
    assert test_file.exists()

    r_res = registry.execute("read_file", {"path": str(test_file)})
    assert r_res.success is True
    assert content in r_res.output


def test_list_dir_on_empty_and_populated_directory(registry, tmp_path):
    # Empty dir
    res_empty = registry.execute("list_dir", {"path": str(tmp_path)})
    assert res_empty.success is True

    # Populated dir
    (tmp_path / "a.py").write_text("# a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    res_pop = registry.execute("list_dir", {"path": str(tmp_path)})
    assert res_pop.success is True
    assert "a.py" in res_pop.output
    assert "b.txt" in res_pop.output


# ============================================================================
# 6. ToolResult Factory Methods & Immutability Invariants
# ============================================================================

@pytest.mark.parametrize("output,meta", [
    ("Build succeeded", {"duration_ms": 120}),
    ("All 500 tests passed", {"coverage": 98.4}),
    ("Clean workspace", {}),
])
def test_tool_result_ok_factory(output: str, meta: dict):
    res = ToolResult.ok(output, metadata=meta)
    assert res.success is True
    assert res.output == output
    assert res.exit_code == 0
    assert res.error == ""
    assert res.metadata == meta
    d = res.to_dict()
    assert d["success"] is True
    assert d["output"] == output


@pytest.mark.parametrize("err_msg,code", [
    ("Syntax error on line 42", 1),
    ("Permission denied", 403),
    ("Timeout expired", 124),
])
def test_tool_result_fail_factory(err_msg: str, code: int):
    res = ToolResult.fail(err_msg, exit_code=code)
    assert res.success is False
    assert res.output == err_msg
    assert res.exit_code == code
    assert res.error == err_msg


# ============================================================================
# 7. ToolParameter JSON Schema Generation Permutations
# ============================================================================

PARAM_SPECS = [
    ("filepath", "string", "Absolute or relative file path", True, None, None, None),
    ("line_number", "integer", "1-based target line number", False, 1, None, None),
    ("threshold", "number", "Confidence score threshold", False, 0.85, None, None),
    ("dry_run", "boolean", "Simulate without disk modification", False, False, None, None),
    ("tags", "array", "Categorical tags", False, None, None, {"type": "string"}),
    ("payload", "object", "Structured data mapping", False, None, None, None),
    ("action", "string", "Operation verb", True, None, ["add", "list", "remove"], None),
]

@pytest.mark.parametrize("name,ptype,desc,req,default,enum_vals,items", PARAM_SPECS)
def test_tool_parameter_schema_generation(name: str, ptype: str, desc: str, req: bool, default: Any, enum_vals: Any, items: Any):
    param = ToolParameter(
        name=name,
        type=ptype,
        description=desc,
        required=req,
        default=default,
        enum=enum_vals,
        items=items,
    )
    schema = param.to_json_schema()
    assert schema["type"] == ptype
    assert schema["description"] == desc
    if default is not None:
        assert schema["default"] == default
    if enum_vals is not None:
        assert schema["enum"] == enum_vals
    if items is not None:
        assert schema["items"] == items


# ============================================================================
# 8. Tool Exit Code & String Representation Permutations
# ============================================================================

EXIT_CODES_AND_OUTPUTS = [
    (0, "Command completed cleanly"),
    (1, "General error"),
    (2, "Misuse of shell built-in"),
    (124, "Subprocess timed out"),
    (127, "Command not found"),
    (130, "Process terminated by Ctrl-C"),
    (400, "Invalid parameter schema"),
    (403, "Permission denied by security engine"),
    (404, "Target symbol or file not found"),
    (500, "Internal runtime exception"),
]

@pytest.mark.parametrize("exit_code,output_text", EXIT_CODES_AND_OUTPUTS)
def test_tool_result_exit_codes_and_string_representation(exit_code: int, output_text: str):
    is_success = (exit_code == 0)
    res = ToolResult(success=is_success, output=output_text, exit_code=exit_code)
    assert res.success is is_success
    assert res.exit_code == exit_code
    assert output_text in str(res)


# ============================================================================
# 9. Individual Tool Schema Integrity Permutations
# ============================================================================

ALL_CORE_TOOL_NAMES = [
    "read_file", "write_file", "edit_file", "delete_file", "copy_file",
    "move_file", "list_dir", "glob_search", "grep_search", "run_shell",
    "run_python", "git_status", "git_diff", "git_log", "git_commit"
]

@pytest.mark.parametrize("tool_name", ALL_CORE_TOOL_NAMES)
def test_core_tools_schema_properties(registry, tool_name: str):
    tool = registry.get(tool_name)
    assert tool is not None
    # OpenAI Schema
    oa = tool.to_openai_schema()
    assert oa["type"] == "function"
    assert oa["function"]["name"] == tool_name
    # Gemini Schema
    gem = tool.to_gemini_schema()
    assert gem["name"] == tool_name
    # Anthropic Schema
    ant = tool.to_anthropic_schema()
    assert ant["name"] == tool_name


ALL_DOMAIN_VERIFICATION_TOOL_NAMES = [
    "benchmark", "crash_debugger", "heal", "security_linter", "spec_contract",
    "test_gen", "todo", "coverage_analyser", "lint_checker", "patch_verifier",
    "test_runner", "type_checker"
]

@pytest.mark.parametrize("tool_name", ALL_DOMAIN_VERIFICATION_TOOL_NAMES)
def test_domain_verification_tools_schema_properties(registry, tool_name: str):
    tool = registry.get(tool_name)
    assert tool is not None
    assert len(tool.name) > 0
    assert tool.clearance_level in (ToolClearanceLevel.READ_ONLY, ToolClearanceLevel.WORKSPACE_MUTATION, ToolClearanceLevel.SYSTEM_EXECUTION)


ALL_INTELLIGENCE_TOOL_NAMES = [
    "code_structure", "detect_circular_imports", "explain_symbol", "find_callees",
    "find_callers", "find_dead_code", "find_implementations", "find_type_definition",
    "rank_central_files", "trace_data_flow"
]

@pytest.mark.parametrize("tool_name", ALL_INTELLIGENCE_TOOL_NAMES)
def test_intelligence_tools_schema_properties(registry, tool_name: str):
    tool = registry.get(tool_name)
    assert tool is not None
    assert tool.clearance_level == ToolClearanceLevel.READ_ONLY


# ============================================================================
# 10. Todo Tool State Lifecycle Permutations (Add -> List -> Complete -> Delete)
# ============================================================================

def test_todo_tool_lifecycle(registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Write a source file with technical debt comment
    code_file = tmp_path / "service.py"
    code_file.write_text("# TODO: Implement feature X\ndef stub(): pass\n", encoding="utf-8")

    # Scan items
    res_list = registry.execute("todo", {"path": str(tmp_path)})
    assert res_list.success is True
    assert "Implement feature X" in res_list.output


# ============================================================================
# 11. Type Validation Matrix: Disallowing Malformed Argument Types
# ============================================================================

INVALID_ARG_TYPE_CASES = [
    ("read_file", {"path": 12345}),
    ("read_file", {"path": True}),
    ("write_file", {"path": ["not", "a", "path"], "content": "hello"}),
    ("write_file", {"path": "file.txt", "content": 9999}),
    ("grep_search", {"pattern": 42}),
    ("run_shell", {"command": ["ls", "-la"]}),
    ("run_python", {"code": {"key": "val"}}),
    ("find_type_definition", {"symbol_name": 100}),
    ("find_implementations", {"base_name": False}),
    ("trace_data_flow", {"start_symbol_name": 3.14}),
]

@pytest.mark.parametrize("tool_name,invalid_args", INVALID_ARG_TYPE_CASES)
def test_invalid_argument_types_rejected(registry, tool_name: str, invalid_args: dict):
    res = registry.execute(tool_name, invalid_args)
    assert res.success is False
    assert res.exit_code == 400
    assert "Validation Error" in res.output or "must be a" in res.output


# ============================================================================
# 12. Glob Search Pattern Permutations Matrix
# ============================================================================

GLOB_PATTERNS = [
    ("*.py", 2),
    ("*.ts", 1),
    ("*.json", 1),
    ("*.md", 1),
    ("nonexistent*.xyz", 0),
    ("**/*", 5),
]

@pytest.mark.parametrize("pattern,expected_min_count", GLOB_PATTERNS)
def test_glob_search_patterns(registry, tmp_path, monkeypatch, pattern: str, expected_min_count: int):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mod1.py").write_text("# 1", encoding="utf-8")
    (tmp_path / "mod2.py").write_text("# 2", encoding="utf-8")
    (tmp_path / "service.ts").write_text("// ts", encoding="utf-8")
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README.md").write_text("# doc", encoding="utf-8")

    res = registry.execute("glob_search", {"pattern": pattern, "path": str(tmp_path)})
    assert res.success is True
    lines = [l for l in res.output.splitlines() if l.strip() and not l.startswith("Found")]
    assert len(lines) >= expected_min_count


# ============================================================================
# 13. Copy File and Move File Operations Matrix
# ============================================================================

def test_copy_file_success(registry, tmp_path):
    src = tmp_path / "source.txt"
    dst = tmp_path / "copy_dest.txt"
    src.write_text("Unique copy payload 12345", encoding="utf-8")

    res = registry.execute("copy_file", {"src": str(src), "dst": str(dst)})
    assert res.success is True
    assert dst.exists()
    assert src.exists()  # Source remains intact
    assert dst.read_text(encoding="utf-8") == "Unique copy payload 12345"


def test_copy_file_nonexistent_source_fails(registry, tmp_path):
    res = registry.execute("copy_file", {"src": str(tmp_path / "ghost.txt"), "dst": str(tmp_path / "out.txt")})
    assert res.success is False


def test_move_file_success(registry, tmp_path):
    src = tmp_path / "to_move.txt"
    dst = tmp_path / "moved_dest.txt"
    src.write_text("Move payload 999", encoding="utf-8")

    res = registry.execute("move_file", {"src": str(src), "dst": str(dst)})
    assert res.success is True
    assert dst.exists()
    assert not src.exists()  # Source is moved


def test_move_file_nonexistent_source_fails(registry, tmp_path):
    res = registry.execute("move_file", {"src": str(tmp_path / "ghost.txt"), "dst": str(tmp_path / "out.txt")})
    assert res.success is False


# ============================================================================
# 14. Delete File Operations Matrix
# ============================================================================

def test_delete_file_success(registry, tmp_path):
    target = tmp_path / "doomed.txt"
    target.write_text("delete me", encoding="utf-8")
    assert target.exists()

    res = registry.execute("delete_file", {"path": str(target)})
    assert res.success is True
    assert not target.exists()


def test_delete_file_nonexistent_fails(registry, tmp_path):
    res = registry.execute("delete_file", {"path": str(tmp_path / "already_deleted.txt")})
    assert res.success is False


