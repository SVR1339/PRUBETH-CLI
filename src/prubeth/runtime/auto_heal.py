"""PRUBETH Autonomous Auto-TDD Self-Healing Engine.

Executes test suites or build commands, intercepts failures and stack traces,
formulates targeted patches via Plan A/Plan B, applies file modifications with
diff staging, verifies test results, and auto-rolls back if regressions occur.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from prubeth.persistence.checkpoints import SnapshotManager
from prubeth.models.gateway import UniversalModelGateway
from prubeth.persistence.memory import MemoryVault
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase

class AutoHealer:
    """Orchestrates closed-loop test execution, error extraction, and self-healing patch application."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        console: Optional[Console] = None,
        model_name: Optional[str] = None
    ):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.console = console or Console(legacy_windows=False)
        self.model_name = model_name
        self.gateway = UniversalModelGateway()
        self.snap_mgr = SnapshotManager(workspace_root=self.workspace_root)
        self.memory = MemoryVault(self.workspace_root / ".prubeth" / "memory")

    def run_command(self, command: str, timeout_s: int = 60) -> Tuple[int, str, str]:
        """Runs test command safely in the workspace."""
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                encoding="utf-8",
                errors="replace"
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout_s}s"
        except Exception as e:
            return 1, "", str(e)

    def extract_failing_files(self, output: str) -> List[str]:
        """Identifies file paths mentioned in Python/JS/Go tracebacks."""
        candidates = set()
        # Python traceback: File "path/to/file.py", line 123
        py_matches = re.findall(r'File "([^"]+\.py)"', output)
        candidates.update(py_matches)

        # Standard file:line patterns (e.g. src/auth.py:42: error)
        line_matches = re.findall(r'([A-Za-z0-9_\-\.\/\\]+\.[a-zA-Z0-9]+):\d+', output)
        candidates.update(line_matches)

        valid_files = []
        for c in candidates:
            p = (self.workspace_root / c).resolve()
            if p.is_file() and not any(ign in str(p) for ign in [".git", "site-packages", ".venv"]):
                try:
                    rel = p.relative_to(self.workspace_root).as_posix()
                    valid_files.append(rel)
                except ValueError:
                    pass
        return valid_files[:4]

    def heal(
        self,
        test_command: str,
        max_attempts: int = 3,
        approval_cb: Optional[Callable[[str, Dict[str, Any]], bool]] = None
    ) -> Dict[str, Any]:
        """Executes the autonomous test-driven self-healing loop."""
        self.console.print(Panel(
            f"[bold cyan]Auto-TDD Healing Engine:[/bold cyan] Intercepting command [bold green]`{test_command}`[/bold green]",
            border_style="cyan"
        ))

        # 1. Baseline Test Run
        self.console.print("  [dim cyan][TEST] Running initial test command to evaluate baseline...[/dim cyan]")
        code, stdout, stderr = self.run_command(test_command)
        combined_output = (stdout + "\n" + stderr).strip()

        if code == 0:
            self.console.print("  [bold green][OK] Command passed with exit code 0. No healing required![/bold green]")
            return {
                "success": True,
                "healed": False,
                "attempts": 0,
                "message": "Baseline command succeeded cleanly."
            }

        self.console.print(f"  [bold red][FAIL] Command failed with exit code {code}. Engaging Auto-Healer...[/bold red]")
        baseline_snap = self.snap_mgr.create_snapshot("auto_heal_baseline")
        self.console.print(f"  [dim green][SECURED] Checkpoint secured: '{baseline_snap}'[/dim green]")

        failing_files = self.extract_failing_files(combined_output)
        self.console.print(f"  [yellow]Identified candidate loci:[/yellow] {failing_files or 'General Workspace'}")

        # Gather relevant code files
        file_contexts = []
        for f in failing_files:
            p = self.workspace_root / f
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                numbered = "\n".join(f"{i+1:4d} | {l}" for i, l in enumerate(lines[:300]))
                file_contexts.append(f"### File `{f}`:\n```\n{numbered}\n```")
            except Exception:
                pass

        history_notes = []

        for attempt in range(1, max_attempts + 1):
            strategy_name = "Plan A (Direct Locus Repair)" if attempt == 1 else f"Plan B (Alternative Diagnostic Strategy - Attempt {attempt})"
            self.console.print(f"\n  [bold cyan][CYCLE {attempt}/{max_attempts}] ({strategy_name})...[/bold cyan]")

            system_instruction = (
                "You are the PRUBETH Principal Autonomous Debugger and SRE.\n"
                "A test or build command failed. Your goal is to diagnose the root cause and provide the exact file edit to make tests pass.\n"
                "Respond ONLY with a JSON object in this exact schema:\n"
                "{\n"
                '  "root_cause": "<concise explanation of bug>",\n'
                '  "file_path": "<relative path of file to fix>",\n'
                '  "action": "edit",\n'
                '  "find_str": "<exact character sequence in file to replace>",\n'
                '  "replace_str": "<replacement character sequence>"\n'
                "}\n"
                "Ensure find_str exactly matches the existing file contents."
            )

            user_prompt = (
                f"Failing Command: {test_command}\n"
                f"Exit Code: {code}\n"
                f"Error Output (Tail):\n```\n{combined_output[-3000:]}\n```\n\n"
                f"Workspace Code Files:\n" + "\n\n".join(file_contexts) + "\n\n"
                f"Previous Attempt History:\n" + "\n".join(history_notes)
            )

            resp = self.gateway.generate(
                user_prompt,
                system_instruction=system_instruction,
                model_name=self.model_name,
                model_tier="fast"
            )

            from prubeth.runtime.controller import extract_json_object
            patch_plan = extract_json_object(resp.text)

            if not patch_plan or "file_path" not in patch_plan or "find_str" not in patch_plan:
                history_notes.append(f"Attempt {attempt}: Model returned invalid JSON patch schema: {resp.text[:150]}")
                continue

            target_rel = patch_plan["file_path"].replace("\\", "/")
            target_path = self.workspace_root / target_rel
            find_str = patch_plan.get("find_str", "")
            replace_str = patch_plan.get("replace_str", "")

            if not target_path.is_file():
                history_notes.append(f"Attempt {attempt}: Target file '{target_rel}' does not exist.")
                continue

            content = target_path.read_text(encoding="utf-8", errors="replace")
            if find_str not in content:
                history_notes.append(f"Attempt {attempt}: find_str not located in '{target_rel}'.")
                continue

            new_content = content.replace(find_str, replace_str, 1)

            # Compute diff
            diff_lines = self.snap_mgr.compute_snapshot_diff()
            self.console.print(f"  [bold cyan]Root Cause Diagnosis:[/bold cyan] {patch_plan.get('root_cause')}")

            # Apply patch
            target_path.write_text(new_content, encoding="utf-8")
            self.console.print(f"  [bold green]Patched:[/bold green] `{target_rel}`")

            # Re-run test command
            self.console.print("  [dim cyan][TEST] Re-running test suite to verify patch...[/dim cyan]")
            re_code, re_stdout, re_stderr = self.run_command(test_command)
            re_output = (re_stdout + "\n" + re_stderr).strip()

            if re_code == 0:
                verified_snap = self.snap_mgr.create_snapshot("auto_heal_verified")
                self.console.print(Panel(
                    f"[bold green][SUCCESS] HEALING SUCCEEDED ON ATTEMPT {attempt}![/bold green]\n"
                    f"Command `{test_command}` exited with code 0.\n"
                    f"Fixed File: `{target_rel}`\n"
                    f"Diagnosis: {patch_plan.get('root_cause')}\n"
                    f"Checkpoint secured: '{verified_snap}'",
                    border_style="green"
                ))

                # Log to MemoryVault
                self.memory.record_anti_pattern(
                    failing_component=target_rel,
                    error_symptom=combined_output[-200:].strip(),
                    root_cause=patch_plan.get("root_cause", "Bug auto-healed"),
                    prevention_rule=f"Applied patch in {target_rel}"
                )

                return {
                    "success": True,
                    "healed": True,
                    "attempts": attempt,
                    "fixed_file": target_rel,
                    "diagnosis": patch_plan.get("root_cause")
                }
            else:
                self.console.print(f"  [yellow]Attempt {attempt} failed (exit code {re_code}). Auto-rolling back to baseline...[/yellow]")
                self.snap_mgr.rollback_to_snapshot(baseline_snap)
                history_notes.append(
                    f"Attempt {attempt} on '{target_rel}' failed with: {re_output[-300:]}. Rolled back."
                )

        # If exhausted all attempts, rollback cleanly
        self.snap_mgr.rollback_to_snapshot(baseline_snap)
        self.console.print(Panel(
            f"[bold red][EXHAUSTED] Auto-healing exhausted {max_attempts} cycles without 100% test pass.[/bold red]\n"
            f"Workspace safely restored to pre-healing baseline.",
            border_style="red"
        ))
        return {
            "success": False,
            "healed": False,
            "attempts": max_attempts,
            "message": "Exhausted all recovery attempts."
        }
