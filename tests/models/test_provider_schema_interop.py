"""Tests verifying multi-provider tool schema interoperability for Google Gemini, Anthropic Claude, and OpenAI."""

import json
import pytest
from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel
from prubeth.tools.core import ALL_CORE_TOOLS
from prubeth.tools.registry import ToolRegistry


class ComplexTool(BaseTool):
    name = "complex_analysis"
    description = "Performs complex multifaceted codebase analysis."
    clearance_level = ToolClearanceLevel.READ_ONLY
    parameters = [
        ToolParameter(name="target_dir", type="string", description="Directory to analyze.", required=True),
        ToolParameter(name="depth", type="integer", description="Scan depth.", required=False, default=3),
        ToolParameter(name="threshold", type="number", description="Complexity score threshold.", required=False, default=0.75),
        ToolParameter(name="strict_mode", type="boolean", description="Enforce strict checks.", required=False, default=True),
        ToolParameter(name="exclude_patterns", type="array", description="Patterns to exclude.", items={"type": "string"}, required=False),
        ToolParameter(name="format", type="string", description="Output format.", enum=["json", "yaml", "text"], required=False, default="json"),
    ]

    def execute(self, args, context=None):
        return ToolResult(success=True, output="Analysis complete")


def test_openai_schema_complex_types():
    tool = ComplexTool()
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "complex_analysis"
    props = fn["parameters"]["properties"]

    assert props["target_dir"]["type"] == "string"
    assert props["depth"]["type"] == "integer"
    assert props["threshold"]["type"] == "number"
    assert props["strict_mode"]["type"] == "boolean"
    assert props["exclude_patterns"]["type"] == "array"
    assert props["exclude_patterns"]["items"] == {"type": "string"}
    assert props["format"]["enum"] == ["json", "yaml", "text"]

    # Only target_dir is required
    assert fn["parameters"]["required"] == ["target_dir"]


def test_gemini_schema_complex_types():
    tool = ComplexTool()
    schema = tool.to_gemini_schema()
    assert schema["name"] == "complex_analysis"
    props = schema["parameters"]["properties"]

    assert props["target_dir"]["type"] == "STRING"
    assert props["depth"]["type"] == "INTEGER"
    assert props["threshold"]["type"] == "NUMBER"
    assert props["strict_mode"]["type"] == "BOOLEAN"
    assert props["exclude_patterns"]["type"] == "ARRAY"
    assert props["format"]["enum"] == ["json", "yaml", "text"]
    assert schema["parameters"]["required"] == ["target_dir"]


def test_anthropic_schema_complex_types():
    tool = ComplexTool()
    schema = tool.to_anthropic_schema()
    assert schema["name"] == "complex_analysis"
    props = schema["input_schema"]["properties"]

    assert props["target_dir"]["type"] == "string"
    assert props["depth"]["type"] == "integer"
    assert props["threshold"]["type"] == "number"
    assert props["strict_mode"]["type"] == "boolean"
    assert props["format"]["enum"] == ["json", "yaml", "text"]
    assert schema["input_schema"]["required"] == ["target_dir"]


@pytest.mark.parametrize("tool_cls", ALL_CORE_TOOLS)
def test_all_tools_schemas_are_json_serializable(tool_cls):
    tool = tool_cls()
    openai_s = tool.to_openai_schema()
    gemini_s = tool.to_gemini_schema()
    anthropic_s = tool.to_anthropic_schema()

    # Invariant: Every schema must serialize cleanly to UTF-8 JSON without circular references or serialization errors
    json_o = json.dumps(openai_s)
    json_g = json.dumps(gemini_s)
    json_a = json.dumps(anthropic_s)

    assert len(json_o) > 20
    assert len(json_g) > 20
    assert len(json_a) > 20


def test_registry_schemas_deterministic():
    reg = ToolRegistry(populate_defaults=True)
    o1 = reg.to_openai_tools()
    o2 = reg.to_openai_tools()
    assert json.dumps(o1, sort_keys=True) == json.dumps(o2, sort_keys=True)

    g1 = reg.to_gemini_tools()
    g2 = reg.to_gemini_tools()
    assert json.dumps(g1, sort_keys=True) == json.dumps(g2, sort_keys=True)

    a1 = reg.to_anthropic_tools()
    a2 = reg.to_anthropic_tools()
    assert json.dumps(a1, sort_keys=True) == json.dumps(a2, sort_keys=True)
