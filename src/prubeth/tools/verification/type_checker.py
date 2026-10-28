"""PRUBETH Automated Type Annotation & Contract Verification Tool."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel


class TypeCheckerTool(BaseTool):
    """Verifies static type annotations using mypy, pyright, or built-in AST signature analysis."""

    name = "type_checker"
    description = "Checks static type signatures and annotations using mypy or built-in AST inspection."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Target file or directory path to type-check.",
                required=True
            ),
            ToolParameter(
                name="engine",
                type="string",
                description="Type checker engine: 'ast' (built-in coverage checker) or 'mypy'.",
                required=False,
                default="ast"
            ),
            ToolParameter(
                name="strict",
                type="boolean",
                description="Enforce type annotations on all parameters and return types.",
                required=False,
                default=False
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path_str = arguments.get("path", "").strip()
        engine = arguments.get("engine", "ast").lower()
        strict = bool(arguments.get("strict", False))

        if not path_str:
            return ToolResult.fail("Missing target path.", exit_code=1)

        p = Path(path_str)
        if not p.exists():
            return ToolResult.fail(f"Target path '{path_str}' does not exist.", exit_code=1)

        if engine == "mypy":
            strict_flag = "--strict" if strict else ""
            cmd = f"mypy {path_str} {strict_flag} --no-error-summary"
            try:
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
                if proc.returncode == 0:
                    return ToolResult.ok(proc.stdout or proc.stderr, metadata={"engine": "mypy"})
                else:
                    return ToolResult.fail(proc.stdout or proc.stderr, exit_code=proc.returncode, metadata={"engine": "mypy"})
            except Exception:
                # Fallback to built-in AST
                pass

        return self._run_ast_type_checker(p, strict=strict)

    def _run_ast_type_checker(self, target_path: Path, strict: bool = False) -> ToolResult:
        files = [target_path] if target_path.is_file() else list(target_path.rglob("*.py"))
        total_functions = 0
        annotated_functions = 0
        missing_annotations: List[Dict[str, Any]] = []

        for f in files:
            if not f.name.endswith(".py"):
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"), filename=str(f))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("__") and node.name.endswith("__") and node.name != "__init__":
                            continue
                        total_functions += 1
                        has_return = node.returns is not None or node.name == "__init__"
                        unannotated_args = []
                        for arg in node.args.args:
                            if arg.arg in ("self", "cls"):
                                continue
                            if arg.annotation is None:
                                unannotated_args.append(arg.arg)

                        if has_return and not unannotated_args:
                            annotated_functions += 1
                        else:
                            missing_annotations.append({
                                "file": str(f),
                                "line": node.lineno,
                                "function": node.name,
                                "missing_return": not has_return,
                                "unannotated_arguments": unannotated_args
                            })
            except Exception:
                pass

        coverage_pct = (annotated_functions / total_functions * 100) if total_functions > 0 else 100.0
        success = (len(missing_annotations) == 0) if strict else True

        summary = (
            f"Type Annotation Coverage: {coverage_pct:.1f}% ({annotated_functions}/{total_functions} functions fully annotated).\n"
            f"Found {len(missing_annotations)} functions with missing type annotations."
        )
        if not success:
            summary = "Strict type checking failed: missing type annotations.\n" + summary
        full_out = summary + "\n" + json.dumps(missing_annotations[:50], indent=2)

        meta = {
            "coverage_pct": coverage_pct,
            "total_functions": total_functions,
            "annotated_functions": annotated_functions,
            "missing_count": len(missing_annotations)
        }

        if success:
            return ToolResult.ok(full_out, metadata=meta)
        else:
            return ToolResult.fail(full_out, exit_code=1, metadata=meta)
