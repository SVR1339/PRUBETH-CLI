"""PRUBETH Closed-Loop Self-Healing Tool."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class HealTool(BaseTool):
    """Executes closed-loop test execution, diagnostic extraction, and self-healing patch iteration."""

    name = "heal"
    description = "Runs test command, intercepts failures, synthesizes corrective patch, verifies, and auto-rolls back on regressions."
    clearance_level = ToolClearanceLevel.WORKSPACE_MUTATION

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="test_command",
                type="string",
                description="Test command to run and heal if failing (e.g. 'pytest tests/test_auth.py').",
                required=True
            ),
            ToolParameter(
                name="max_attempts",
                type="integer",
                description="Maximum repair iterations to attempt (default 3).",
                required=False,
                default=3
            ),
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        from prubeth.runtime.auto_heal import AutoHealer
        test_cmd = arguments.get("test_command", "").strip()
        max_attempts = int(arguments.get("max_attempts", 3))

        if not test_cmd:
            return ToolResult.fail("Missing test_command to heal.", exit_code=1)

        healer = AutoHealer()
        res = healer.heal(test_command=test_cmd, max_attempts=max_attempts)

        if res.get("success", False):
            return ToolResult.ok(res.get("message", "Healing loop executed."), metadata=res)
        else:
            return ToolResult.fail(res.get("message", "Healing failed."), exit_code=1, metadata=res)
