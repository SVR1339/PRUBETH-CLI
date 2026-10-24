import unittest
import io
import os
import sqlite3
import tempfile
from pathlib import Path
from rich.console import Console

from prubeth.config.manager import ConfigManager, DEFAULT_CONFIG
from prubeth.cli.therapy import SystemTherapist

class TestSystemTherapy(unittest.TestCase):
    """Test suite for the PRUBETH Deep Configuration & System Therapy Engine."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name) / ".prubeth"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cfg_mgr = ConfigManager(self.config_dir)
        self.console = Console(file=io.StringIO(), force_terminal=False)
        self.therapist = SystemTherapist(self.console, self.cfg_mgr)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_complete_therapy_returns_seven_pillars(self):
        """Verifies that therapy covers all 7 critical system pillars."""
        report = self.therapist.run_complete_therapy()
        self.assertIn("pillars", report)
        self.assertEqual(len(report["pillars"]), 7)
        self.assertEqual(report["overall_status"], "HEALTHY & OPTIMIZED")

        pillar_names = [p["pillar"] for p in report["pillars"]]
        self.assertIn("1. Terminal Subsystem (PRINCE3)", pillar_names)
        self.assertIn("2. Configuration Drift & Schema", pillar_names)
        self.assertIn("3. Memory Budget & Garbage Collection", pillar_names)
        self.assertIn("4. Cognitive Cascade & Local Sync", pillar_names)
        self.assertIn("5. SQLite WAL Persistence Maintenance", pillar_names)
        self.assertIn("6. DevSecOps Sandbox & Jail", pillar_names)
        self.assertIn("7. Speculative Plan B & Resilience", pillar_names)

    def test_config_drift_auto_remediation(self):
        """Tests that corrupted or missing configuration keys are auto-healed."""
        cfg = self.cfg_mgr.load_config()
        # Deliberately delete keys and introduce a corrupted type
        if "cloud_timeout_s" in cfg:
            del cfg["cloud_timeout_s"]
        cfg["watchdog_timeout_s"] = "invalid_int_string"
        cfg["speculative_plan_b"] = False  # Should be re-armed
        self.cfg_mgr.save_config(cfg)

        # Run therapy
        report = self.therapist.run_complete_therapy()
        
        # Verify keys were restored and repaired
        repaired_cfg = self.cfg_mgr.load_config()
        self.assertIn("cloud_timeout_s", repaired_cfg)
        self.assertEqual(repaired_cfg["cloud_timeout_s"], DEFAULT_CONFIG["cloud_timeout_s"])
        self.assertEqual(repaired_cfg["speculative_plan_b"], True)

    def test_sqlite_wal_maintenance_therapy(self):
        """Tests that SQLite database integrity check and WAL checkpoint truncate execute."""
        db_path = Path.cwd() / ".prubeth" / "prubeth.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE IF NOT EXISTS therapy_test (id INTEGER PRIMARY KEY, msg TEXT);")
        conn.execute("INSERT INTO therapy_test (msg) VALUES ('therapy_ok');")
        conn.commit()
        conn.close()

        report = self.therapist.run_complete_therapy()
        pillar_5 = [p for p in report["pillars"] if "Persistence" in p["pillar"]][0]
        self.assertEqual(pillar_5["status"], "OPTIMAL")
        self.assertIn("integrity", pillar_5["detail"].lower())

    def test_render_therapy_report_display(self):
        """Verifies visual formatting of the therapy report."""
        self.therapist.render_therapy_report()
        output = self.console.file.getvalue()
        self.assertIn("System Therapy", output)
        self.assertIn("Scorecard", output)
        self.assertIn("100% PERFECT", output)

if __name__ == "__main__":
    unittest.main()
