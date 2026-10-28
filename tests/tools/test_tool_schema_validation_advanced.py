"""Advanced schema validation, boundary conditions, and edge-case execution tests for PRUBETH core tools."""

import os
import pytest
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel
from prubeth.tools.registry import ToolRegistry, get_default_registry
from prubeth.tools.core.read_file import ReadFileTool
from prubeth.tools.core.write_file import WriteFileTool
from prubeth.tools.core.edit_file import EditFileTool
from prubeth.tools.core.list_dir import ListDirTool
from prubeth.tools.core.grep_search import GrepSearchTool
from prubeth.tools.core.glob_search import GlobSearchTool


# =========================================================================
# Custom Tool Invariants & Edge Cases
# =========================================================================

class SpecialCharsTool(BaseTool):
    name = "special_chars_tool"
    description = "Tests special characters and edge-case parameters."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(name="regex_pattern", type="string", description="Regex string with special chars: ^[a-z]+$.", required=True),
        ToolParameter(name="options", type="array", description="List of options.", items={"type": "string"}, required=False, default=["opt1", "opt2"]),
        ToolParameter(name="config_dict", type="object", description="Arbitrary JSON config object.", required=False),
        ToolParameter(name="float_val", type="number", description="Floating point numeric value.", required=False, default=3.14159),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Err: {err}", exit_code=1)
        return ToolResult(success=True, output="Special characters processed cleanly", exit_code=0)


def test_special_chars_tool_openai_schema():
    tool = SpecialCharsTool()
    schema = tool.to_openai_schema()
    props = schema["function"]["parameters"]["properties"]
    assert props["regex_pattern"]["type"] == "string"
    assert props["options"]["type"] == "array"
    assert props["config_dict"]["type"] == "object"
    assert props["float_val"]["type"] == "number"


def test_special_chars_tool_gemini_schema():
    tool = SpecialCharsTool()
    schema = tool.to_gemini_schema()
    props = schema["parameters"]["properties"]
    assert props["regex_pattern"]["type"] == "STRING"
    assert props["options"]["type"] == "ARRAY"
    assert props["config_dict"]["type"] == "OBJECT"
    assert props["float_val"]["type"] == "NUMBER"


def test_special_chars_tool_anthropic_schema():
    tool = SpecialCharsTool()
    schema = tool.to_anthropic_schema()
    props = schema["input_schema"]["properties"]
    assert props["regex_pattern"]["type"] == "string"
    assert props["options"]["type"] == "array"
    assert props["config_dict"]["type"] == "object"
    assert props["float_val"]["type"] == "number"


def test_special_chars_tool_validation():
    tool = SpecialCharsTool()
    # Missing required
    ok1, err1 = tool.validate_args({})
    assert ok1 is False
    assert "regex_pattern" in err1

    # Valid execution
    res = tool.execute({"regex_pattern": "^[0-9]+$", "float_val": 2.718})
    assert res.success is True
    assert "processed cleanly" in res.output


# =========================================================================
# Empty File & Boundary Conditions
# =========================================================================

def test_read_file_tool_empty_file(tmp_path: Path):
    empty_f = tmp_path / "empty.txt"
    empty_f.write_text("", encoding="utf-8")

    tool = ReadFileTool()
    res = tool.execute({"path": str(empty_f)})
    assert res.success is True
    assert res.output == ""
    assert res.metadata["total_lines"] == 0


def test_write_file_tool_empty_content(tmp_path: Path):
    target = tmp_path / "created_empty.txt"
    tool = WriteFileTool()
    res = tool.execute({"path": str(target), "content": ""})
    assert res.success is True
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == ""


def test_edit_file_tool_empty_replacement(tmp_path: Path):
    target = tmp_path / "remove_target.txt"
    target.write_text("line 1\ndelete_this_line\nline 3\n", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target),
        "target": "delete_this_line\n",
        "replacement": ""
    })
    assert res.success is True
    content = target.read_text(encoding="utf-8")
    assert "delete_this_line" not in content
    assert "line 1\nline 3\n" == content


def test_edit_file_tool_rejects_empty_target(tmp_path: Path):
    target = tmp_path / "test.txt"
    target.write_text("content", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({"path": str(target), "target": "", "replacement": "new"})
    assert res.success is False
    assert "cannot be empty" in res.output


# =========================================================================
# Grep & Glob Search Advanced Filtering
# =========================================================================

def test_grep_search_empty_matches_returns_zero(tmp_path: Path):
    (tmp_path / "f1.txt").write_text("apple banana orange\n", encoding="utf-8")
    (tmp_path / "f2.txt").write_text("grape melon peach\n", encoding="utf-8")

    tool = GrepSearchTool()
    res = tool.execute({"query": "pineapple", "path": str(tmp_path)})
    assert res.success is True
    assert res.metadata["matches"] == 0
    assert "No matches found" in res.output


def test_glob_search_nested_hierarchies(tmp_path: Path):
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c" / "deep.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "a" / "b" / "middle.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / "a" / "top.py").write_text("z = 3\n", encoding="utf-8")

    tool = GlobSearchTool()
    res = tool.execute({"pattern": "a/**/*.py", "path": str(tmp_path)})
    assert res.success is True
    assert res.metadata["count"] == 3


def test_registry_tool_override_and_replace():
    reg = ToolRegistry(populate_defaults=False)
    tool1 = SpecialCharsTool()
    reg.register(tool1)
    assert len(reg) == 1

    # Re-registering tool with same name overrides
    tool2 = SpecialCharsTool()
    reg.register(tool2)
    assert len(reg) == 1
    assert reg.get("special_chars_tool") is tool2


def test_registry_execute_with_extra_kwargs_succeeds():
    reg = ToolRegistry(populate_defaults=True)
    # Extra unexpected arguments should not crash execute
    res = reg.execute("read_file", {"path": "nonexistent.txt", "unsupported_extra_arg": 12345})
    assert res.exit_code == 404


def test_base_tool_abstract_instantiation_raises():
    with pytest.raises(TypeError):
        BaseTool()  # abstract class cannot be instantiated directly


def test_tool_parameter_repr():
    p = ToolParameter(name="test_param", type="string", description="desc", required=True, default="def")
    s = p.to_json_schema()
    assert s["type"] == "string"
    assert s["default"] == "def"


def test_tool_result_metadata_modification():
    res = ToolResult(success=True, output="output")
    res.metadata["custom_key"] = "custom_val"
    assert res.to_dict()["metadata"]["custom_key"] == "custom_val"


def test_tool_clearance_level_strings():
    assert str(ToolClearanceLevel.READ_ONLY.value) == "read_only"
    assert str(ToolClearanceLevel.WORKSPACE_MUTATION.value) == "workspace_mutation"
    assert str(ToolClearanceLevel.SYSTEM_EXECUTION.value) == "system_execution"


def test_tool_registry_len_and_contains():
    reg = ToolRegistry(populate_defaults=True)
    assert len(reg) >= 15
    assert "write_file" in reg
    assert "phantom" not in reg
