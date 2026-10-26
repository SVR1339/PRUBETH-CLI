"""Test suite verifying Prompt Caching, Context Caching, and Frontier Models v1.3.1."""

import unittest
import json
from unittest.mock import MagicMock, patch
import io
import sys
from rich.console import Console

from prubeth.models.gateway import UniversalModelGateway, GenerationResponse
from prubeth.config.manager import ConfigManager
from prubeth.cli.hud import calculate_session_spend, MODEL_PRICING, render_cost_report
from prubeth.models.telemetry import LLMOpsMonitor
from prubeth.cli.commands import handle_cache_command

class TestCachingAndFrontierModels(unittest.TestCase):
    """Deep verification of Prompt Caching, Context Caching, and frontier model catalogs."""

    def setUp(self):
        LLMOpsMonitor().reset()
        self.gw = UniversalModelGateway()
        self.cfg_mgr = ConfigManager()

    def test_frontier_model_alias_resolution(self):
        """Verifies resolution of all modern frontier models and provider mappings."""
        cases = [
            ("2.5-pro", "gemini-2.5-pro", "google"),
            ("gemini-2.5-flash", "gemini-2.5-flash", "google"),
            ("claude-3.7", "claude-3-7-sonnet-20250219", "anthropic"),
            ("claude-3-7-sonnet", "claude-3-7-sonnet-20250219", "anthropic"),
            ("claude-3.5", "claude-3-5-sonnet-20241022", "anthropic"),
            ("o3-mini", "o3-mini", "openai"),
            ("o1", "o1", "openai"),
            ("gpt-4.5", "gpt-4.5-preview", "openai"),
            ("deepseek-r1", "deepseek-r1", "deepseek"),
            ("deepseek-v3", "deepseek-v3", "deepseek"),
        ]
        for alias, expected_model, expected_provider in cases:
            res = self.cfg_mgr.resolve_model_and_provider(alias)
            self.assertEqual(res["model"], expected_model, f"Alias {alias} resolved to {res['model']}")
            self.assertEqual(res["provider"], expected_provider, f"Alias {alias} provider is {res['provider']}")
            self.assertTrue(res["enable_caching"])
            self.assertTrue(res["enable_context_caching"])
            self.assertEqual(res["context_cache_ttl_s"], 300)
            self.assertEqual(res["anthropic_cache_turns"], 2)

    def test_gemini_context_cache_payload_creation(self):
        """Verifies create_gemini_context_cache constructs valid Google cachedContents payloads."""
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "name": "cachedContents/cache_12345678",
                "model": "models/gemini-2.5-pro",
                "displayName": "prubeth-test-cache",
                "usageMetadata": {"totalTokenCount": 35000},
                "expireTime": "2026-10-26T07:15:00Z"
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            result = self.gw.create_gemini_context_cache(
                model="gemini-2.5-pro",
                contents=[{"role": "user", "parts": [{"text": "Large codebase documentation..."}]}],
                system_instruction="Strict coding invariants",
                ttl_s=600,
                display_name="prubeth-test-cache",
                api_key="test-gemini-key"
            )

            self.assertEqual(result["name"], "cachedContents/cache_12345678")
            self.assertEqual(result["usageMetadata"]["totalTokenCount"], 35000)

            # Inspect outgoing request
            req_arg = mock_url.call_args[0][0]
            body = json.loads(req_arg.data.decode("utf-8"))
            self.assertEqual(body["model"], "models/gemini-2.5-pro")
            self.assertEqual(body["displayName"], "prubeth-test-cache")
            self.assertEqual(body["ttl"], "600s")
            self.assertIn("systemInstruction", body)

    def test_gemini_generate_with_context_cache(self):
        """Verifies _generate_google passes cachedContent parameter and parses cachedContentTokenCount."""
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "candidates": [{
                    "content": {"parts": [{"text": "Optimized output with cached context"}]}
                }],
                "usageMetadata": {
                    "promptTokenCount": 42000,
                    "candidatesTokenCount": 512,
                    "cachedContentTokenCount": 40000,
                    "thoughtsTokenCount": 128
                }
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            resp = self.gw._generate_google(
                model="gemini-2.5-pro",
                messages="Refactor the authentication module",
                system_instruction="Staff engineer prompt",
                api_key="test-key",
                endpoint="https://generativelanguage.googleapis.com/v1beta",
                cached_content="cachedContents/cache_12345678"
            )

            self.assertEqual(resp.text, "Optimized output with cached context")
            self.assertEqual(resp.prompt_tokens, 42000)
            self.assertEqual(resp.candidate_tokens, 512)
            self.assertEqual(resp.cached_tokens, 40000)
            self.assertEqual(resp.thinking_tokens, 128)

            req_arg = mock_url.call_args[0][0]
            body = json.loads(req_arg.data.decode("utf-8"))
            self.assertEqual(body["cachedContent"], "cachedContents/cache_12345678")
            self.assertNotIn("system_instruction", body)
            self.assertNotIn("tools", body)

    def test_anthropic_ephemeral_prompt_caching(self):
        """Verifies _generate_anthropic sets ephemeral cache breakpoints and extracts cache read/write tokens."""
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "content": [{"type": "text", "text": "Claude 3.7 synthesized answer"}],
                "usage": {
                    "input_tokens": 1500,
                    "output_tokens": 450,
                    "cache_read_input_tokens": 12000,
                    "cache_creation_input_tokens": 0
                }
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            messages = [
                {"role": "user", "content": "Initial prompt"},
                {"role": "assistant", "content": "Assistant answer"},
                {"role": "user", "content": "Follow-up request"}
            ]

            resp = self.gw._generate_anthropic(
                model="claude-3-7-sonnet-20250219",
                messages=messages,
                system_instruction="Strict invariants",
                api_key="test-anthropic-key",
                endpoint="https://api.anthropic.com/v1",
                tools=True,
                enable_caching=True,
                anthropic_cache_turns=2
            )

            self.assertEqual(resp.text, "Claude 3.7 synthesized answer")
            self.assertEqual(resp.prompt_tokens, 13500)
            self.assertEqual(resp.cached_tokens, 12000)
            self.assertEqual(resp.tokens_cached, 12000)
            self.assertEqual(resp.cache_creation_tokens, 0)

            # Verify prompt caching headers & breakpoints
            req_arg = mock_url.call_args[0][0]
            self.assertEqual(req_arg.headers.get("Anthropic-beta"), "prompt-caching-2024-07-31")
            body = json.loads(req_arg.data.decode("utf-8"))
            # Breakpoint 1: System
            self.assertEqual(body["system"][0]["cache_control"], {"type": "ephemeral"})
            # Breakpoint 2: Tools
            self.assertEqual(body["tools"][-1]["cache_control"], {"type": "ephemeral"})
            # Breakpoint 3: Multi-turn history user message
            last_user_msg = [m for m in body["messages"] if m["role"] == "user"][-1]
            self.assertEqual(last_user_msg["content"][0]["cache_control"], {"type": "ephemeral"})

    def test_openai_prefix_caching_and_reasoning_tokens(self):
        """Verifies _generate_openai_compatible extracts prompt_tokens_details.cached_tokens and reasoning_tokens."""
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{
                    "message": {"role": "assistant", "content": "o3-mini reasoning complete"}
                }],
                "usage": {
                    "prompt_tokens": 8000,
                    "completion_tokens": 1200,
                    "prompt_tokens_details": {
                        "cached_tokens": 6400
                    },
                    "completion_tokens_details": {
                        "reasoning_tokens": 850
                    }
                }
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            resp = self.gw._generate_openai_compatible(
                model="o3-mini",
                messages="Prove Riemann hypothesis step 1",
                system_instruction="Mathematical rigour",
                api_key="test-openai-key",
                endpoint="https://api.openai.com/v1",
                provider_name="openai"
            )

            self.assertEqual(resp.text, "o3-mini reasoning complete")
            self.assertEqual(resp.prompt_tokens, 8000)
            self.assertEqual(resp.candidate_tokens, 1200)
            self.assertEqual(resp.cached_tokens, 6400)
            self.assertEqual(resp.thinking_tokens, 850)

    def test_cache_pricing_and_dollar_savings_calculation(self):
        """Verifies exact token cost calculations and cache savings with frontier model pricing."""
        monitor = LLMOpsMonitor()
        monitor.reset()

        # 1. Gemini-2.5-Pro: 10,000 input tokens where 8,000 are cached (75% savings on cached)
        # Base input = $1.25/M, cache read = $0.3125/M, output = $5.00/M
        monitor.record_call(
            model="gemini-2.5-pro",
            provider="google",
            latency_s=0.45,
            input_tokens=10000,
            output_tokens=2000,
            cached_tokens=8000,
            success=True
        )

        spend = calculate_session_spend()
        # Uncached input = 2,000 -> (2,000/1M)*1.25 = $0.0025
        # Cached input = 8,000 -> (8,000/1M)*0.3125 = $0.0025
        # Output = 2,000 -> (2,000/1M)*5.00 = $0.0100
        # Total cost = 0.0025 + 0.0025 + 0.0100 = $0.0150
        # Without cache = (10,000/1M)*1.25 + 0.0100 = $0.0225
        # Saved = $0.0225 - $0.0150 = $0.0075
        self.assertAlmostEqual(spend["total_cost_usd"], 0.0150, places=4)
        self.assertAlmostEqual(spend["total_saved_usd"], 0.0075, places=4)
        self.assertEqual(spend["cached_tokens"], 8000)

    def test_handle_cache_command_execution(self):
        """Verifies /cache command runs cleanly and renders multi-tier cache radar."""
        console = Console(file=io.StringIO(), force_terminal=False)
        with patch("prubeth.cli.commands.console", console):
            handle_cache_command([])
            out = console.file.getvalue()
            self.assertIn("[CACHE]", out)
            self.assertIn("KV & Context Cache", out)
            self.assertIn("Gemini Context", out)
            self.assertIn("1. System Prompt", out)

    def test_git_mention_resolution(self):
        """Verifies @git and @git:status resolution in ContextExpander (Claude Code Parity)."""
        import tempfile
        from pathlib import Path
        from prubeth.repository.context import ContextExpander
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_idx = MagicMock()
            expander = ContextExpander(workspace_root=Path(tmp_dir), index=mock_idx)
            cleaned, atts = expander.resolve_mentions("Check working tree state with @git and @diff")
            self.assertNotIn("@git", cleaned)
            self.assertNotIn("@diff", cleaned)
            types = [a["type"] for a in atts]
            self.assertIn("git", types)
            self.assertIn("diff", types)

    def test_context_compaction_and_history(self):
        """Verifies multi-turn history tracking, compact_history(), and handle_compact_command (Claude Code Parity)."""
        from prubeth.runtime.controller import AutonomousRuntimeController
        from prubeth.cli.commands import handle_compact_command

        controller = AutonomousRuntimeController()
        # Seed realistic multi-turn exchanges with large tool payloads
        large_payload = "Detailed test logs and AST nodes\n" * 60
        controller.fluid_history = [
            {"role": "user", "content": "Refactor database connection pool to handle timeouts: " + large_payload},
            {"role": "assistant", "content": "Refactored DB pool with 5s timeout: " + large_payload, "tools_summary": ["edit_file: OK", "run_command: OK"]},
            {"role": "user", "content": "Now add connection retry backoff"},
            {"role": "assistant", "content": "Added exponential backoff algorithm", "tools_summary": ["edit_file: OK"]}
        ]

        stats = controller.compact_history()
        self.assertEqual(stats["original_turns"], 4)
        self.assertEqual(stats["compacted_turns"], 2)
        self.assertGreater(stats["tokens_saved_approx"], 0)
        self.assertIn("Compacted Architectural Context", stats["summary"])

        # Test command rendering
        console = Console(file=io.StringIO(), force_terminal=False)
        with patch("prubeth.cli.commands.console", console):
            handle_compact_command([], controller=controller)
            out = console.file.getvalue()
            self.assertIn("[COMPACT]", out)
            self.assertIn("Pinned Prefix", out)

        # Test clearing history
        controller.clear_history()
        self.assertEqual(len(controller.fluid_history), 0)

    def test_frontier_thinking_and_reasoning_budgets(self):
        """Verifies thinking budget and reasoning effort parameters for Claude 3.7, Gemini 2.5, and OpenAI o3-mini."""
        # 1. Config Manager & Schema Validation
        res = self.cfg_mgr.resolve_model_and_provider("claude-3.7")
        self.assertEqual(res["thinking_budget"], 2048)
        self.assertEqual(res["reasoning_effort"], "medium")

        # 2. Google Gemini 2.5 thinkingConfig injection
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "candidates": [{"content": {"parts": [{"text": "Gemini 2.5 Thinking response"}]}}],
                "usageMetadata": {"promptTokenCount": 500, "candidatesTokenCount": 200, "thoughtsTokenCount": 180}
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            resp = self.gw._generate_google(
                model="gemini-2.5-pro",
                messages="Complex architectural reasoning",
                system_instruction="Strict invariants",
                api_key="test-key",
                endpoint="https://generativelanguage.googleapis.com/v1beta",
                thinking_budget=4096
            )
            req_arg = mock_url.call_args[0][0]
            body = json.loads(req_arg.data.decode("utf-8"))
            self.assertEqual(body["generationConfig"]["thinkingConfig"]["thinkingBudget"], 4096)
            self.assertEqual(resp.thinking_tokens, 180)

        # 3. Anthropic Claude 3.7 thinking block injection
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "content": [
                    {"type": "thinking", "thinking": "Internal chain of thought step 1 step 2"},
                    {"type": "text", "text": "Synthesized code answer"}
                ],
                "usage": {"input_tokens": 800, "output_tokens": 150}
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            resp = self.gw._generate_anthropic(
                model="claude-3-7-sonnet-20250219",
                messages="Refactor memory model",
                system_instruction="Strict invariants",
                api_key="test-key",
                endpoint="https://api.anthropic.com/v1",
                thinking_budget=2048
            )
            req_arg = mock_url.call_args[0][0]
            body = json.loads(req_arg.data.decode("utf-8"))
            self.assertEqual(body["thinking"]["type"], "enabled")
            self.assertEqual(body["thinking"]["budget_tokens"], 2048)
            self.assertGreater(resp.thinking_tokens, 0)

        # 4. OpenAI o3-mini reasoning_effort parameter injection
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "Reasoning complete", "role": "assistant"}}],
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 200,
                    "completion_tokens_details": {"reasoning_tokens": 120}
                }
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            resp = self.gw._generate_openai_compatible(
                model="o3-mini",
                messages="Optimize Triton kernel",
                system_instruction="",
                api_key="test-key",
                endpoint="https://api.openai.com/v1",
                provider_name="openai",
                reasoning_effort="high"
            )
            req_arg = mock_url.call_args[0][0]
            body = json.loads(req_arg.data.decode("utf-8"))
            self.assertEqual(body["reasoning_effort"], "high")
            self.assertNotIn("temperature", body)
            self.assertEqual(resp.thinking_tokens, 120)

    def test_context_cache_manager_lifecycle(self):
        """Verifies ContextCacheManager automated Gemini cachedContents creation, caching, and invalidation."""
        from prubeth.models.caching import ContextCacheManager
        cache_mgr = ContextCacheManager(config_manager=self.cfg_mgr, gateway=self.gw)

        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "name": "cachedContents/auto_session_9988",
                "model": "models/gemini-2.5-pro",
                "displayName": "prubeth-test",
                "usageMetadata": {"totalTokenCount": 24000},
                "expireTime": "2026-10-26T08:00:00Z"
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy-gemini-key"}):
                # 1. First call creates session
                name = cache_mgr.get_or_create_gemini_session(
                    model="gemini-2.5-pro",
                    workspace_context="Massive repository context snippet " * 200,
                    system_instruction="Strict invariants",
                    ttl_s=300
                )
                self.assertEqual(name, "cachedContents/auto_session_9988")
                self.assertIsNotNone(cache_mgr.active_gemini_session)
                self.assertFalse(cache_mgr.active_gemini_session.is_expired)

                # 2. Second call reuses session instantly without invoking urlopen again
                call_count_before = mock_url.call_count
                name2 = cache_mgr.get_or_create_gemini_session(
                    model="gemini-2.5-pro",
                    workspace_context="Massive repository context snippet " * 200,
                    system_instruction="Strict invariants",
                    ttl_s=300
                )
                self.assertEqual(name2, "cachedContents/auto_session_9988")
                self.assertEqual(mock_url.call_count, call_count_before)

                # 3. Telemetry inspection
                telem = cache_mgr.get_cache_telemetry("gemini-2.5-pro")
                self.assertEqual(telem["method_name"], "Context Caching (cachedContents REST API)")
                self.assertIsNotNone(telem["gemini_session"])
                self.assertEqual(telem["gemini_session"]["name"], "cachedContents/auto_session_9988")

                # 4. Invalidation
                cache_mgr.invalidate_gemini_cache()
                self.assertIsNone(cache_mgr.active_gemini_session)

    def test_cache_command_subcommands(self):
        """Verifies /cache status, /cache clear, and /cache refresh subcommands."""
        from prubeth.runtime.controller import AutonomousRuntimeController
        controller = AutonomousRuntimeController()
        console = Console(file=io.StringIO(), force_terminal=False)

        with patch("prubeth.cli.commands.console", console):
            handle_cache_command(["clear"], controller=controller)
            out = console.file.getvalue()
            self.assertIn("session invalidated", out)

if __name__ == "__main__":
    unittest.main()
