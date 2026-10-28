"""PRUBETH Central Tool Registry.

Manages tool lifecycle, clearance permissions, schema exports for multi-provider
native tool calling, and tool dispatch.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Type, Union

from prubeth.tools.base import BaseTool, ToolClearanceLevel, ToolResult
from prubeth.tools.core import ALL_CORE_TOOLS
from prubeth.tools.intelligence import ALL_INTELLIGENCE_TOOLS
from prubeth.tools.verification import ALL_VERIFICATION_TOOLS
from prubeth.tools.domain import ALL_DOMAIN_TOOLS


class ToolRegistry:
    """Central registry and schema broker for PRUBETH autonomous developer tools."""

    def __init__(self, populate_defaults: bool = True):
        self._tools: Dict[str, BaseTool] = {}
        if populate_defaults:
            for tool_cls in ALL_CORE_TOOLS:
                self.register(tool_cls())
            for tool_cls in ALL_INTELLIGENCE_TOOLS:
                self.register(tool_cls())
            for tool_cls in ALL_VERIFICATION_TOOLS:
                self.register(tool_cls())
            for tool_cls in ALL_DOMAIN_TOOLS:
                self.register(tool_cls())

    def register(self, tool: Union[BaseTool, Type[BaseTool]]) -> None:
        """Registers a tool instance or tool class."""
        instance = tool() if isinstance(tool, type) else tool
        if not isinstance(instance, BaseTool):
            raise TypeError(f"Tool must inherit from BaseTool, got {type(tool).__name__}")
        if not instance.name:
            raise ValueError("Tool name cannot be empty.")
        self._tools[instance.name] = instance

    def unregister(self, name: str) -> bool:
        """Removes a tool from registry by name."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[BaseTool]:
        """Looks up a tool by name."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Checks if a tool is registered."""
        return name in self._tools

    def list_tools(self, clearance: Optional[ToolClearanceLevel] = None) -> List[BaseTool]:
        """Lists registered tools, optionally filtered by clearance level."""
        if clearance is None:
            return list(self._tools.values())
        return [t for t in self._tools.values() if t.clearance_level == clearance]

    def to_openai_tools(self, clearance: Optional[ToolClearanceLevel] = None) -> List[Dict[str, Any]]:
        """Exports tools as OpenAI function call specifications."""
        return [t.to_openai_schema() for t in self.list_tools(clearance)]

    def to_gemini_tools(self, clearance: Optional[ToolClearanceLevel] = None) -> List[Dict[str, Any]]:
        """Exports tools wrapped in Google Gemini FunctionDeclarations."""
        funcs = [t.to_gemini_schema() for t in self.list_tools(clearance)]
        return [{"functionDeclarations": funcs}] if funcs else []

    def to_anthropic_tools(self, clearance: Optional[ToolClearanceLevel] = None) -> List[Dict[str, Any]]:
        """Exports tools in Anthropic Claude specification format."""
        return [t.to_anthropic_schema() for t in self.list_tools(clearance)]

    def execute(self, name: str, args: Dict[str, Any], context: Any = None) -> ToolResult:
        """Validates and executes a tool."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output=f"Error: Unknown tool '{name}'. Available: {', '.join(sorted(self._tools.keys()))}",
                exit_code=404
            )

        valid, err = tool.validate_args(args)
        if not valid:
            return ToolResult(
                success=False,
                output=f"Validation Error in {name}: {err}",
                exit_code=400
            )

        try:
            return tool.execute(args, context=context)
        except TypeError:
            return tool.execute(args)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


_global_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Returns the shared global tool registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry(populate_defaults=True)
    return _global_registry
