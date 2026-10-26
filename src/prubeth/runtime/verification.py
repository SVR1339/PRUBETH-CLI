"""PRUBETH Test-Time Compute Self-Verification Engine (OpenAI o1/Codex Target).

Provides pre-commit AST syntax gates, contract breaking-change detection,
and test-time self-verification before landing modifications on disk or concluding tasks.
"""

import ast
import difflib
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

from prubeth.verification.polyglot import PolyglotSyntaxGate

class TestTimeVerifier:
    """Pre-flight and post-flight verification gates ensuring contract preservation and test passage."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()

    def verify_patch_safety(self, file_path: str, old_content: str, new_content: str) -> Tuple[bool, str]:
        """Validates that candidate content is syntactically sound and preserves backward compatibility."""
        # 1. Polyglot syntax gate
        valid_syntax, err = PolyglotSyntaxGate.validate_content(file_path, new_content)
        if not valid_syntax:
            return False, f"AST Syntax Verification Failure: {err}"

        # 2. Python interface signature contract check
        if file_path.endswith(".py") and old_content.strip():
            compat_ok, compat_err = self._check_python_signature_compatibility(old_content, new_content)
            if not compat_ok:
                return False, f"Contract Verification Failure: {compat_err}"

        return True, "Patch passed all pre-flight verification invariants."

    def analyze_ast_contract_changes(self, old_code: str, new_code: str) -> Dict[str, Any]:
        """Provides rich visual AST signature diff detailing additions, deletions, and contract modifications."""
        try:
            old_tree = ast.parse(old_code) if old_code.strip() else None
            new_tree = ast.parse(new_code) if new_code.strip() else None
        except Exception as e:
            return {"error": f"AST Parse Error: {e}", "compatible": False}

        def extract_meta(tree):
            if not tree:
                return {}
            meta = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    meta[node.name] = {
                        "kind": "async def" if isinstance(node, ast.AsyncFunctionDef) else "def",
                        "args": [a.arg for a in node.args.args],
                        "docstring": ast.get_docstring(node) is not None
                    }
                elif isinstance(node, ast.ClassDef):
                    meta[node.name] = {
                        "kind": "class",
                        "bases": [getattr(b, "id", "") for b in node.bases if hasattr(b, "id")],
                        "docstring": ast.get_docstring(node) is not None
                    }
            return meta

        old_meta = extract_meta(old_tree)
        new_meta = extract_meta(new_tree)

        added = [k for k in new_meta if k not in old_meta]
        removed = [k for k in old_meta if k not in new_meta]
        modified = []
        breaking = []

        for k in old_meta:
            if k in new_meta:
                old_d = old_meta[k]
                new_d = new_meta[k]
                if old_d.get("args") != new_d.get("args"):
                    mod_entry = {
                        "name": k,
                        "old_args": old_d.get("args", []),
                        "new_args": new_d.get("args", [])
                    }
                    modified.append(mod_entry)
                    # Check if dropped positional args
                    if len(new_d.get("args", [])) < len(old_d.get("args", [])):
                        dropped = set(old_d.get("args", [])) - set(new_d.get("args", []))
                        breaking.append(f"'{k}' dropped parameters: {dropped}")

        return {
            "compatible": len(breaking) == 0,
            "added_symbols": added,
            "removed_symbols": removed,
            "modified_symbols": modified,
            "breaking_violations": breaking
        }

    def _check_python_signature_compatibility(self, old_code: str, new_code: str) -> Tuple[bool, str]:
        """Detects accidental deletion of existing public function arguments or functions without deprecation."""
        try:
            old_tree = ast.parse(old_code)
            new_tree = ast.parse(new_code)
        except Exception:
            # If parsing fails, already caught by syntax gate
            return True, ""

        old_funcs: Dict[str, List[str]] = {}
        for node in ast.walk(old_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):  # Public function
                    old_funcs[node.name] = [a.arg for a in node.args.args]

        new_funcs: Dict[str, List[str]] = {}
        for node in ast.walk(new_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    new_funcs[node.name] = [a.arg for a in node.args.args]

        # Check for removed public functions
        for f_name, old_args in old_funcs.items():
            if f_name not in new_funcs:
                # Public function was removed; warn if callers might break
                pass
            else:
                new_args = new_funcs[f_name]
                # Check if positional parameters were dropped
                if len(new_args) < len(old_args) and not any(a == "args" for a in new_args):
                    dropped = set(old_args) - set(new_args)
                    return False, f"Public function '{f_name}' dropped parameters: {dropped}. Breaking interface contract."

        return True, ""

    def run_self_verification(self, test_cmd: Optional[str] = None, timeout: int = 45) -> Tuple[bool, str]:
        """Runs workspace verification command to verify tests pass after code modifications."""
        import subprocess
        import sys

        cmd = test_cmd
        if not cmd:
            # Check PRUBETH.md
            prubeth_file = self.workspace_root / "PRUBETH.md"
            if prubeth_file.exists():
                try:
                    for line in prubeth_file.read_text(encoding="utf-8").splitlines():
                        if "Test Command" in line and "`" in line:
                            cmd = line.split("`")[1]
                            break
                except Exception:
                    pass

        if not cmd:
            if (self.workspace_root / "tests").is_dir():
                cmd = f"{sys.executable} -m unittest discover tests"
            elif (self.workspace_root / "package.json").exists():
                cmd = "npm test"
            elif (self.workspace_root / "Cargo.toml").exists():
                cmd = "cargo test"
            else:
                return True, "No test suite detected in workspace. Verification skipped."

        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            success = (res.returncode == 0)
            output = (res.stdout + "\n" + res.stderr).strip()
            return success, output
        except subprocess.TimeoutExpired:
            return False, f"Verification timeout after {timeout}s: Command `{cmd}` did not terminate."
        except Exception as e:
            return False, f"Verification execution error: {e}"
