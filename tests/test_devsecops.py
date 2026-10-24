import os
import unittest
import tempfile
from pathlib import Path
from prubeth.security.permissions import SecurityEngine, PermissionLevel

class TestDevSecOpsSecurityEngine(unittest.TestCase):
    """DevSecOps Methodology Verification: Security Invariants and Boundary Enforcement."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        self.security = SecurityEngine(workspace_root=str(self.workspace), auto_approve_all=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_path_traversal_jail_escapes_prevented(self):
        """DevSecOps Rule: Prevent path traversal attacks escaping workspace boundary."""
        malicious_paths = [
            "../../System32/drivers/etc/hosts",
            "../secret.env",
            os.path.abspath(os.sep) + "Windows" if os.name == "nt" else "/etc/passwd",
            str(self.workspace.parent / "unauthorized.txt")
        ]
        for bad_path in malicious_paths:
            is_safe, resolved, err = self.security.validate_path(bad_path)
            self.assertFalse(is_safe, f"Path '{bad_path}' should have failed jail validation")
            self.assertIn("escapes workspace jail", err)

    def test_valid_in_workspace_paths_allowed(self):
        """DevSecOps Rule: Legitimate project file paths inside workspace are approved."""
        safe_paths = [
            "src/main.py",
            "README.md",
            str(self.workspace / "tests" / "test_app.py")
        ]
        for safe in safe_paths:
            is_safe, resolved, err = self.security.validate_path(safe)
            self.assertTrue(is_safe, f"Safe path '{safe}' should be valid")
            self.assertEqual(err, "")

    def test_lethal_destructive_commands_blocked(self):
        """DevSecOps Rule: Destructive host commands must be unconditionally blocked."""
        lethal_commands = [
            "rm -rf /",
            "del /f /s /q C:\\",
            "shutdown -s -t 0",
            "format C: /fs:NTFS",
            "reg delete HKLM\\Software",
            "vssadmin delete shadows /all"
        ]
        for cmd in lethal_commands:
            allowed, reason = self.security.check_tool_permission("run_command", {"command": cmd})
            self.assertFalse(allowed, f"Command '{cmd}' must be blocked by DevSecOps filter")
            self.assertIn("SECURITY DENIAL", reason)

    def test_credential_and_secret_redaction(self):
        """DevSecOps Rule: Sensitive API tokens and credentials must be scrubbed from logs."""
        raw_trace = (
            "Connecting with openai_key='sk-abcdef1234567890abcdef1234567890' "
            "and gemini AIzaSyAbcdefghijklmnopqrstuvwxyz123456789 "
            "and github token ghp_1234567890abcdefghijklmnopqrstuvwxyz "
            "with password: my_super_secret_password_123!"
        )
        redacted = self.security.redact_secrets(raw_trace)
        self.assertNotIn("sk-abcdef1234567890", redacted)
        self.assertNotIn("AIzaSyAbcdefghijk", redacted)
        self.assertNotIn("ghp_1234567890", redacted)
        self.assertIn("[REDACTED_OPENAI_KEY]", redacted)
        self.assertIn("[REDACTED_GEMINI_KEY]", redacted)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", redacted)

    def test_permission_approval_callback_rejection(self):
        """DevSecOps Rule: Human-in-the-loop developer rejection must halt tool execution."""
        def deny_all(tool, args):
            return False

        allowed, reason = self.security.check_tool_permission(
            "write_file",
            {"path": "sensitive.py", "content": "print(1)"},
            approval_callback=deny_all
        )
        self.assertFalse(allowed)
        self.assertIn("USER REJECTION", reason)

    def test_permission_auto_approval_mode(self):
        """DevSecOps Rule: When auto-approval is explicitly configured, safe actions pass."""
        auto_security = SecurityEngine(workspace_root=str(self.workspace), auto_approve_all=True)
        allowed, reason = auto_security.check_tool_permission(
            "write_file",
            {"path": "safe.py", "content": "print('hello')"}
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "")

if __name__ == "__main__":
    unittest.main()
