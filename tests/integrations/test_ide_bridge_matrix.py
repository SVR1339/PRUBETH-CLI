"""Comprehensive Unit Test Matrix for PRUBETH IDE Bridge IPC Gateway."""

from __future__ import annotations

import json
import socket
import time
from unittest.mock import MagicMock
import pytest

from prubeth.integrations.ide_bridge import IDEBridgeServer


def test_ide_bridge_initialization_defaults():
    """Validates IDEBridgeServer default ports, naming, and initial state."""
    server = IDEBridgeServer(port=29999)
    assert server.port == 29999
    assert server.running is False
    assert server.client_count == 0
    assert server.command_callbacks == []
    assert server.DEFAULT_PORT == 28888
    assert "prubeth_ipc" in server.NAMED_PIPE_NAME


def test_ide_bridge_start_and_stop():
    """Validates lifecycle startup and graceful shutdown."""
    # Find free port
    temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temp_sock.bind(("127.0.0.1", 0))
    free_port = temp_sock.getsockname()[1]
    temp_sock.close()

    server = IDEBridgeServer(port=free_port)
    server.start()
    assert server.running is True
    time.sleep(0.05)

    # Double start is idempotent
    server.start()
    assert server.running is True

    server.stop()
    assert server.running is False
    assert server.client_count == 0


def test_ide_bridge_client_connection_and_event_emission():
    """Validates socket connection, NDJSON streaming framing, and event emission."""
    temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temp_sock.bind(("127.0.0.1", 0))
    free_port = temp_sock.getsockname()[1]
    temp_sock.close()

    server = IDEBridgeServer(port=free_port)
    server.start()
    time.sleep(0.05)

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect(("127.0.0.1", free_port))
    client_sock.settimeout(2.0)
    time.sleep(0.05)

    assert server.client_count == 1

    # Emit event to client
    server.emit_event("step_progress", {"phase": "AST_GATE", "percent": 50})

    raw_data = client_sock.recv(4096).decode("utf-8")
    assert raw_data.endswith("\n")
    event_obj = json.loads(raw_data.strip())
    assert event_obj["protocol"] == "prubeth.ipc/v1"
    assert event_obj["event"] == "step_progress"
    assert event_obj["data"]["phase"] == "AST_GATE"
    assert event_obj["data"]["percent"] == 50
    assert "timestamp" in event_obj

    client_sock.close()
    server.stop()


def test_ide_bridge_incoming_command_callback():
    """Validates that incoming NDJSON messages from IDE frontends invoke registered handlers."""
    temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temp_sock.bind(("127.0.0.1", 0))
    free_port = temp_sock.getsockname()[1]
    temp_sock.close()

    server = IDEBridgeServer(port=free_port)
    received_commands = []
    server.register_command_handler(lambda cmd: received_commands.append(cmd))

    server.start()
    time.sleep(0.05)

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect(("127.0.0.1", free_port))
    time.sleep(0.05)

    # Send command
    cmd_payload = json.dumps({"action": "jump_to_source", "file": "src/main.py", "line": 42}) + "\n"
    client_sock.sendall(cmd_payload.encode("utf-8"))
    time.sleep(0.1)

    assert len(received_commands) == 1
    assert received_commands[0]["action"] == "jump_to_source"
    assert received_commands[0]["line"] == 42

    # Send malformed data does not crash server
    client_sock.sendall(b"NOT_JSON_DATA\n")
    time.sleep(0.05)
    assert server.running is True

    client_sock.close()
    server.stop()


def test_ide_bridge_dead_client_cleanup():
    """Validates that dead or disconnected client sockets are purged on event emit."""
    temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temp_sock.bind(("127.0.0.1", 0))
    free_port = temp_sock.getsockname()[1]
    temp_sock.close()

    server = IDEBridgeServer(port=free_port)
    server.start()
    time.sleep(0.05)

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect(("127.0.0.1", free_port))
    time.sleep(0.05)
    assert server.client_count == 1

    # Forcefully close client socket
    client_sock.close()
    time.sleep(0.05)

    # Server emit attempts to write to dead socket and cleans it up
    server.emit_event("ping", {})
    assert server.client_count == 0

    server.stop()
