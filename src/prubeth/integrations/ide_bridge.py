"""PRUBETH IDE Integration Bridge & IPC Event Streamer.

Provides Inter-Process Communication (IPC) via Windows Named Pipe / Socket server,
streaming live execution trees, diff badges, and telemetry to the PRUBETH IDE.
"""

import sys
import os
import json
import time
import socket
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

class IDEBridgeServer:
    """Subsystem 15: Real-time IPC Gateway for PRUBETH IDE GUI Integration."""

    DEFAULT_PORT = 28888
    NAMED_PIPE_NAME = r"\\.\pipe\prubeth_ipc"

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.running = False
        self.server_thread: Optional[threading.Thread] = None
        self.clients: List[socket.socket] = []
        self.clients_lock = threading.Lock()
        self.command_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._server_socket: Optional[socket.socket] = None
        self._ready_event = threading.Event()

    def start(self):
        """Starts the background IPC listener thread."""
        if self.running:
            return
        self.running = True
        self._ready_event.clear()
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self._ready_event.wait(timeout=5.0)

    def stop(self):
        """Stops the IPC server and disconnects active clients."""
        self.running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        with self.clients_lock:
            for c in self.clients:
                try:
                    c.close()
                except Exception:
                    pass
            self.clients.clear()

    def register_command_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Registers a callback for incoming IDE commands."""
        self.command_callbacks.append(handler)

    def _run_server(self):
        """Background listener accepting IDE client socket connections."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(("127.0.0.1", self.port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)
            self._ready_event.set()
        except Exception:
            self.running = False
            self._ready_event.set()
            return

        while self.running:
            try:
                client_sock, _ = self._server_socket.accept()
                with self.clients_lock:
                    self.clients.append(client_sock)
                # Spawn worker thread for incoming IDE commands
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle_client(self, client_sock: socket.socket):
        """Receives incoming messages from an attached PRUBETH IDE client."""
        client_sock.settimeout(1.0)
        buffer = ""
        while self.running:
            try:
                data = client_sock.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            msg = json.loads(line)
                            for cb in self.command_callbacks:
                                cb(msg)
                        except json.JSONDecodeError:
                            pass
            except socket.timeout:
                continue
            except Exception:
                break

        with self.clients_lock:
            if client_sock in self.clients:
                self.clients.remove(client_sock)
        try:
            client_sock.close()
        except Exception:
            pass

    def emit_event(self, event_type: str, payload: Any):
        """Streams a strongly-typed NDJSON event to all connected IDE surfaces."""
        msg = {
            "protocol": "prubeth.ipc/v1",
            "event": event_type,
            "timestamp": time.time(),
            "data": payload
        }
        raw = json.dumps(msg, default=str) + "\n"
        encoded = raw.encode("utf-8")

        with self.clients_lock:
            dead_clients = []
            for client in self.clients:
                try:
                    client.sendall(encoded)
                except Exception:
                    dead_clients.append(client)
            for dc in dead_clients:
                self.clients.remove(dc)

    @property
    def client_count(self) -> int:
        """Returns number of actively connected IDE frontends."""
        with self.clients_lock:
            return len(self.clients)
