"""PRUBETH Edit File Tool.

Surgically modifies existing files using fuzzy whitespace-tolerant patching and atomic writes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel
from prubeth.tools.file_ops import atomic_write_file, fuzzy_replace_text
from prubeth.verification.polyglot import PolyglotSyntaxGate


class EditFileTool(BaseTool):
    """Surgically edits an existing file with tolerance for indentation shifts."""

    name = "edit_file"
    description = "Replace an exact target code block in an existing file with replacement code."
    clearance_level = ToolClearanceLevel.WORKSPACE_MUTATION
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file to edit.",
            required=True
        ),
        ToolParameter(
            name="target",
            type="string",
            description="The exact existing text sequence to be replaced.",
            required=True
        ),
        ToolParameter(
            name="replacement",
            type="string",
            description="The new replacement content to substitute in place of target.",
            required=True
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force edit even if syntax gate detects flaws, logging an advisory instead of blocking (default False).",
            required=False,
            default=False
        ),
    ]

    def execute(self, args: Dict[str, Any], context: Any = None) -> ToolResult:
        valid, err = self.validate_args(args)
        if not valid:
            return ToolResult(success=False, output=f"Validation Error: {err}", exit_code=1)

        raw_path = str(args.get("path", "")).strip()
        target_text = str(args.get("target", ""))
        replacement_text = str(args.get("replacement", ""))
        force = bool(args.get("force", False))
        unrestricted = bool(
            getattr(context, "developer_mode", False) or
            getattr(context, "unrestricted_mode", False) or
            os.environ.get("PRUBETH_UNRESTRICTED_DEVELOPER_MODE") == "1"
        )

        if not raw_path:
            return ToolResult(success=False, output="Error: File path cannot be empty.", exit_code=1)
        if not target_text:
            return ToolResult(success=False, output="Error: Target text cannot be empty.", exit_code=1)

        target = Path(raw_path)
        if not target.is_absolute() and context and hasattr(context, "workspace_root"):
            target = Path(context.workspace_root) / target

        if not target.is_file():
            return ToolResult(success=False, output=f"Error: File not found: {raw_path}", exit_code=404)

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(success=False, output=f"Error reading file '{raw_path}': {e}", exit_code=500)

        # Execute fuzzy replacement via FuzzyPatcher with fallback
        from prubeth.runtime.patcher import FuzzyPatcher
        patcher = FuzzyPatcher()
        patch_res = patcher.apply_patch(content, target_text, replacement_text)
        if patch_res.success:
            new_content = patch_res.patched_content
            msg = f"{patch_res.match_kind} match replaced."
        else:
            success, new_content, msg = fuzzy_replace_text(content, target_text, replacement_text)
            if not success:
                return ToolResult(
                    success=False,
                    output=f"Error: Target text could not be located in {raw_path}. {patch_res.error_message or msg}",
                    exit_code=400
                )

        # Pre-flight syntax validation on updated content
        syntax_ok, syntax_err = PolyglotSyntaxGate.validate_content(str(target), new_content)
        advisory = ""
        if not syntax_ok:
            if force or unrestricted:
                advisory = f" [Advisory: Syntax invariant notice: {syntax_err} (bypassed via force/developer clearance)]"
            else:
                return ToolResult(
                    success=False,
                    output=f"Error: Edited file produces invalid syntax: {syntax_err}",
                    exit_code=422
                )

        try:
            atomic_write_file(target, new_content, encoding="utf-8")
            meta = {"path": str(target), "match_method": msg}
            if advisory:
                meta["syntax_advisory"] = syntax_err
                meta["forced"] = True

            return ToolResult(
                success=True,
                output=f"Successfully modified {raw_path}: {msg}{advisory}",
                exit_code=0,
                metadata=meta
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Error committing edit to '{raw_path}': {e}",
                exit_code=500
            )
