"""PRUBETH MCP (Model Context Protocol) JSON-RPC 2.0 Protocol Specifications.

Defines typed dataclasses and serializers for MCP client-server communication:
tools/list, tools/call, resources/list, resources/read, and ping/initialize.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union

@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MCPResource:
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None

@dataclass
class MCPRequest:
    jsonrpc: str = "2.0"
    id: Union[int, str] = 1
    method: str = ""
    params: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"jsonrpc": self.jsonrpc, "id": self.id, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        return d

@dataclass
class MCPResponse:
    jsonrpc: str
    id: Union[int, str]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPResponse":
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id", 1),
            result=data.get("result"),
            error=data.get("error")
        )
