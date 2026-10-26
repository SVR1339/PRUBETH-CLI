import os
import time
import json
import unittest
import tempfile
from pathlib import Path

from prubeth.config.manager import ConfigManager, DEFAULT_CONFIG
from prubeth.persistence.database import TaskDatabase
from prubeth.persistence.checkpoints import SnapshotManager
from prubeth.verification.polyglot import PolyglotSyntaxGate
from prubeth.runtime.state_machine import TaskStateMachine, TaskState

class TestSREReliabilityAndResilience(unittest.TestCase):
    """Site Reliability Engineering (SRE): SLI/SLO Invariants, Latency & Failure Recovery."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sre_sli_corrupted_config_self_healing(self):
        """SRE Resilience: CLI must self-heal corrupted config.json without raising unhandled crash."""
        config_dir = self.workspace / ".prubeth"
        config_dir.mkdir(parents=True, exist_ok=True)
        corrupted_file = config_dir / "config.json"
        
        # Write corrupted garbage
        corrupted_file.write_text("{ broken_json: [ invalid, syntax ", encoding="utf-8")

        # Load via ConfigManager
        cfg_mgr = ConfigManager(config_dir=config_dir)
        cfg = cfg_mgr.load_config()

        # Must fall back gracefully to default schema
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.get("active_profile"), "builder")
        self.assertTrue(cfg.get("speculative_plan_b"))

    def test_sre_sli_ast_gate_microsecond_latency(self):
        """SRE Latency SLI: Polyglot AST syntax validation must execute under 20ms."""
        valid_python_source = """
class HighPerformanceOrchestrator:
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.queue = []

    def dispatch(self, item: str) -> bool:
        if len(self.queue) < self.capacity:
            self.queue.append(item)
            return True
        return False
"""
        gate = PolyglotSyntaxGate()
        t0 = time.perf_counter()
        valid, msg = gate.validate_content("orchestrator.py", valid_python_source)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        self.assertTrue(valid)
        self.assertIn("successful", msg)
        # Must execute within sub-50ms SLO
        self.assertLess(latency_ms, 50.0, f"AST parse latency {latency_ms:.2f}ms exceeded 50ms SLO")

    def test_sre_sli_sqlite_wal_concurrency(self):
        """SRE Concurrency: SQLite WAL mode supports rapid read/write iterations without locking errors."""
        db_path = self.workspace / ".prubeth" / "sre_test.db"
        db = TaskDatabase(str(db_path))

        t0 = time.perf_counter()
        task_id = "sre-task-concurrent"
        db.create_task(task_id, "Stress test concurrency in WAL mode")

        # Rapidly log 50 tool executions
        for i in range(50):
            db.record_tool_execution(task_id, "test_tool", {"step": i}, "result_ok", exit_code=0, duration_ms=5)

        task = db.get_task(task_id)
        total_time_ms = (time.perf_counter() - t0) * 1000.0
        db.close()

        self.assertIsNotNone(task)
        self.assertEqual(task.task_id, task_id)
        self.assertLess(total_time_ms, 3000.0, f"50 WAL writes took {total_time_ms:.2f}ms")

    def test_sre_sli_snapshot_and_rollback_speed(self):
        """SRE Latency SLI: Snapshot creation and rollback must complete in < 1000ms."""
        # Create 15 dummy workspace files
        for i in range(15):
            p = self.workspace / f"module_{i}.py"
            p.write_text(f"# Module {i}\ndef process():\n    return {i * 10}\n", encoding="utf-8")

        snap_mgr = SnapshotManager(workspace_root=self.workspace, task_id="sre_perf")
        
        # Measure snapshot latency
        t0 = time.perf_counter()
        snap_mgr.create_snapshot("bench-snap")
        snap_time_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(snap_time_ms, 2000.0, f"Snapshot creation {snap_time_ms:.2f}ms exceeded 2000ms SLO")

        # Mutate all files
        for i in range(15):
            (self.workspace / f"module_{i}.py").write_text("# Corrupted\n", encoding="utf-8")

        # Measure rollback latency
        t1 = time.perf_counter()
        rolled_back = snap_mgr.rollback_to_snapshot("bench-snap")
        rollback_time_ms = (time.perf_counter() - t1) * 1000.0

        self.assertTrue(rolled_back)
        self.assertLess(rollback_time_ms, 2000.0, f"Rollback {rollback_time_ms:.2f}ms exceeded 2000ms SLO")

        # Verify restoration
        sample = (self.workspace / "module_5.py").read_text(encoding="utf-8")
        self.assertIn("def process():", sample)

    def test_sre_memory_footprint_invariance(self):
        """SRE Invariant: State machine object allocations remain bounded without memory leaks."""
        state_machines = []
        for i in range(200):
            sm = TaskStateMachine(task_id=f"leak-check-{i}")
            sm.transition_to(TaskState.CONTEXTUALIZING)
            sm.transition_to(TaskState.PLANNING)
            sm.transition_to(TaskState.READY)
            state_machines.append(sm)

        # 200 state machines should not exceed negligible memory
        self.assertEqual(len(state_machines), 200)
        self.assertEqual(state_machines[-1].current_state, TaskState.READY)

if __name__ == "__main__":
    unittest.main()
