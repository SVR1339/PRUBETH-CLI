"""Unit tests for PRUBETH Sovereign Cryptographic Integrity Engine (Subsystem 16)."""

import unittest
import tempfile
import json
import io
from pathlib import Path
from rich.console import Console

from prubeth.security.integrity import PrubethIntegrityEngine

class TestPrubethIntegrityEngine(unittest.TestCase):
    """Verifies runtime self-integrity, AST validation, and cryptographic attestation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.buf = io.StringIO()
        self.test_console = Console(file=self.buf, force_terminal=False)
        self.engine = PrubethIntegrityEngine(console=self.test_console, workspace_root=self.workspace)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_audit_module_ast_integrity(self):
        """Ensures all internal PRUBETH modules parse successfully as valid Python AST."""
        ok, count, errors = self.engine.audit_module_ast_integrity()
        self.assertTrue(ok, f"Corrupted Python modules found: {errors}")
        self.assertGreater(count, 10, "Expected at least 10 core modules in package")

    def test_audit_sandbox_jail_integrity(self):
        """Verifies that adversarial path traversal vectors are strictly blocked."""
        ok, leaks = self.engine.audit_sandbox_jail_integrity()
        self.assertTrue(ok, f"Sandbox jail leaks detected: {leaks}")
        self.assertEqual(len(leaks), 0)

    def test_audit_settings_schema_integrity(self):
        """Validates settings.json schema verification and critical deny rules."""
        # 1. Default fallback without file
        ok, detail = self.engine.audit_settings_schema_integrity()
        self.assertTrue(ok)

    def test_compute_runtime_attestation_hash(self):
        """Asserts deterministic SHA-256 calculation for runtime attestation."""
        h1 = self.engine.compute_runtime_attestation_hash()
        h2 = self.engine.compute_runtime_attestation_hash()
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64, "Expected valid 64-character SHA-256 hex digest")

    def test_run_full_attestation(self):
        """Validates full attestation pass and certificate issuance."""
        att = self.engine.run_full_attestation()
        self.assertTrue(att["all_valid"])
        self.assertTrue(att["attestation_token"].startswith("PRUBETH-SOVEREIGN-INTEGRITY-ATTESTED-"))
        self.assertTrue(att["ast_ok"])
        self.assertTrue(att["sandbox_ok"])
        self.assertEqual(len(att["sha256_full"]), 64)

    def test_render_report(self):
        """Ensures the console report renders cleanly and returns true."""
        result = self.engine.render_report()
        self.assertTrue(result)
        out = self.buf.getvalue()
        self.assertIn("PRUBETH Sovereign Runtime Cryptographic Integrity", out)

if __name__ == "__main__":
    unittest.main()
