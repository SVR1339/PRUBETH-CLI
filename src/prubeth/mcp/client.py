"""PRUBETH MCP (Model Context Protocol) Stdio Client Transport.

Manages subprocess communication with local or remote MCP servers via JSON-RPC 2.0.
"""

import sys
import os
import json
import subprocess
import threading
import time
from typing import Dict, Any, List, Optional, Tuple

from prubeth.mcp.protocol import MCPRequest, MCPResponse, MCPTool, MCPResource

class MCPClient:
    """Manages an active MCP Server subprocess via standard input/output streams."""

    def __init__(self, name: str, command: str, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or os.environ.copy()
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._connected = False
        self.tools: List[MCPTool] = []
        self.resources: List[MCPResource] = []

    def connect(self, timeout: float = 5.0) -> bool:
        """Launches the MCP server subprocess and performs handshake."""
        if self._connected and self.process and self.process.poll() is None:
            return True

        cmd = [self.command] + self.args
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=self.env,
                bufsize=1
            )
            self._connected = True

            # Send initialize request
            init_res = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "clientInfo": {
                    "name": "prubeth-cli",
                    "version": "1.0.0"
                }
            }, timeout=timeout)

            if init_res.error:
                self.disconnect()
                return False

            # Send initialized notification
            self._send_notification("notifications/initialized")
            
            # Auto-discover tools and resources
            self.discover_capabilities()
            return True

        except Exception:
            self._connected = False
            if self.process:
                try:
                    self.process.kill()
                except Exception:
                    pass
                self.process = None
            return False

    def disconnect(self):
        """Terminates the MCP server subprocess cleanly."""
        self._connected = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    def is_alive(self) -> bool:
        """Checks if the subprocess is active and running."""
        return bool(self._connected and self.process and self.process.poll() is None)

    def discover_capabilities(self):
        """Discovers tools and resources supported by this MCP server."""
        if not self.is_alive():
            return

        # 1. Fetch Tools
        tool_res = self._send_request("tools/list", {})
        if not tool_res.error and isinstance(tool_res.result, dict):
            raw_tools = tool_res.result.get("tools", [])
            self.tools = [
                MCPTool(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {})
                )
                for t in raw_tools
            ]

        # 2. Fetch Resources
        res_res = self._send_request("resources/list", {})
        if not res_res.error and isinstance(res_res.result, dict):
            raw_resources = res_res.result.get("resources", [])
            self.resources = [
                MCPResource(
                    uri=r.get("uri", ""),
                    name=r.get("name", ""),
                    description=r.get("description"),
                    mime_type=r.get("mimeType")
                )
                for r in raw_resources
            ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Tuple[bool, str]:
        """Calls a specific tool on this MCP server."""
        if not self.is_alive():
            if not self.connect():
                return False, f"Failed to connect to MCP server '{self.name}'."

        res = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        }, timeout=timeout)

        if res.error:
            return False, f"MCP Error ({res.error.get('code')}): {res.error.get('message')}"

        result_obj = res.result or {}
        content_list = result_obj.get("content", [])
        if content_list and isinstance(content_list, list):
            texts = [c.get("text", "") for c in content_list if isinstance(c, dict) and "text" in c]
            return not result_obj.get("isError", False), "\n".join(texts)

        return True, json.dumps(result_obj, indent=2)

    def read_resource(self, uri: str, timeout: float = 15.0) -> Tuple[bool, str]:
        """Fetches resource contents from this MCP server."""
        if not self.is_alive():
            if not self.connect():
                return False, f"Failed to connect to MCP server '{self.name}'."

        res = self._send_request("resources/read", {"uri": uri}, timeout=timeout)
        if res.error:
            return False, f"MCP Resource Error: {res.error.get('message')}"

        contents = (res.result or {}).get("contents", [])
        if contents:
            item = contents[0]
            return True, item.get("text") or item.get("blob") or ""
        return False, "Empty resource contents."

    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 5.0) -> MCPResponse:
        """Sends a synchronous JSON-RPC request and waits for matching response."""
        with self._lock:
            self._request_id += 1
            req = MCPRequest(id=self._request_id, method=method, params=params)
            raw = json.dumps(req.to_dict()) + "\n"

            if not self.process or not self.process.stdin or not self.process.stdout:
                return MCPResponse(jsonrpc="2.0", id=req.id, error={"code": -32000, "message": "Server process disconnected"})

            try:
                self.process.stdin.write(raw)
                self.process.stdin.flush()

                # Read line response
                resp_line = self.process.stdout.readline()
                if not resp_line:
                    return MCPResponse(jsonrpc="2.0", id=req.id, error={"code": -32001, "message": "EOF received from MCP server"})

                data = json.loads(resp_line)
                return MCPResponse.from_dict(data)
            except Exception as e:
                return MCPResponse(jsonrpc="2.0", id=req.id, error={"code": -32603, "message": str(e)})

    def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Sends a fire-and-forget JSON-RPC notification (no id)."""
        with self._lock:
            payload = {"jsonrpc": "2.0", "method": method}
            if params is not None:
                payload["params"] = params
            raw = json.dumps(payload) + "\n"
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(raw)
                    self.process.stdin.flush()
                except Exception:
                    pass
