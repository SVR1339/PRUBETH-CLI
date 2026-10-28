"""PRUBETH Pre-Flight Dry-Run Patch Verification Tool."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel
from prubeth.runtime.patcher import FuzzyPatcher


class PatchVerifierTool(BaseTool):
    """Dry-runs code patches without touching the disk, verifying match validity and syntax integrity."""

    name = "patch_verifier"
    description = "Tests prospective patch application against a file in dry-run mode, verifying syntax and match count."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.patcher = FuzzyPatcher()

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path of the target file to test patch against.",
                required=True
            ),
            ToolParameter(
                name="target",
                type="string",
                description="Exact or fuzzy character sequence to be replaced.",
                required=True
            ),
            ToolParameter(
                name="replacement",
                type="string",
                description="New code content to insert in place of target.",
                required=True
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path_str = arguments.get("path", "").strip()
        target = arguments.get("target", "")
        replacement = arguments.get("replacement", "")

        if not path_str:
            return ToolResult.fail("Missing file path.", exit_code=1)
        if not target:
            return ToolResult.fail("Target string cannot be empty.", exit_code=1)

        p = Path(path_str)
        if not p.is_file():
            return ToolResult.fail(f"File '{path_str}' not found.", exit_code=1)

        try:
            original_content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult.fail(f"Failed reading file: {str(e)}", exit_code=1)

        result = self.patcher.apply_patch(original_content, target, replacement)

        if not result.success:
            return ToolResult.fail(
                f"Patch verification failed: {result.error_message}",
                exit_code=1,
                metadata={
                    "match_kind": result.match_kind,
                    "confidence": result.confidence,
                    "matches_found": result.matches_found
                }
            )

        # Check syntax if python file
        syntax_valid = True
        syntax_err = ""
        if p.suffix == ".py":
            try:
                ast.parse(result.patched_content, filename=path_str)
            except SyntaxError as e:
                syntax_valid = False
                syntax_err = f"SyntaxError in prospective patched code: line {e.lineno}: {e.msg}"

        if not syntax_valid:
            return ToolResult.fail(
                syntax_err,
                exit_code=1,
                metadata={"match_kind": result.match_kind, "syntax_valid": False}
            )

        return ToolResult.ok(
            (
                f"Patch Verification PASSED (Dry-Run):\n"
                f"  Match Kind:  {result.match_kind}\n"
                f"  Confidence:  {result.confidence:.2f}\n"
                f"  Matches:     {result.matches_found}\n"
                f"  Syntax:      VALID\n"
                f"  Size Delta:  {len(result.patched_content) - len(original_content):+d} chars\n"
            ),
            metadata={
                "match_kind": result.match_kind,
                "confidence": result.confidence,
                "syntax_valid": True,
                "delta": len(result.patched_content) - len(original_content)
            }
        )
