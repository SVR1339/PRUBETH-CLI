import os
import subprocess
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from prubeth.security.permissions import SecurityEngine
from prubeth.persistence.database import TaskDatabase
from prubeth.verification.polyglot import PolyglotSyntaxGate

class ToolExecutionEngine:
    """Subsystem 4: Tool Execution Engine with Permission Checks and Audit Trail."""

    def __init__(self, security: SecurityEngine, db: TaskDatabase, current_task_id: str, mcp_mgr: Optional[Any] = None):
        self.security = security
        self.db = db
        self.task_id = current_task_id
        self.mcp_mgr = mcp_mgr

    def execute_tool(self, tool_name: str, args: Dict[str, Any], approval_cb=None) -> Tuple[bool, str]:
        """Validates permissions, runs tool, logs execution to SQLite database."""
        # 1. Security & Permission Check
        is_permitted, err = self.security.check_tool_permission(tool_name, args, approval_cb)
        if not is_permitted:
            self.db.record_tool_execution(self.task_id, tool_name, args, err, exit_code=403)
            return False, err

        # 2. Execution Dispatch
        start_time = os.times().elapsed
        success = True
        exit_code = 0
        output = ""

        try:
            target_path = str(args.get("path") or args.get("file_path") or args.get("filepath") or args.get("file") or "")
            target_content = str(args.get("content") or args.get("text") or args.get("data") or "")
            target_cmd = str(args.get("command") or args.get("cmd") or "")
            target_query = str(args.get("query") or args.get("pattern") or args.get("regex") or "")

            if tool_name == "read_file":
                output = self._read_file(target_path, args.get("start_line", 1), args.get("end_line"), limit=args.get("limit"))
                if output.startswith("Error:"):
                    success = False
            elif tool_name == "write_file":
                output = self._write_file(target_path, target_content)
            elif tool_name == "edit_file":
                output = self._edit_file(target_path, args.get("target", ""), args.get("replacement", ""), edits=args.get("edits"))
                if output.startswith("Error:"):
                    success = False
            elif tool_name == "run_command":
                exit_code, output = self._run_command(target_cmd, args.get("timeout", 60))
                success = (exit_code == 0)
            elif tool_name == "grep_search":
                output = self._grep_search(target_query, target_path or ".")
            elif tool_name == "find_files":
                output = "\n".join(self._find_files(args.get("pattern") or target_query or "**/*"))
            elif tool_name == "git_diff":
                exit_code, output = self._run_command("git diff HEAD")
                if "not recognized" in output:
                    output = "Git is not installed or not configured in system PATH."
                    success = True
            elif tool_name == "git_status":
                exit_code, output = self._run_command("git status --short")
                if "not recognized" in output:
                    output = "Git is not installed or not configured in system PATH."
                    success = True
            elif tool_name.startswith("mcp_") and self.mcp_mgr:
                parts = tool_name.split("_", 2)
                if len(parts) >= 3:
                    s_name, t_name = parts[1], parts[2]
                    success, output = self.mcp_mgr.call_mcp_tool(s_name, t_name, args)
                else:
                    return False, f"Malformed MCP tool name: {tool_name}"
            else:
                return False, f"Unknown tool: {tool_name}"

        except Exception as e:
            success = False
            output = f"Execution Exception in {tool_name}: {str(e)}"
            exit_code = 500

        duration_ms = int((os.times().elapsed - start_time) * 1000)
        self.db.record_tool_execution(self.task_id, tool_name, args, output, exit_code=exit_code, duration_ms=duration_ms)
        return success, output

    def _read_file(self, path: str, start_line: int, end_line: Optional[int], limit: Optional[int] = None) -> str:
        _, p, _ = self.security.validate_path(path)
        if not p.is_file():
            return f"Error: File not found: {path}"
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        s_idx = max(0, start_line - 1)
        e_idx = len(lines) if end_line is None else min(len(lines), end_line)
        selected = lines[s_idx:e_idx]
        rendered = "".join([f"{s_idx + i + 1:4d} | {l}" for i, l in enumerate(selected)])
        if limit and len(rendered) > limit:
            rendered = rendered[:limit] + f"\n... [Truncated {len(rendered) - limit} characters for context budgeting]"
        return rendered

    def _write_file(self, path: str, content: str) -> str:
        _, p, _ = self.security.validate_path(path)
        valid, err = PolyglotSyntaxGate.validate_content(path, content)
        if not valid:
            raise ValueError(f"Pre-Flight Syntax Invariant Failed: {err}")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {path}"

    def _edit_file(self, path: str, target: str = "", replacement: str = "", edits: Optional[List[Dict[str, Any]]] = None) -> str:
        _, p, _ = self.security.validate_path(path)
        if not p.is_file():
            return f"Error: File not found: {path}"
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()

        if edits:
            new_content = content
            for edit in edits:
                action = edit.get("action", "append")
                edit_content = edit.get("content", "")
                if action == "append":
                    new_content += edit_content
                elif action == "insert":
                    line_no = edit.get("line", 1)
                    lines = new_content.splitlines(keepends=True)
                    lines.insert(max(0, line_no - 1), edit_content)
                    new_content = "".join(lines)
                elif action == "replace":
                    t = edit.get("target", "")
                    r = edit.get("replacement", "")
                    if t and t in new_content:
                        new_content = new_content.replace(t, r, 1)
        else:
            if not target:
                return f"Error: Target text cannot be empty in {path}."
            if target not in content:
                return f"Error: Target text not found in {path}. Make sure indentation and whitespace match exactly."
            if content.count(target) > 1:
                return f"Error: Target text matches multiple times in {path}. Provide more surrounding context."
            new_content = content.replace(target, replacement, 1)

        valid, err = PolyglotSyntaxGate.validate_content(path, new_content)
        if not valid:
            raise ValueError(f"Pre-Flight Syntax Invariant Failed: {err}")
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Successfully modified {path}"

    def _run_command(self, cmd: str, timeout: int = 60) -> Tuple[int, str]:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(self.security.workspace_root),
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        out = (res.stdout or "") + ("\n[STDERR]\n" + res.stderr if res.stderr else "")
        trimmed = out.strip()
        if res.returncode != 0:
            if not trimmed:
                trimmed = f"Command failed with exit code {res.returncode}"
            else:
                trimmed = f"{trimmed}\nCommand failed with exit code {res.returncode}"
        return res.returncode, trimmed

    def _grep_search(self, query: str, path: str) -> str:
        _, resolved, _ = self.security.validate_path(path)
        matches = []
        ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", ".prubeth"}
        for root, dirs, files in os.walk(resolved):
            dirs[:] = [d for d in dirs if d not in ignored]
            for file in files:
                f_path = Path(root) / file
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        for idx, line in enumerate(f, 1):
                            if query in line:
                                rel = f_path.relative_to(self.security.workspace_root).as_posix()
                                matches.append(f"{rel}:{idx} | {line.strip()}")
                                if len(matches) >= 40:
                                    break
                except Exception:
                    continue
            if len(matches) >= 40:
                break
        return "\n".join(matches) if matches else f"No matches found for '{query}'"

    def _find_files(self, pattern: str) -> List[str]:
        matches = []
        ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", ".prubeth"}
        for root, dirs, files in os.walk(self.security.workspace_root):
            dirs[:] = [d for d in dirs if d not in ignored]
            for file in files:
                rel = os.path.relpath(os.path.join(root, file), self.security.workspace_root).replace("\\", "/")
                if Path(rel).match(pattern):
                    matches.append(rel)
                    if len(matches) >= 50:
                        break
            if len(matches) >= 50:
                break
        return matches
