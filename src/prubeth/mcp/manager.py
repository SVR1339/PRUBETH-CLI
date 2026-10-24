"""PRUBETH MCP Multi-Server Registry & Tool Discovery Coordinator.

Subsystem 16: Discovers, manages, and executes tools from external MCP servers.
Integrates directly with PRUBETH's ToolExecutionEngine and SecurityEngine.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from prubeth.mcp.client import MCPClient
from prubeth.mcp.protocol import MCPTool, MCPResource

DEFAULT_MCP_CONFIG = {
    "mcpServers": {}
}

class MCPManager:
    """Manages active MCP servers and exposes tools to the runtime controller."""

    def __init__(self, workspace_root: Optional[Path] = None, config_path: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.config_path = config_path or (self.workspace_root / ".prubeth" / "mcp.json")
        self.servers: Dict[str, MCPClient] = {}
        self._ensure_config()
        self._load_servers_from_config()

    def _ensure_config(self):
        """Initializes empty mcp.json if it doesn't exist."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(DEFAULT_MCP_CONFIG, indent=2), encoding="utf-8")

    def _load_servers_from_config(self):
        """Loads MCP servers defined in mcp.json."""
        if not self.config_path.exists():
            return
        try:
            cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
            servers_dict = cfg.get("mcpServers", {})
            for name, s_info in servers_dict.items():
                cmd = s_info.get("command")
                args = s_info.get("args", [])
                env = s_info.get("env")
                if cmd:
                    self.register_server(name, cmd, args, env)
        except Exception:
            pass

    def register_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None
    ) -> MCPClient:
        """Registers a new MCP server."""
        if name in self.servers:
            self.servers[name].disconnect()

        client = MCPClient(name=name, command=command, args=args, env=env)
        self.servers[name] = client
        return client

    def unregister_server(self, name: str):
        """Disconnects and removes an MCP server."""
        if name in self.servers:
            self.servers[name].disconnect()
            del self.servers[name]

    def connect_all(self):
        """Connects to all registered MCP servers and discovers capabilities."""
        for client in self.servers.values():
            try:
                client.connect(timeout=3.0)
            except Exception:
                pass

    def disconnect_all(self):
        """Cleanly disconnects all active MCP servers."""
        for client in self.servers.values():
            client.disconnect()

    def list_servers(self) -> List[Dict[str, Any]]:
        """Returns metadata and health of all registered servers."""
        result = []
        for name, client in self.servers.items():
            result.append({
                "name": name,
                "command": client.command,
                "args": client.args,
                "connected": client.is_alive(),
                "tools_count": len(client.tools),
                "resources_count": len(client.resources)
            })
        return result

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Returns all tools from all servers formatted for LLM function calling."""
        all_tools = []
        for s_name, client in self.servers.items():
            if not client.is_alive():
                client.connect(timeout=2.0)
            for t in client.tools:
                all_tools.append({
                    "name": f"mcp_{s_name}_{t.name}",
                    "server": s_name,
                    "tool": t.name,
                    "description": f"[{s_name}] {t.description}",
                    "input_schema": t.input_schema
                })
        return all_tools

    def call_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
        """Executes a tool on the designated server."""
        client = self.servers.get(server_name)
        if not client:
            return False, f"MCP server '{server_name}' is not registered."

        return client.call_tool(tool_name, arguments)
