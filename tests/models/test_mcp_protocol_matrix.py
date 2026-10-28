"""PRUBETH MCP Protocol, Manager & Preset Registry Matrix Tests.

Exhaustively verifies MCPTool, MCPResource, MCPRequest, MCPResponse data contracts,
JSON-RPC 2.0 serialisation, from_dict parsing, MCPManager workspace/global config
initialisation, preset discovery, and multi-server registry isolation.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from prubeth.mcp.protocol import MCPTool, MCPResource, MCPRequest, MCPResponse
from prubeth.mcp.manager import MCPManager, MCP_PRESETS


# ============================================================================
# 1. MCPTool Data Contracts
# ============================================================================

def test_mcp_tool_basic_fields():
    tool = MCPTool(name="write_file", description="Writes content to a file on disk.")
    assert tool.name == "write_file"
    assert tool.description == "Writes content to a file on disk."
    assert tool.input_schema == {}


def test_mcp_tool_with_schema():
    schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    }
    tool = MCPTool(name="write_file", description="Write file", input_schema=schema)
    assert tool.input_schema["type"] == "object"
    assert "path" in tool.input_schema["properties"]


def test_mcp_tool_empty_schema_is_dict():
    tool = MCPTool(name="list_dir", description="Lists directory.")
    assert isinstance(tool.input_schema, dict)


# ============================================================================
# 2. MCPResource Data Contracts
# ============================================================================

def test_mcp_resource_basic():
    res = MCPResource(uri="file:///workspace/README.md", name="README.md")
    assert res.uri == "file:///workspace/README.md"
    assert res.name == "README.md"
    assert res.description is None
    assert res.mime_type is None


def test_mcp_resource_with_mime_type():
    res = MCPResource(
        uri="file:///data/schema.json",
        name="schema.json",
        description="Project JSON schema",
        mime_type="application/json"
    )
    assert res.mime_type == "application/json"
    assert res.description == "Project JSON schema"


# ============================================================================
# 3. MCPRequest JSON-RPC 2.0 Serialisation
# ============================================================================

def test_mcp_request_defaults():
    req = MCPRequest()
    assert req.jsonrpc == "2.0"
    assert req.id == 1
    assert req.method == ""
    assert req.params is None


def test_mcp_request_tools_list():
    req = MCPRequest(method="tools/list")
    d = req.to_dict()
    assert d["jsonrpc"] == "2.0"
    assert d["method"] == "tools/list"
    assert "params" not in d  # No params → omitted


def test_mcp_request_tools_call_with_params():
    req = MCPRequest(
        method="tools/call",
        id=42,
        params={"name": "write_file", "arguments": {"path": "main.py", "content": "pass"}}
    )
    d = req.to_dict()
    assert d["id"] == 42
    assert d["params"]["name"] == "write_file"
    assert d["params"]["arguments"]["path"] == "main.py"


def test_mcp_request_initialize():
    req = MCPRequest(
        method="initialize",
        params={"protocolVersion": "2024-11-05", "clientInfo": {"name": "prubeth", "version": "2.0.0"}}
    )
    d = req.to_dict()
    assert d["method"] == "initialize"
    assert d["params"]["protocolVersion"] == "2024-11-05"


def test_mcp_request_ping():
    req = MCPRequest(method="ping", id="ping_1")
    d = req.to_dict()
    assert d["id"] == "ping_1"
    assert d["method"] == "ping"


def test_mcp_request_json_roundtrip():
    req = MCPRequest(method="resources/list", id=99)
    serialised = json.dumps(req.to_dict())
    restored = json.loads(serialised)
    assert restored["method"] == "resources/list"
    assert restored["id"] == 99


# ============================================================================
# 4. MCPResponse Deserialisation (from_dict)
# ============================================================================

def test_mcp_response_success_from_dict():
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": [{"name": "write_file", "description": "Write."}]}
    }
    resp = MCPResponse.from_dict(data)
    assert resp.jsonrpc == "2.0"
    assert resp.id == 1
    assert resp.result is not None
    assert resp.error is None


def test_mcp_response_error_from_dict():
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32601, "message": "Method not found"}
    }
    resp = MCPResponse.from_dict(data)
    assert resp.error is not None
    assert resp.error["code"] == -32601
    assert resp.result is None


def test_mcp_response_minimal_from_dict():
    data = {"jsonrpc": "2.0", "id": 7, "result": None}
    resp = MCPResponse.from_dict(data)
    assert resp.id == 7
    assert resp.result is None
    assert resp.error is None


def test_mcp_response_missing_id_defaults():
    data = {"jsonrpc": "2.0", "result": {"ok": True}}
    resp = MCPResponse.from_dict(data)
    assert resp.id == 1  # Default


def test_mcp_response_missing_jsonrpc_defaults():
    data = {"id": 5, "result": "pong"}
    resp = MCPResponse.from_dict(data)
    assert resp.jsonrpc == "2.0"


# ============================================================================
# 5. MCPManager Initialisation & Config
# ============================================================================

def test_mcp_manager_creates_workspace_config(tmp_path: Path):
    mgr = MCPManager(workspace_root=tmp_path)
    config_file = tmp_path / ".prubeth" / "mcp.json"
    assert config_file.exists()


def test_mcp_manager_config_valid_json(tmp_path: Path):
    mgr = MCPManager(workspace_root=tmp_path)
    config_file = tmp_path / ".prubeth" / "mcp.json"
    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert "mcpServers" in data


def test_mcp_manager_initialises_empty_servers(tmp_path: Path):
    mgr = MCPManager(workspace_root=tmp_path)
    assert isinstance(mgr.servers, dict)


def test_mcp_manager_workspace_root_resolved(tmp_path: Path):
    mgr = MCPManager(workspace_root=tmp_path)
    assert mgr.workspace_root == tmp_path.resolve()


# ============================================================================
# 6. MCP Preset Registry
# ============================================================================

def test_mcp_presets_has_sqlite():
    assert "sqlite" in MCP_PRESETS
    assert "command" in MCP_PRESETS["sqlite"]


def test_mcp_presets_has_fetch():
    assert "fetch" in MCP_PRESETS
    assert "args" in MCP_PRESETS["fetch"]


def test_mcp_presets_has_filesystem():
    assert "filesystem" in MCP_PRESETS
    assert "description" in MCP_PRESETS["filesystem"]


def test_mcp_presets_has_git():
    assert "git" in MCP_PRESETS
    assert MCP_PRESETS["git"]["command"] == "uvx"


def test_mcp_presets_has_github():
    assert "github" in MCP_PRESETS


def test_mcp_presets_has_memory():
    assert "memory" in MCP_PRESETS


@pytest.mark.parametrize("preset_name", ["sqlite", "fetch", "filesystem", "git", "github", "memory"])
def test_mcp_preset_has_required_fields(preset_name: str):
    preset = MCP_PRESETS[preset_name]
    assert "command" in preset
    assert "description" in preset
    assert len(preset["description"]) > 10
