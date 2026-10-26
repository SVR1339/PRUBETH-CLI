"""PRUBETH Persistent Interactive Subshell Engine.

Maintains stateful directory tracking (cd), environment variable persistence (set, export),
and execution across tool turns, exactly matching Claude Code and Gemini CLI standards.
"""

import os
import sys
import subprocess
import shlex
import re
from pathlib import Path
from typing import Tuple, Optional, Dict

class PersistentSubshell:
    """Stateful subshell runner that preserves environment variables and working directory."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.cwd = self.workspace_root
        self.env: Dict[str, str] = dict(os.environ)
        self.is_windows = sys.platform == "win32"

    def execute(self, cmd: str, timeout_s: int = 60) -> Tuple[int, str]:
        """Executes a command with stateful working directory and environment persistence."""
        clean_cmd = cmd.strip()
        if not clean_cmd:
            return 0, ""

        # Handle explicit 'cd <path>' command
        if clean_cmd.startswith("cd ") or clean_cmd == "cd":
            target = clean_cmd[3:].strip()
            if not target or target == "~":
                self.cwd = self.workspace_root
                return 0, f"Changed directory to {self.cwd}"
            
            # Resolve target relative to current working directory
            new_path = (self.cwd / target).resolve()
            if new_path.is_dir():
                self.cwd = new_path
                return 0, f"Changed directory to {self.cwd}"
            else:
                return 1, f"Directory does not exist: {target}"

        # Handle 'export KEY=VAL' or 'set KEY=VAL' or '$env:KEY = "VAL"'
        export_match = re.match(r"^(?:export|set|\$env:)\s*([A-Za-z0-9_]+)\s*=\s*(.*)$", clean_cmd)
        if export_match:
            k = export_match.group(1).strip()
            v = export_match.group(2).strip().strip('"').strip("'")
            self.env[k] = v
            # If simple standalone export without compound operator, return immediately
            if "&&" not in clean_cmd and ";" not in clean_cmd:
                return 0, f"Environment variable {k} updated"

        try:
            res = subprocess.run(
                clean_cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self.cwd),
                env=self.env,
                timeout=timeout_s,
                encoding="utf-8",
                errors="replace"
            )
            out = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
            return res.returncode, out.strip()
        except subprocess.TimeoutExpired:
            return 124, f"Command timed out after {timeout_s}s"
        except Exception as e:
            return 1, f"Command execution error: {str(e)}"

    def close(self):
        """Releases all open resources."""
        pass

    def __del__(self):
        self.close()
