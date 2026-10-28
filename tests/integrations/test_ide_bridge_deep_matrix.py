"""PRUBETH IDE Bridge IPC Gateway & Socket Protocol Matrix.

Exhaustively verifies IPC socket connectivity, NDJSON event emission,
client lifecycle management, dead client purging, and IDE command dispatch.
"""

from __future__ import annotations

import json
import socket
import time
from pathlib import Path
import pytest

from prubeth.integrations.ide_bridge import IDEBridgeServer


# ============================================================================
# 1. Server Lifecycle & Port Invariants
# ============================================================================

def test_ide_bridge_server_initial_state():
    """Server initializes stopped with 0 clients and default configuration."""
    server = IDEBridgeServer(port=29990)
    assert server.port == 29990
    assert server.running is False
    assert server.client_count == 0
    assert len(server.command_callbacks) == 0


def test_ide_bridge_server_start_and_stop():
    """Server starts background socket listener thread and closes cleanly on stop."""
    server = IDEBridgeServer(port=29991)
    server.start()
    assert server.running is True
    assert server.server_thread is not None
    assert server.server_thread.is_alive()

    # Re-calling start when running is a no-op
    server.start()
    assert server.running is True

    server.stop()
    assert server.running is False
    time.sleep(0.1)


# ============================================================================
# 2. Client Connectivity & NDJSON Event Streaming
# ============================================================================

def test_ide_bridge_client_connection_and_event_broadcast():
    """Connected client socket receives formatted NDJSON stream events."""
    port = 29992
    server = IDEBridgeServer(port=port)
    server.start()
    time.sleep(0.1)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("127.0.0.1", port))
        time.sleep(0.1)
        assert server.client_count == 1

        # Emit typed event
        server.emit_event("task_progress", {"task_id": "t1", "pct": 75})

        client.settimeout(2.0)
        data = client.recv(4096).decode("utf-8")
        assert "prubeth.ipc/v1" in data
        assert "task_progress" in data
        assert "75" in data

        parsed = json.loads(data.strip())
        assert parsed["protocol"] == "prubeth.ipc/v1"
        assert parsed["event"] == "task_progress"
        assert parsed["data"]["task_id"] == "t1"
    finally:
        client.close()
        server.stop()


def test_ide_bridge_dead_client_purging():
    """Server automatically unregisters dropped client connections during next broadcast."""
    port = 29993
    server = IDEBridgeServer(port=port)
    server.start()
    time.sleep(0.1)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("127.0.0.1", port))
        time.sleep(0.1)
        assert server.client_count == 1

        # Force abrupt close on client side
        client.close()
        time.sleep(0.1)

        # Broadcast should detect broken pipe and purge
        server.emit_event("heartbeat", {"alive": True})
        assert server.client_count == 0
    finally:
        server.stop()


def test_ide_bridge_command_callback_dispatch():
    """Incoming messages from IDE frontend trigger registered command handlers."""
    port = 29994
    server = IDEBridgeServer(port=port)
    received_commands = []

    def handle_command(msg: dict):
        received_commands.append(msg)

    server.register_command_handler(handle_command)
    server.start()
    time.sleep(0.1)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("127.0.0.1", port))
        time.sleep(0.1)

        # Send command JSON with newline delimiter
        payload = json.dumps({"action": "pause_task", "task_id": "task_abc"}) + "\n"
        client.sendall(payload.encode("utf-8"))
        time.sleep(0.2)

        assert len(received_commands) == 1
        assert received_commands[0]["action"] == "pause_task"
        assert received_commands[0]["task_id"] == "task_abc"
    finally:
        client.close()
        server.stop()
