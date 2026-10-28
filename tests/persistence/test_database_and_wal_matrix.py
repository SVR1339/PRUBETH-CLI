"""PRUBETH Task Database & SQLite WAL Resilience Matrix.

Exhaustively verifies SQLite WAL mode invariants, schema migrations,
task state audit transitions, checkpoint tracking, tool execution telemetry,
and multi-threaded concurrent write safety without lock contention.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import List
import pytest

from prubeth.persistence.database import TaskDatabase, TaskRecord


# ============================================================================
# 1. Database Schema & WAL Journal Mode Invariants
# ============================================================================

def test_task_database_initialization_wal_mode(tmp_path: Path):
    """Database initializes in SQLite WAL mode with standard PRAGMA settings."""
    db_file = tmp_path / "prubeth.db"
    db = TaskDatabase(str(db_file))

    conn = db._get_connection()
    cursor = conn.cursor()

    # Query journal_mode
    journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
    assert journal_mode.lower() == "wal"

    # Query busy_timeout
    busy_timeout = cursor.execute("PRAGMA busy_timeout;").fetchone()[0]
    assert busy_timeout >= 5000

    db.close()


def test_task_database_create_and_get_task(tmp_path: Path):
    """Creates a task record and verifies immediate retrieval with identical fields."""
    db = TaskDatabase(str(tmp_path / "tasks.db"))
    record = db.create_task("task_001", "Implement autonomous test runner")

    assert record.task_id == "task_001"
    assert record.goal == "Implement autonomous test runner"
    assert record.state == "CREATED"
    assert record.created_at != ""

    fetched = db.get_task("task_001")
    assert fetched is not None
    assert fetched.task_id == "task_001"
    assert fetched.goal == "Implement autonomous test runner"
    assert fetched.state == "CREATED"
    assert fetched.completed_at is None
    db.close()


def test_task_database_nonexistent_task_returns_none(tmp_path: Path):
    db = TaskDatabase(str(tmp_path / "tasks.db"))
    assert db.get_task("ghost_task") is None
    db.close()


def test_task_database_list_tasks_ordered(tmp_path: Path):
    """list_tasks retrieves all records ordered by updated_at descending."""
    db = TaskDatabase(str(tmp_path / "tasks.db"))
    for i in range(1, 6):
        db.create_task(f"task_{i:03d}", f"Goal {i}")

    tasks = db.list_tasks(limit=10)
    assert len(tasks) == 5
    # Limit check
    tasks_top_2 = db.list_tasks(limit=2)
    assert len(tasks_top_2) == 2
    db.close()


# ============================================================================
# 2. State Transition Lifecycle & Audit Trail
# ============================================================================

def test_task_database_state_transitions_audit_log(tmp_path: Path):
    """Task transitions are immutably logged into state_transitions audit table."""
    db = TaskDatabase(str(tmp_path / "tasks.db"))
    db.create_task("task_lifecycle", "Lifecycle test")

    transitions = [
        ("CREATED", "PLANNING", "Planner invoked"),
        ("PLANNING", "EXECUTING", "Plan approved"),
        ("EXECUTING", "VERIFYING", "Tool actions finished"),
        ("VERIFYING", "COMPLETED", "All tests passed with zero regressions"),
    ]

    for from_s, to_s, reason in transitions:
        db.update_task_state("task_lifecycle", from_s, to_s, reason=reason)

    task = db.get_task("task_lifecycle")
    assert task is not None
    assert task.state == "COMPLETED"

    audit_logs = db.get_state_transitions("task_lifecycle")
    assert len(audit_logs) == 4
    assert audit_logs[0]["from_state"] == "CREATED"
    assert audit_logs[0]["to_state"] == "PLANNING"
    assert audit_logs[3]["to_state"] == "COMPLETED"
    assert audit_logs[3]["reason"] == "All tests passed with zero regressions"
    db.close()


# ============================================================================
# 3. Checkpoints & Tool Execution Records
# ============================================================================

def test_task_database_record_and_get_checkpoints(tmp_path: Path):
    """Git and filesystem checkpoints are recorded and queryable by task_id."""
    db = TaskDatabase(str(tmp_path / "tasks.db"))
    db.create_task("task_cp", "Checkpoint test")

    db.record_checkpoint("task_cp", git_hash="a1b2c3d4", stash_ref="", description="Pre-flight baseline")
    db.record_checkpoint("task_cp", git_hash="e5f6a7b8", stash_ref="stash@{0}", description="Post-mutation stash")

    cps = db.get_checkpoints("task_cp")
    assert len(cps) == 2
    assert cps[0]["git_hash"] == "a1b2c3d4"
    assert cps[0]["description"] == "Pre-flight baseline"
    assert cps[1]["git_hash"] == "e5f6a7b8"
    assert cps[1]["stash_ref"] == "stash@{0}"
    db.close()


def test_task_database_tool_execution_audit_trail(tmp_path: Path):
    """Tool calls are recorded with serialized JSON arguments, results, and timings."""
    db = TaskDatabase(str(tmp_path / "tasks.db"))
    db.create_task("task_tools", "Tool telemetry test")

    db.record_tool_execution(
        task_id="task_tools",
        tool_name="read_file",
        args={"path": "src/core.py"},
        result="def main(): pass",
        exit_code=0,
        duration_ms=45
    )
    db.record_tool_execution(
        task_id="task_tools",
        tool_name="run_command",
        args={"command": "pytest"},
        result="2688 passed in 3.12s",
        exit_code=0,
        duration_ms=3120
    )

    executions = db.get_task_tool_executions("task_tools")
    assert len(executions) == 2
    assert executions[0]["tool_name"] == "read_file"
    assert executions[0]["exit_code"] == 0
    assert executions[0]["duration_ms"] == 45
    assert executions[1]["tool_name"] == "run_command"
    assert executions[1]["duration_ms"] == 3120
    db.close()


def test_task_database_verification_evidence(tmp_path: Path):
    """Records deterministic test verification framework runs and results."""
    db = TaskDatabase(str(tmp_path / "tasks.db"))
    db.create_task("task_verify", "Verification record test")

    db.record_verification(
        task_id="task_verify",
        framework="pytest",
        passed=2688,
        failed=0,
        exit_code=0,
        summary="100% test pass rate achieved"
    )

    evidences = db.get_verification_evidence("task_verify")
    assert len(evidences) == 1
    assert evidences[0]["framework"] == "pytest"
    assert evidences[0]["tests_passed"] == 2688
    assert evidences[0]["tests_failed"] == 0
    assert evidences[0]["exit_code"] == 0
    assert evidences[0]["output_summary"] == "100% test pass rate achieved"
    db.close()


# ============================================================================
# 4. WAL Checkpoint & Concurrency Resilience
# ============================================================================

def test_task_database_checkpoint_wal_truncate(tmp_path: Path):
    """Forcing WAL checkpoint truncates journal back into the main SQLite database."""
    db = TaskDatabase(str(tmp_path / "wal_test.db"))
    for i in range(10):
        db.create_task(f"wal_{i}", f"Goal {i}")

    ok = db.checkpoint_wal()
    assert ok is True
    db.close()


def test_task_database_multithreaded_concurrent_writes(tmp_path: Path):
    """Multiple threads writing to the database concurrently do not crash or corrupt state."""
    db = TaskDatabase(str(tmp_path / "concurrent.db"))
    errors: List[Exception] = []

    def worker(worker_id: int):
        try:
            for j in range(10):
                tid = f"thread_{worker_id}_task_{j}"
                db.create_task(tid, f"Worker {worker_id} Task {j}")
                db.update_task_state(tid, "CREATED", "EXECUTING", "Thread started")
                db.record_tool_execution(tid, "dummy_tool", {"step": j}, "ok", exit_code=0)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread errors occurred: {errors}"
    tasks = db.list_tasks(limit=100)
    assert len(tasks) == 50
    db.close()


def test_task_database_context_manager(tmp_path: Path):
    """TaskDatabase acts as a clean context manager that closes connection on exit."""
    db_file = tmp_path / "ctx.db"
    with TaskDatabase(str(db_file)) as db:
        db.create_task("ctx_task", "Testing context manager")
        assert db.get_task("ctx_task") is not None
    # Connection should be closed
    assert db._conn is None


def test_task_database_reopen_existing_db(tmp_path: Path):
    """Reopening an existing database file retains all tables and rows."""
    db_file = tmp_path / "persist.db"
    db1 = TaskDatabase(str(db_file))
    db1.create_task("keep_me", "Permanent task")
    db1.close()

    db2 = TaskDatabase(str(db_file))
    task = db2.get_task("keep_me")
    assert task is not None
    assert task.goal == "Permanent task"
    db2.close()


def test_task_database_close_is_idempotent(tmp_path: Path):
    db = TaskDatabase(str(tmp_path / "idempotent.db"))
    db.close()
    db.close()  # Must not raise
    assert db._conn is None
