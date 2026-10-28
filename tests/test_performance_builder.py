import unittest
import tempfile
import shutil
from pathlib import Path
from prubeth.config.manager import ConfigManager
from prubeth.performance.builder import PerformanceBuilder

class TestPerformanceBuilder(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg_mgr = ConfigManager(config_dir=Path(self.tmpdir))
        self.builder = PerformanceBuilder(self.cfg_mgr)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_probe_environment(self):
        env = self.builder.probe_environment()
        self.assertIn("os", env)
        self.assertIn("python_version", env)
        self.assertIn("cpu_cores", env)
        self.assertGreater(env["cpu_cores"], 0)
        self.assertIn("process_memory_mb", env)
        self.assertGreater(env["process_memory_mb"], 0)
        self.assertIn("disk_io_speed_mb_s", env)
        self.assertGreater(env["disk_io_speed_mb_s"], 0)

    def test_compute_spi_builder_profile(self):
        self.cfg_mgr.apply_profile("builder")
        spi = self.builder.compute_spi()
        self.assertGreaterEqual(spi["composite_spi"], 0)
        self.assertLessEqual(spi["composite_spi"], 100)
        self.assertGreaterEqual(spi["velocity"], 80)
        self.assertGreaterEqual(spi["resilience"], 80)
        self.assertEqual(spi["autonomy_tier"], "Tier 5 (Fully Autonomous Hands-Free)")

    def test_compute_spi_safe_audit_profile(self):
        self.cfg_mgr.apply_profile("safe-audit")
        spi = self.builder.compute_spi()
        self.assertGreaterEqual(spi["composite_spi"], 0)
        self.assertLessEqual(spi["composite_spi"], 100)
        self.assertIn("Tier 3", spi["autonomy_tier"])
        # Restore builder profile
        self.cfg_mgr.apply_profile("builder")

    def test_generate_recommendations(self):
        env = self.builder.probe_environment()
        cfg = self.cfg_mgr.load_config()
        recs = self.builder.generate_recommendations(env, cfg)
        self.assertIsInstance(recs, list)
        self.assertGreater(len(recs), 0)
        for r in recs:
            self.assertIn("badge", r)
            self.assertIn("action", r)
            self.assertIn("command", r)
            self.assertIn("impact", r)

if __name__ == "__main__":
    unittest.main()
