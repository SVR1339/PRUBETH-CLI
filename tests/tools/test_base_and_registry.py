"""Tests for PRUBETH Base Tool Architecture and Central Tool Registry."""

import pytest
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel
from prubeth.tools.registry import ToolRegistry, get_default_registry
from prubeth.tools.core import ALL_CORE_TOOLS
from prubeth.tools.intelligence import ALL_INTELLIGENCE_TOOLS


class DummyEchoTool(BaseTool):
    name = "dummy_echo"
    description = "Echoes back the message."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(name="message", type="string", description="The text to echo.", required=True),
        ToolParameter(name="count", type="integer", description="Repetition count.", required=False, default=1),
        ToolParameter(name="uppercase", type="boolean", description="Whether to uppercase.", required=False, default=False),
        ToolParameter(name="mode", type="string", description="Mode enum.", required=False, enum=["fast", "slow"]),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation failed: {err}", exit_code=1)
        msg = str(args.get("message", ""))
        cnt = int(args.get("count", 1) or 1)
        if args.get("uppercase"):
            msg = msg.upper()
        res = " ".join([msg] * cnt)
        return ToolResult(success=True, output=res, exit_code=0, metadata={"length": len(res)})


class DummyMutationTool(BaseTool):
    name = "dummy_mutate"
    description = "Mutates workspace state."
    clearance_level = ToolClearanceLevel.WORKSPACE_MUTATION
    parameters = [
        ToolParameter(name="target_file", type="string", description="File to mutate.", required=True)
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        return ToolResult(success=True, output="Mutated successfully", exit_code=0)


class DummyExecTool(BaseTool):
    name = "dummy_exec"
    description = "Executes arbitrary system command."
    clearance_level = ToolClearanceLevel.SYSTEM_EXECUTION
    parameters = [
        ToolParameter(name="cmd", type="string", description="Command string.", required=True)
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        return ToolResult(success=True, output="Executed cmd", exit_code=0)


# =========================================================================
# ToolClearanceLevel & ToolParameter Tests
# =========================================================================

def test_clearance_levels():
    assert ToolClearanceLevel.READ_ONLY.value == "read_only"
    assert ToolClearanceLevel.WORKSPACE_MUTATION.value == "workspace_mutation"
    assert ToolClearanceLevel.SYSTEM_EXECUTION.value == "system_execution"


def test_tool_parameter_schema_basic():
    p = ToolParameter(name="path", type="string", description="Target file path.")
    schema = p.to_json_schema()
    assert schema["type"] == "string"
    assert schema["description"] == "Target file path."
    assert "default" not in schema
    assert "enum" not in schema


def test_tool_parameter_schema_with_enum_and_default():
    p = ToolParameter(
        name="log_level",
        type="string",
        description="Logging level",
        required=False,
        default="info",
        enum=["debug", "info", "warn", "error"]
    )
    schema = p.to_json_schema()
    assert schema["default"] == "info"
    assert schema["enum"] == ["debug", "info", "warn", "error"]


def test_tool_parameter_schema_array_items():
    p = ToolParameter(
        name="tags",
        type="array",
        description="List of tag names",
        items={"type": "string"}
    )
    schema = p.to_json_schema()
    assert schema["type"] == "array"
    assert schema["items"] == {"type": "string"}


# =========================================================================
# ToolResult Tests
# =========================================================================

def test_tool_result_creation_and_dict():
    res = ToolResult(success=True, output="Done", exit_code=0, metadata={"turn": 1})
    assert res.success is True
    assert res.output == "Done"
    assert str(res) == "Done"
    d = res.to_dict()
    assert d["success"] is True
    assert d["output"] == "Done"
    assert d["exit_code"] == 0
    assert d["metadata"]["turn"] == 1


# =========================================================================
# BaseTool Validation & Multi-Provider Schema Generation Tests
# =========================================================================

def test_base_tool_validate_args_success():
    tool = DummyEchoTool()
    ok, err = tool.validate_args({"message": "hello", "count": 2, "uppercase": True, "mode": "fast"})
    assert ok is True
    assert err is None


def test_base_tool_validate_args_missing_required():
    tool = DummyEchoTool()
    ok, err = tool.validate_args({"count": 2})
    assert ok is False
    assert "Missing required parameter: 'message'" in err


def test_base_tool_validate_args_type_mismatch():
    tool = DummyEchoTool()
    ok, err = tool.validate_args({"message": 12345})
    assert ok is False
    assert "must be a string" in err

    ok2, err2 = tool.validate_args({"message": "test", "count": "not_an_int"})
    assert ok2 is False
    assert "must be an integer" in err2

    ok3, err3 = tool.validate_args({"message": "test", "uppercase": "yes"})
    assert ok3 is False
    assert "must be a boolean" in err3


def test_base_tool_validate_args_invalid_enum():
    tool = DummyEchoTool()
    ok, err = tool.validate_args({"message": "test", "mode": "warp_speed"})
    assert ok is False
    assert "must be one of ['fast', 'slow']" in err


def test_base_tool_openai_schema_generation():
    tool = DummyEchoTool()
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "dummy_echo"
    assert fn["description"] == "Echoes back the message."
    assert "message" in fn["parameters"]["properties"]
    assert "message" in fn["parameters"]["required"]
    assert "count" in fn["parameters"]["properties"]
    assert "count" not in fn["parameters"]["required"]


def test_base_tool_gemini_schema_generation():
    tool = DummyEchoTool()
    schema = tool.to_gemini_schema()
    assert schema["name"] == "dummy_echo"
    params = schema["parameters"]
    assert params["type"] == "OBJECT"
    assert params["properties"]["message"]["type"] == "STRING"
    assert params["properties"]["count"]["type"] == "INTEGER"
    assert params["properties"]["uppercase"]["type"] == "BOOLEAN"
    assert "message" in params["required"]


def test_base_tool_anthropic_schema_generation():
    tool = DummyEchoTool()
    schema = tool.to_anthropic_schema()
    assert schema["name"] == "dummy_echo"
    assert schema["description"] == "Echoes back the message."
    assert schema["input_schema"]["type"] == "object"
    assert "message" in schema["input_schema"]["properties"]
    assert "message" in schema["input_schema"]["required"]


def test_base_tool_execution():
    tool = DummyEchoTool()
    res = tool.execute({"message": "prubeth", "count": 3, "uppercase": True})
    assert res.success is True
    assert res.output == "PRUBETH PRUBETH PRUBETH"
    assert res.metadata["length"] == 23


# =========================================================================
# ToolRegistry Tests
# =========================================================================

def test_registry_default_population():
    reg = ToolRegistry(populate_defaults=True)
    # Registry has grown: 15 core + 10 intelligence + 12 domain/verification tools = 37 total
    assert len(reg) >= len(ALL_CORE_TOOLS) + len(ALL_INTELLIGENCE_TOOLS)
    assert reg.has("read_file")
    assert reg.has("write_file")
    assert reg.has("edit_file")
    assert reg.has("run_shell")
    assert reg.has("git_status")


def test_registry_empty_initialization():
    reg = ToolRegistry(populate_defaults=False)
    assert len(reg) == 0


def test_registry_register_and_unregister():
    reg = ToolRegistry(populate_defaults=False)
    tool = DummyEchoTool()
    reg.register(tool)
    assert len(reg) == 1
    assert reg.has("dummy_echo")
    assert "dummy_echo" in reg

    unreg_ok = reg.unregister("dummy_echo")
    assert unreg_ok is True
    assert len(reg) == 0
    assert not reg.has("dummy_echo")

    # Unregister nonexistent returns False
    assert reg.unregister("dummy_echo") is False


def test_registry_register_class_directly():
    reg = ToolRegistry(populate_defaults=False)
    reg.register(DummyEchoTool)
    assert reg.has("dummy_echo")


def test_registry_register_invalid_type_raises():
    reg = ToolRegistry(populate_defaults=False)
    with pytest.raises(TypeError):
        reg.register(object())  # type: ignore


def test_registry_filter_by_clearance():
    reg = ToolRegistry(populate_defaults=False)
    reg.register(DummyEchoTool())
    reg.register(DummyMutationTool())
    reg.register(DummyExecTool())

    ro_tools = reg.list_tools(ToolClearanceLevel.READ_ONLY)
    assert len(ro_tools) == 1
    assert ro_tools[0].name == "dummy_echo"

    wm_tools = reg.list_tools(ToolClearanceLevel.WORKSPACE_MUTATION)
    assert len(wm_tools) == 1
    assert wm_tools[0].name == "dummy_mutate"

    exec_tools = reg.list_tools(ToolClearanceLevel.SYSTEM_EXECUTION)
    assert len(exec_tools) == 1
    assert exec_tools[0].name == "dummy_exec"


def test_registry_export_openai_tools():
    reg = ToolRegistry(populate_defaults=False)
    reg.register(DummyEchoTool())
    tools = reg.to_openai_tools()
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "dummy_echo"


def test_registry_export_gemini_tools():
    reg = ToolRegistry(populate_defaults=False)
    reg.register(DummyEchoTool())
    gemini_tools = reg.to_gemini_tools()
    assert len(gemini_tools) == 1
    assert "functionDeclarations" in gemini_tools[0]
    assert gemini_tools[0]["functionDeclarations"][0]["name"] == "dummy_echo"


def test_registry_export_anthropic_tools():
    reg = ToolRegistry(populate_defaults=False)
    reg.register(DummyEchoTool())
    claude_tools = reg.to_anthropic_tools()
    assert len(claude_tools) == 1
    assert claude_tools[0]["name"] == "dummy_echo"
    assert "input_schema" in claude_tools[0]


def test_registry_execute_dispatch_success():
    reg = ToolRegistry(populate_defaults=False)
    reg.register(DummyEchoTool())
    res = reg.execute("dummy_echo", {"message": "hello"})
    assert res.success is True
    assert res.output == "hello"


def test_registry_execute_unknown_tool():
    reg = ToolRegistry(populate_defaults=False)
    res = reg.execute("nonexistent_tool", {})
    assert res.success is False
    assert res.exit_code == 404
    assert "Unknown tool" in res.output


def test_registry_execute_validation_error():
    reg = ToolRegistry(populate_defaults=False)
    reg.register(DummyEchoTool())
    res = reg.execute("dummy_echo", {})  # missing message
    assert res.success is False
    assert res.exit_code == 400
    assert "Validation Error" in res.output


def test_get_default_registry_singleton():
    r1 = get_default_registry()
    r2 = get_default_registry()
    assert r1 is r2
    assert len(r1) >= 15
