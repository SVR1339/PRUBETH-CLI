"""PRUBETH All 37 Tools Schema Export, Validation & Boundary Permutations Matrix.

Exhaustively verifies every one of the 37 tools in ToolRegistry:
- OpenAI Function Calling schema structure and non-empty description
- Google Gemini FunctionDeclaration schema specification
- Anthropic Claude tool input_schema structure
- Boundary input validation: empty arguments dictionary handling
- Resilience against arbitrary extraneous unknown argument injections
"""

from __future__ import annotations

import pytest
from prubeth.tools.registry import get_default_registry, ToolRegistry
from prubeth.tools.base import BaseTool


REGISTRY = get_default_registry()
ALL_TOOL_NAMES = sorted(list(REGISTRY._tools.keys()))


# ============================================================================
# 1. Total Registered Count Invariant
# ============================================================================

def test_registry_contains_all_37_tools():
    assert len(REGISTRY) == 37


# ============================================================================
# 2. OpenAI Function Calling Schema Matrix (37 Tests)
# ============================================================================

@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_tool_openai_schema_conformance(tool_name: str):
    tool = REGISTRY.get(tool_name)
    assert tool is not None

    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == tool_name
    assert isinstance(fn["description"], str)
    assert len(fn["description"].strip()) > 0
    assert "parameters" in fn
    assert fn["parameters"]["type"] == "object"
    assert "properties" in fn["parameters"]


# ============================================================================
# 3. Google Gemini FunctionDeclaration Schema Matrix (37 Tests)
# ============================================================================

@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_tool_gemini_schema_conformance(tool_name: str):
    tool = REGISTRY.get(tool_name)
    assert tool is not None

    schema = tool.to_gemini_schema()
    assert schema["name"] == tool_name
    assert isinstance(schema["description"], str)
    assert len(schema["description"].strip()) > 0
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "OBJECT"
    assert "properties" in schema["parameters"]


# ============================================================================
# 4. Anthropic Claude Tool Schema Matrix (37 Tests)
# ============================================================================

@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_tool_anthropic_schema_conformance(tool_name: str):
    tool = REGISTRY.get(tool_name)
    assert tool is not None

    schema = tool.to_anthropic_schema()
    assert schema["name"] == tool_name
    assert isinstance(schema["description"], str)
    assert len(schema["description"].strip()) > 0
    assert "input_schema" in schema
    assert schema["input_schema"]["type"] == "object"
    assert "properties" in schema["input_schema"]


# ============================================================================
# 5. Empty Arguments Validation Matrix (37 Tests)
# ============================================================================

@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_tool_empty_arguments_validation(tool_name: str):
    tool = REGISTRY.get(tool_name)
    assert tool is not None

    # Must return a tuple of (bool, Optional[str]) without throwing an uncaught exception
    valid, msg = tool.validate_args({})
    assert isinstance(valid, bool)
    assert msg is None or isinstance(msg, str)
    if not valid and msg is not None:
        assert len(msg.strip()) > 0


# ============================================================================
# 6. Unknown Argument Injection Resilience Matrix (37 Tests)
# ============================================================================

@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_tool_unknown_argument_injection_resilience(tool_name: str):
    tool = REGISTRY.get(tool_name)
    assert tool is not None

    bogus_payload = {
        "__adversarial_injection__": "DROP TABLE users;",
        "__extra_token__": 99999,
        "__meta_null__": None
    }
    # Must gracefully handle unexpected keys without crashing
    valid, msg = tool.validate_args(bogus_payload)
    assert isinstance(valid, bool)
    assert msg is None or isinstance(msg, str)
