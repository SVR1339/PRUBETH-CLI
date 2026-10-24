import unittest
from prubeth.cli.spec import CLI_SPEC_REGISTRY, validate_cli_command_spec, CommandSpec

class TestSDDSpecification(unittest.TestCase):
    """Specification-Driven Development (SDD): Interface & Grammar Contracts."""

    def test_all_core_commands_specified(self):
        """SDD Rule: Every CLI command must have a formal specification before deployment."""
        required_commands = [
            "run", "settings", "config", "swarm", "worktrees",
            "memory", "mcp", "consensus", "rollback", "diff", "benchmark"
        ]
        for cmd in required_commands:
            self.assertTrue(validate_cli_command_spec(cmd), f"Command '{cmd}' is missing from SDD specification")
            spec = CLI_SPEC_REGISTRY[cmd]
            self.assertIsInstance(spec, CommandSpec)
            self.assertTrue(len(spec.description) > 0)
            self.assertTrue(spec.usage.startswith("prubeth"))
            self.assertIn(0, spec.expected_exit_codes)

    def test_run_command_option_specifications(self):
        """SDD Rule: Option flags, defaults, and choices must conform to type contracts."""
        run_spec = CLI_SPEC_REGISTRY["run"]
        option_names = {opt.name: opt for opt in run_spec.options}

        self.assertIn("profile", option_names)
        self.assertEqual(option_names["profile"].choices, ["builder", "deep-reasoning", "local-airgap", "safe-audit"])

        self.assertIn("output_format", option_names)
        self.assertEqual(option_names["output_format"].choices, ["text", "json", "stream-json"])

        self.assertIn("auto", option_names)
        self.assertEqual(option_names["auto"].type_name, "bool")

if __name__ == "__main__":
    unittest.main()
