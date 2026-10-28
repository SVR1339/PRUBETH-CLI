"""PRUBETH MCP Multi-Server Registry & Tool Discovery Coordinator.

Subsystem 16: Discovers, manages, and executes tools from external MCP servers.
Integrates directly with PRUBETH's ToolExecutionEngine and SecurityEngine.
Supports both workspace-scoped (.prubeth/mcp.json) and global (~/.prubeth/mcp.json) servers,
plus official one-click presets for SQLite, Filesystem, GitHub, Git, Fetch, and Memory.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from prubeth.mcp.client import MCPClient
from prubeth.mcp.protocol import MCPTool, MCPResource

DEFAULT_MCP_CONFIG = {
    "mcpServers": {}
}

MCP_PRESETS: Dict[str, Dict[str, Any]] = {
    "sqlite": {
        "command": "uvx",
        "args": ["mcp-server-sqlite", "--db-path", "./app.db"],
        "description": "Local SQLite database querying, schema analysis, and table inspection."
    },
    "fetch": {
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "description": "High-fidelity web content fetcher and markdown extractor."
    },
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "description": "Granular filesystem operations with strict path sandboxing."
    },
    "git": {
        "command": "uvx",
        "args": ["mcp-server-git"],
        "description": "Git repository inspection, log traversal, commit creation, and branch diffing."
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "description": "GitHub API integrations: search issues, read pull requests, inspect commits."
    },
    "memory": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Persistent knowledge-graph associative memory across agent sessions."
    }
}

class MCPManager:
    """Manages active MCP servers and exposes tools to the runtime controller."""

    def __init__(self, workspace_root: Optional[Path] = None, config_path: Optional[Path] = None):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.workspace_config_path = config_path or (self.workspace_root / ".prubeth" / "mcp.json")
        self.global_config_path = Path.home() / ".prubeth" / "mcp.json"
        self.config_path = self.workspace_config_path
        self.servers: Dict[str, MCPClient] = {}
        self.server_origins: Dict[str, str] = {}  # "workspace" or "global"
        
        self._ensure_config()
        self._load_servers_from_config()

    def _ensure_config(self):
        """Initialises empty mcp.json if it doesn't exist."""
        if not self.workspace_config_path.exists():
            try:
                self.workspace_config_path.parent.mkdir(parents=True, exist_ok=True)
                self.workspace_config_path.write_text(json.dumps(DEFAULT_MCP_CONFIG, indent=2), encoding="utf-8")
            except Exception:
                pass

    def _load_servers_from_config(self):
        """Loads MCP servers defined in both global and workspace configurations."""
        # 1. Load global servers (~/.prubeth/mcp.json)
        if self.global_config_path.exists():
            try:
                g_cfg = json.loads(self.global_config_path.read_text(encoding="utf-8"))
                for name, s_info in g_cfg.get("mcpServers", {}).items():
                    cmd = s_info.get("command")
                    args = s_info.get("args", [])
                    env = s_info.get("env")
                    if cmd:
                        self.register_server(name, cmd, args, env)
                        self.server_origins[name] = "global"
            except Exception:
                pass

        # 2. Load workspace servers (.prubeth/mcp.json) - overrides global if identical name
        if self.workspace_config_path.exists():
            try:
                w_cfg = json.loads(self.workspace_config_path.read_text(encoding="utf-8"))
                for name, s_info in w_cfg.get("mcpServers", {}).items():
                    cmd = s_info.get("command")
                    args = s_info.get("args", [])
                    env = s_info.get("env")
                    if cmd:
                        self.register_server(name, cmd, args, env)
                        self.server_origins[name] = "workspace"
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
        if name not in self.server_origins:
            self.server_origins[name] = "workspace"
        return client

    def unregister_server(self, name: str):
        """Disconnects and removes an MCP server from active registry."""
        if name in self.servers:
            self.servers[name].disconnect()
            del self.servers[name]
        if name in self.server_origins:
            del self.server_origins[name]

    def save_server_config(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        is_global: bool = False
    ) -> Path:
        """Persists server registration to JSON configuration file."""
        target_path = self.global_config_path if is_global else self.workspace_config_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        cfg_data = {"mcpServers": {}}
        if target_path.exists():
            try:
                cfg_data = json.loads(target_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        if "mcpServers" not in cfg_data:
            cfg_data["mcpServers"] = {}

        payload: Dict[str, Any] = {"command": command, "args": args or []}
        if env:
            payload["env"] = env
        cfg_data["mcpServers"][name] = payload
        target_path.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
        
        self.register_server(name, command, args, env)
        self.server_origins[name] = "global" if is_global else "workspace"
        return target_path

    def remove_server_config(self, name: str, is_global: bool = False) -> bool:
        """Removes server registration from designated configuration file."""
        target_path = self.global_config_path if is_global else self.workspace_config_path
        if not target_path.exists():
            return False

        try:
            cfg_data = json.loads(target_path.read_text(encoding="utf-8"))
            if "mcpServers" in cfg_data and name in cfg_data["mcpServers"]:
                del cfg_data["mcpServers"][name]
                target_path.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
                self.unregister_server(name)
                return True
        except Exception:
            pass
        return False

    def install_preset(self, preset_key: str, is_global: bool = False, custom_name: Optional[str] = None) -> Tuple[bool, str]:
        """Installs a popular official MCP preset."""
        preset = MCP_PRESETS.get(preset_key.lower().strip())
        if not preset:
            avail = ", ".join(MCP_PRESETS.keys())
            return False, f"Unknown preset '{preset_key}'. Available presets: {avail}"

        name = custom_name or preset_key
        path = self.save_server_config(
            name=name,
            command=preset["command"],
            args=preset["args"],
            is_global=is_global
        )
        scope = "Global" if is_global else "Workspace"
        return True, f"Installed MCP preset '{preset_key}' as '{name}' in {scope} configuration ({path})."

    def test_server(self, name: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Performs live ping, handshake, and tool discovery benchmark on a specific server."""
        client = self.servers.get(name)
        if not client:
            return {"success": False, "error": f"MCP server '{name}' is not registered."}

        t0 = time.time()
        connected = client.connect(timeout=timeout)
        dur = round(time.time() - t0, 3)

        if not connected:
            return {
                "success": False,
                "server": name,
                "latency_s": dur,
                "error": "Handshake failed or process terminated prematurely."
            }

        tools = [
            {"name": t.name, "description": t.description}
            for t in client.tools
        ]
        resources = [
            {"name": r.name, "uri": r.uri}
            for r in client.resources
        ]

        return {
            "success": True,
            "server": name,
            "latency_s": dur,
            "connected": True,
            "tools": tools,
            "resources": resources,
            "tool_count": len(tools),
            "resource_count": len(resources)
        }

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
                "resources_count": len(client.resources),
                "scope": self.server_origins.get(name, "workspace")
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
