import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class TaskRecord:
    task_id: str
    goal: str
    state: str
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

class TaskDatabase:
    """Production SQLite Task & Checkpoint Store for PRUBETH."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            dot_dir = Path.cwd() / ".prubeth"
            dot_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = dot_dir / "prubeth.db"

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        return conn

    def _init_schema(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 1. Tasks Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT
            )
            """)

            # 2. State Transition Audit Log
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                reason TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            )
            """)

            # 3. Git Checkpoints
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                git_hash TEXT,
                stash_ref TEXT,
                description TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            )
            """)

            # 4. Tool Execution Audit Log
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                args_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                exit_code INTEGER,
                duration_ms INTEGER,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            )
            """)

            # 5. Deterministic Verification Evidence
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                framework TEXT NOT NULL,
                tests_passed INTEGER NOT NULL,
                tests_failed INTEGER NOT NULL,
                exit_code INTEGER NOT NULL,
                output_summary TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            )
            """)
            conn.commit()
        finally:
            conn.close()

    def create_task(self, task_id: str, goal: str) -> TaskRecord:
        now = datetime.now().isoformat()
        conn = self._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO tasks (task_id, goal, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, goal, "CREATED", now, now)
            )
            conn.commit()
        finally:
            conn.close()
        return TaskRecord(task_id, goal, "CREATED", now, now)

    def update_task_state(self, task_id: str, from_state: str, to_state: str, reason: str = ""):
        now = datetime.now().isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tasks SET state = ?, updated_at = ? WHERE task_id = ?",
                (to_state, now, task_id)
            )
            cursor.execute(
                "INSERT INTO state_transitions (task_id, from_state, to_state, timestamp, reason) VALUES (?, ?, ?, ?, ?)",
                (task_id, from_state, to_state, now, reason)
            )
            conn.commit()
        finally:
            conn.close()

    def record_checkpoint(self, task_id: str, git_hash: str, stash_ref: str, description: str):
        now = datetime.now().isoformat()
        conn = self._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO checkpoints (task_id, git_hash, stash_ref, description, timestamp) VALUES (?, ?, ?, ?, ?)",
                (task_id, git_hash, stash_ref, description, now)
            )
            conn.commit()
        finally:
            conn.close()

    def record_tool_execution(self, task_id: str, tool_name: str, args: Dict[str, Any], result: str, exit_code: int = 0, duration_ms: int = 0):
        now = datetime.now().isoformat()
        conn = self._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO tool_executions (task_id, tool_name, args_json, result_json, exit_code, duration_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, tool_name, json.dumps(args), json.dumps(result), exit_code, duration_ms, now)
            )
            conn.commit()
        finally:
            conn.close()

    def record_verification(self, task_id: str, framework: str, passed: int, failed: int, exit_code: int, summary: str):
        now = datetime.now().isoformat()
        conn = self._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO verification_evidence (task_id, framework, tests_passed, tests_failed, exit_code, output_summary, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, framework, passed, failed, exit_code, summary, now)
            )
            conn.commit()
        finally:
            conn.close()

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        conn = self._get_connection()
        try:
            row = conn.cursor().execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row:
                return TaskRecord(
                    task_id=row["task_id"],
                    goal=row["goal"],
                    state=row["state"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    completed_at=row["completed_at"],
                    error_message=row["error_message"]
                )
        finally:
            conn.close()
        return None
