"""PRUBETH Typed Tool Architecture & Multi-Provider Invariant Contract.

Defines clearance levels, parameter specifications, standardized results,
and base tool class with schema generation for Google Gemini, Anthropic Claude,
and OpenAI / OpenRouter endpoints.
"""

from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Union


class ToolClearanceLevel(enum.Enum):
    """Execution clearance classification for security enforcement."""
    READ_ONLY = "read_only"
    WORKSPACE_MUTATION = "workspace_mutation"
    SYSTEM_EXECUTION = "system_execution"


@dataclass
class ToolParameter:
    """Specification of an individual tool argument."""
    name: str
    type: str  # "string", "integer", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    items: Optional[Dict[str, Any]] = None

    def to_json_schema(self) -> Dict[str, Any]:
        """Converts parameter definition to JSON Schema property format."""
        schema: Dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum is not None:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        if self.items is not None and self.type == "array":
            schema["items"] = self.items
        return schema


@dataclass
class ToolResult:
    """Standardized execution outcome across all tools."""
    success: bool
    output: str
    exit_code: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, output: str, metadata: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Convenience constructor for successful tool execution."""
        return cls(success=True, output=output, exit_code=0, metadata=metadata or {})

    @classmethod
    def fail(cls, output: str, exit_code: int = 1, metadata: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Convenience constructor for failed tool execution."""
        return cls(success=False, output=output, exit_code=exit_code, metadata=metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "exit_code": self.exit_code,
            "metadata": self.metadata,
        }

    @property
    def error(self) -> str:
        """Convenience property exposing output when execution fails."""
        return "" if self.success else self.output

    def __str__(self) -> str:
        return self.output


class BaseTool(abc.ABC):
    """Abstract base class for all PRUBETH autonomous developer tools."""

    name: str = ""
    description: str = ""
    clearance_level: ToolClearanceLevel = ToolClearanceLevel.READ_ONLY
    parameters: List[ToolParameter] = []

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None, **kwargs):
        import os
        from pathlib import Path
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        if hasattr(self, "get_parameters") and callable(getattr(self, "get_parameters")):
            self.parameters = self.get_parameters()

    def validate_args(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validates incoming arguments against parameter specifications."""
        if not isinstance(args, dict):
            return False, f"Expected arguments dictionary, received {type(args).__name__}"

        for param in self.parameters:
            if param.required and param.name not in args:
                return False, f"Missing required parameter: '{param.name}'"

            if param.name in args:
                val = args[param.name]
                if param.type == "string" and not isinstance(val, str):
                    return False, f"Parameter '{param.name}' must be a string, got {type(val).__name__}"
                elif param.type == "integer" and not isinstance(val, int):
                    return False, f"Parameter '{param.name}' must be an integer, got {type(val).__name__}"
                elif param.type == "boolean" and not isinstance(val, bool):
                    return False, f"Parameter '{param.name}' must be a boolean, got {type(val).__name__}"
                elif param.type == "array" and not isinstance(val, (list, tuple)):
                    return False, f"Parameter '{param.name}' must be a list, got {type(val).__name__}"
                elif param.type == "object" and not isinstance(val, dict):
                    return False, f"Parameter '{param.name}' must be a dict, got {type(val).__name__}"

                if param.enum is not None and val not in param.enum:
                    return False, f"Parameter '{param.name}' must be one of {param.enum}, got '{val}'"

        return True, None

    @abc.abstractmethod
    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        """Executes the tool with validated arguments."""
        pass

    def to_openai_schema(self) -> Dict[str, Any]:
        """Converts tool declaration to OpenAI / OpenRouter function calling format."""
        properties = {}
        required = []

        for p in self.parameters:
            properties[p.name] = p.to_json_schema()
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def to_gemini_schema(self) -> Dict[str, Any]:
        """Converts tool declaration to Google Gemini FunctionDeclaration format."""
        properties = {}
        required = []

        # Map types to OpenAPI/Gemini type strings
        type_map = {
            "string": "STRING",
            "integer": "INTEGER",
            "number": "NUMBER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
        }

        for p in self.parameters:
            prop_def: Dict[str, Any] = {
                "type": type_map.get(p.type, "STRING"),
                "description": p.description,
            }
            if p.enum:
                prop_def["enum"] = p.enum
            if p.items and p.type == "array":
                prop_def["items"] = p.items
            properties[p.name] = prop_def
            if p.required:
                required.append(p.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "OBJECT",
                "properties": properties,
                "required": required,
            },
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Converts tool declaration to Anthropic Claude tool specification format."""
        properties = {}
        required = []

        for p in self.parameters:
            properties[p.name] = p.to_json_schema()
            if p.required:
                required.append(p.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
