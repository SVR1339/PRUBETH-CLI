"""PRUBETH Spec-Driven Development Pre-Flight Contract Verification Tool."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel
from prubeth.runtime.contract import ASTContractGate


class SpecContractTool(BaseTool):
    """Inspects proposed code edits and detects breaking interface changes or broken callers before writing to disk."""

    name = "spec_contract"
    description = "Checks proposed code changes for breaking interface alterations, missing parameters, and broken callers."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def __init__(self):
        super().__init__()
        self.gate = ASTContractGate()

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Target file path.",
                required=True
            ),
            ToolParameter(
                name="new_content",
                type="string",
                description="Prospective new file content to verify against existing contract.",
                required=True
            ),
            ToolParameter(
                name="force",
                type="boolean",
                description="Whether to permit breaking changes (default False).",
                required=False,
                default=False
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        file_path = arguments.get("file_path", "").strip()
        new_content = arguments.get("new_content", "")
        force = bool(arguments.get("force", False))

        if not file_path:
            return ToolResult.fail("Missing file_path.", exit_code=1)

        p = Path(file_path)
        old_content = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""

        result = self.gate.verify_change(
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
            force=force
        )

        breaking_list = [
            f"- [{b.severity.value}] {b.symbol_name}: {b.message}"
            for b in result.breaking_changes
        ]

        summary_lines = [
            f"Contract Verification for '{file_path}':",
            f"  Status: {'PASSED' if result.valid else 'BLOCKED (Breaking Changes Detected)'}",
            f"  Breaking Changes Count: {len(result.breaking_changes)}",
            f"  Affected Callers: {len(result.affected_callers)}",
        ]
        if breaking_list:
            summary_lines.append("\nDetected Issues:")
            summary_lines.extend(breaking_list)
        if result.remediation_advice:
            summary_lines.append("\nRemediation Suggestions:")
            summary_lines.extend(f"- {r}" for r in result.remediation_advice)

        out_text = "\n".join(summary_lines)
        meta = {
            "valid": result.valid,
            "breaking_count": len(result.breaking_changes),
            "affected_callers": result.affected_callers,
            "has_errors": result.has_errors
        }

        if result.valid:
            return ToolResult.ok(out_text, metadata=meta)
        else:
            return ToolResult.fail(out_text, exit_code=1, metadata=meta)
