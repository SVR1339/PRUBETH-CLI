import unittest
import io
import sys
from rich.console import Console

from prubeth.cli.doctor import PrubethDoctor
from prubeth.cli.version import get_version_metadata, render_version_info, PRUBETH_VERSION
from prubeth.cli.help import render_tier1_help
from prubeth.cli.completions import (
    generate_powershell_completion,
    generate_bash_completion,
    generate_zsh_completion
)

class TestCliDiagnosticsAndQualification(unittest.TestCase):
    """Tier-1 CLI qualification and diagnostics test suite."""

    def setUp(self):
        self.console = Console(file=io.StringIO(), force_terminal=False)

    def test_version_metadata_integrity(self):
        """Verifies version, license, and zero-telemetry metadata."""
        meta = get_version_metadata()
        self.assertIn(meta["version"], ["1.0.0", "1.1.0", "1.2.0", "1.2.1", "1.3.0", "1.3.1"])
        self.assertIn("Enterprise Commercial Production", meta["release_tier"])
        self.assertEqual(meta["license"], "Apache-2.0")
        self.assertIn("Local-First", meta["zero_telemetry"])
        self.assertIn("33 MB", meta["memory_budget"])

    def test_render_version_info_table_and_json(self):
        """Verifies version rendering in both ANSI table and JSON modes."""
        render_version_info(self.console, as_json=False)
        output = self.console.file.getvalue()
        self.assertTrue(any(v in output for v in ["1.0.0", "1.1.0", "1.2.0", "1.2.1", "1.3.0", "1.3.1"]))
        self.assertIn("Apache-2.0", output)

        # JSON mode
        stdout_orig = sys.stdout
        buf = io.StringIO()
        try:
            sys.stdout = buf
            render_version_info(self.console, as_json=True)
            json_out = buf.getvalue()
            self.assertTrue(any(f'"version": "{v}"' in json_out for v in ["1.0.0", "1.1.0", "1.2.0", "1.2.1", "1.3.0", "1.3.1"]))
            self.assertIn('"zero_telemetry": "Verified (100% Local-First)"', json_out)
        finally:
            sys.stdout = stdout_orig

    def test_render_tier1_help(self):
        """Verifies structured tier-1 CLI help output."""
        render_tier1_help(self.console)
        output = self.console.file.getvalue()
        self.assertIn("PRUBETH Autonomous Developer CLI", output)
        self.assertIn("CORE CLI OPTIONS", output)
        self.assertIn("OPERATIONAL COMMANDS & WORKFLOWS", output)
        self.assertIn("doctor", output)
        self.assertIn("onboarding", output)
        self.assertIn("swarm", output)

    def test_doctor_diagnostics_suite(self):
        """Verifies that doctor checks run and produce accepted qualification results."""
        doctor = PrubethDoctor(self.console)
        all_ok, results = doctor.diagnose_all()
        self.assertEqual(len(results), 9)
        
        # Verify critical invariant pillars are passing
        pillar_map = {r["pillar"]: r["status"] for r in results}
        self.assertIn("1. Python Runtime & Environment", pillar_map)
        self.assertIn("2. Terminal Subsystem (PRINCE3)", pillar_map)
        self.assertIn("6. DevSecOps Sandbox & Path Jail", pillar_map)
        self.assertIn("7. Persistence & Snapshot Tree", pillar_map)
        self.assertIn("9. Cryptographic Runtime Integrity", pillar_map)
        
        self.assertEqual(pillar_map["6. DevSecOps Sandbox & Path Jail"], "PASS")
        self.assertEqual(pillar_map["7. Persistence & Snapshot Tree"], "PASS")
        self.assertEqual(pillar_map["9. Cryptographic Runtime Integrity"], "PASS")

    def test_shell_completions_generation(self):
        """Verifies syntax and keyword inclusion in shell completions."""
        ps_comp = generate_powershell_completion()
        self.assertIn("Register-ArgumentCompleter", ps_comp)
        self.assertIn("doctor", ps_comp)
        self.assertIn("onboarding", ps_comp)
        self.assertIn("version", ps_comp)
        self.assertIn("therapy", ps_comp)
        self.assertIn("heal", ps_comp)

        bash_comp = generate_bash_completion()
        self.assertIn("_prubeth_completions()", bash_comp)
        self.assertIn("therapy", bash_comp)
        self.assertIn("complete -F _prubeth_completions prubeth", bash_comp)

        zsh_comp = generate_zsh_completion()
        self.assertIn("#compdef prubeth", zsh_comp)
        self.assertIn("_prubeth", zsh_comp)

if __name__ == "__main__":
    unittest.main()
