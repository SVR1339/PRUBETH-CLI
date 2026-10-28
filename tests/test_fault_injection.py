import os
import unittest
import tempfile
from pathlib import Path

from prubeth.tools.execution import ToolExecutionEngine
from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase
from prubeth.runtime.controller import extract_json_object
from prubeth.config.manager import ConfigManager

class TestFaultInjection(unittest.TestCase):
    """Fault Injection: Chaotic Verification of Model Failures, Timeouts, Interrupted Commands & Bad Inputs."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        self.db = TaskDatabase(str(self.workspace / ".prubeth" / "fault.db"))
        self.sec = SecurityEngine(workspace_root=str(self.workspace), auto_approve_all=True)
        self.engine = ToolExecutionEngine(self.sec, self.db, "fault-task-1")

    def tearDown(self):
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass
        self.temp_dir.cleanup()

    def test_fault_injection_unknown_tool_hallucination(self):
        """Fault Injection: When model hallucinates a non-existent tool name."""
        ok, res = self.engine.execute_tool("hallucinated_teleport_code", {"arg": 123})
        self.assertFalse(ok)
        self.assertIn("Unknown tool", res)

    def test_fault_injection_malformed_json_extractor(self):
        """Fault Injection: When model outputs malformed markdown blocks or broken JSON."""
        # Clean markdown fence
        resp1 = '```json\n{"tool": "read_file", "args": {"path": "main.py"}}\n```'
        call1 = extract_json_object(resp1)
        self.assertIsNotNone(call1)
        self.assertEqual(call1["tool"], "read_file")

        # Unfenced raw JSON
        resp2 = '{"tool": "git_status", "args": {}}'
        call2 = extract_json_object(resp2)
        self.assertIsNotNone(call2)
        self.assertEqual(call2["tool"], "git_status")

        # Conversational text without tool call
        resp3 = "I have completed the task and all tests are passing."
        call3 = extract_json_object(resp3)
        self.assertIsNone(call3)

    def test_fault_injection_failing_shell_command(self):
        """Fault Injection: Subprocess command exits with non-zero error code."""
        # Non-zero exit command
        ok, out = self.engine.execute_tool("run_command", {"command": "python -c \"import sys; sys.exit(42)\""})
        self.assertFalse(ok)
        self.assertIn("Command failed with exit code 42", out)

    def test_fault_injection_missing_file_read(self):
        """Fault Injection: Model attempts to read non-existent file."""
        ok, out = self.engine.execute_tool("read_file", {"path": "does_not_exist.py"})
        self.assertFalse(ok)
        self.assertIn("File not found", out)

    def test_fault_injection_edit_nonexistent_target_string(self):
        """Fault Injection: Model attempts edit_file with a target string that is not in the file."""
        test_file = self.workspace / "sample.py"
        test_file.write_text("x = 10\n", encoding="utf-8")

        ok, out = self.engine.execute_tool("edit_file", {
            "path": "sample.py",
            "target": "this_string_does_not_exist",
            "replacement": "y = 20"
        })
        self.assertFalse(ok)
        self.assertIn("not found", out)

    def test_fault_injection_model_gateway_failover_cascade(self):
        """Fault Injection: UniversalModelGateway cascades to backup provider when primary fails."""
        from unittest.mock import patch, MagicMock
        from prubeth.models.gateway import UniversalModelGateway, GenerationResponse

        gateway = UniversalModelGateway()

        # Mock primary failing with 429 RateLimit, secondary succeeding
        with patch.object(gateway, "_generate_google", side_effect=Exception("429 Too Many Requests")):
            with patch.object(gateway, "_generate_openai_compatible", return_value=GenerationResponse(
                text="Failover cascade response",
                model="openrouter/free",
                provider="openrouter"
            )):
                resp = gateway.generate(
                    prompt="Hello world",
                    model_name="gemini-3.1-pro-preview"
                )
                self.assertIsNotNone(resp)
                self.assertEqual(resp.text, "Failover cascade response")
                self.assertEqual(resp.model, "openrouter/free")

    def test_fault_injection_timeout_autoswitch_to_local_model(self):
        """Fault Injection: High latency / timeout triggers instant auto-switch to local downloaded model."""
        from unittest.mock import patch
        from prubeth.models.gateway import UniversalModelGateway, GenerationResponse

        gateway = UniversalModelGateway()

        # Mock cloud model timing out ("taking too much time")
        with patch.object(gateway, "_generate_google", side_effect=TimeoutError("The read operation timed out")):
            # Mock local offline loaded model present in LM Studio
            with patch.object(gateway, "detect_local_model", return_value={
                "provider": "lm_studio",
                "model": "qwen2.5-coder-7b-instruct",
                "endpoint": "http://localhost:1234/v1",
                "api_key": ""
            }):
                with patch.object(gateway, "_generate_openai_compatible", return_value=GenerationResponse(
                    text="Local model executed instantaneously",
                    model="qwen2.5-coder-7b-instruct",
                    provider="lm_studio"
                )):
                    resp = gateway.generate(prompt="Build auth controller", model_name="gemini-3.1-pro-preview")
                    self.assertIsNotNone(resp)
                    self.assertEqual(resp.provider, "lm_studio")
                    self.assertEqual(resp.model, "qwen2.5-coder-7b-instruct")
                    self.assertEqual(resp.text, "Local model executed instantaneously")

    def test_detect_local_model_offline_resilience(self):
        """Fast-probe should return None and not raise when local engine is offline."""
        from prubeth.models.gateway import UniversalModelGateway
        from unittest.mock import patch
        gateway = UniversalModelGateway()
        with patch("socket.socket.connect", side_effect=OSError("Engine offline")):
            res = gateway.detect_local_model()
            self.assertIsNone(res)

    def test_fault_injection_auth_error_autoswitch_to_local_model(self):
        """Fault Injection: Invalid API Key / 401 Unauthorized triggers instant auto-switch to local model."""
        from unittest.mock import patch
        from prubeth.models.gateway import UniversalModelGateway, GenerationResponse

        gateway = UniversalModelGateway()

        # Mock cloud model failing with 401 Unauthorized
        with patch.object(gateway, "_generate_google", side_effect=Exception("HTTP Error 401: Unauthorized - Invalid API Key")):
            # Mock local offline loaded model present in Ollama
            with patch.object(gateway, "detect_local_model", return_value={
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "endpoint": "http://localhost:11434/v1",
                "api_key": ""
            }):
                with patch.object(gateway, "_generate_openai_compatible", return_value=GenerationResponse(
                    text="Local model executed cleanly after auth error",
                    model="qwen2.5-coder:7b",
                    provider="ollama"
                )):
                    resp = gateway.generate(prompt="Write login test", model_name="gemini-3.1-pro-preview")
                    self.assertIsNotNone(resp)
                    self.assertEqual(resp.provider, "ollama")
                    self.assertEqual(resp.model, "qwen2.5-coder:7b")
                    self.assertEqual(resp.text, "Local model executed cleanly after auth error")

    def test_onboarding_and_factory_reset(self):
        """Setup & Onboarding: Factory reset and probe capabilities execute cleanly."""
        from prubeth.cli.setup import probe_local_ai_capabilities, render_onboarding_wizard, execute_factory_reset
        from prubeth.config.manager import ConfigManager
        from rich.console import Console
        from io import StringIO

        out = StringIO()
        c = Console(file=out)
        info = probe_local_ai_capabilities()
        self.assertIn("ollama_installed", info)

        temp_cfg_dir = self.workspace / ".prubeth"
        temp_cfg_dir.mkdir(parents=True, exist_ok=True)
        temp_cfg_mgr = ConfigManager(config_dir=temp_cfg_dir)

        # Test rendering onboarding wizard with isolated config
        render_onboarding_wizard(c, cfg_mgr=temp_cfg_mgr, interactive=False)
        self.assertIn("PRUBETH First-Time Setup", out.getvalue())

        # Test factory reset execution with isolated config
        out_reset = StringIO()
        c_reset = Console(file=out_reset)
        execute_factory_reset(c_reset, cfg_mgr=temp_cfg_mgr)
        self.assertIn("Factory Default Reset", out_reset.getvalue())

if __name__ == "__main__":
    unittest.main()
