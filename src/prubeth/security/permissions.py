import os
import re
from enum import Enum
from pathlib import Path
from typing import Dict, Tuple, Optional, Callable, Any

class PermissionLevel(str, Enum):
    ALLOW = "ALLOW"
    ASK = "ASK"
    DENY = "DENY"

class SecurityEngine:
    """Subsystem 8: Security and Governance Engine."""

    def __init__(self, workspace_root: Optional[str] = None, auto_approve_all: bool = False):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.auto_approve_all = auto_approve_all

        # Default per-tool permission rules
        self.tool_policies: Dict[str, PermissionLevel] = {
            "read_file": PermissionLevel.ALLOW,
            "find_files": PermissionLevel.ALLOW,
            "grep_search": PermissionLevel.ALLOW,
            "git_status": PermissionLevel.ALLOW,
            "git_diff": PermissionLevel.ALLOW,
            "code_search": PermissionLevel.ALLOW,
            "resolve_symbol": PermissionLevel.ALLOW,
            "find_symbol_references": PermissionLevel.ALLOW,
            "write_file": PermissionLevel.ALLOW if auto_approve_all else PermissionLevel.ASK,
            "edit_file": PermissionLevel.ALLOW if auto_approve_all else PermissionLevel.ASK,
            "run_command": PermissionLevel.ALLOW if auto_approve_all else PermissionLevel.ASK,
        }

        # Lethal commands blacklisted regardless of approval mode
        self.hard_denylist = [
            "rm -rf /", "rm -rf /*", "mkfs", "dd if=",
            ":(){ :|:& };:", "format c:", "del /f /s /q c:\\",
            "shutdown", "reboot", "diskpart", "bcdedit",
            "vssadmin delete", "reg delete", "net user"
        ]

        # Sensitive credential redaction patterns (DevSecOps)
        self.secret_patterns = [
            (re.compile(r'(?i)(?:api_key|apikey|secret|token|password|auth|bearer)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?'), r'***REDACTED***'),
            (re.compile(r'sk-[a-zA-Z0-9]{20,}'), '[REDACTED_OPENAI_KEY]'),
            (re.compile(r'sk-ant-[a-zA-Z0-9_\-]{20,}'), '[REDACTED_ANTHROPIC_KEY]'),
            (re.compile(r'AIza[0-9A-Za-z\-_]{35}'), '[REDACTED_GEMINI_KEY]'),
            (re.compile(r'ghp_[a-zA-Z0-9]{36}'), '[REDACTED_GITHUB_TOKEN]'),
        ]

    def redact_secrets(self, text: str) -> str:
        """DevSecOps Invariant: Scrub credentials and tokens from logs, traces, and DB records."""
        if not text:
            return ""
        sanitized = text
        for pattern, replacement in self.secret_patterns:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    def validate_path(self, target_path: str) -> Tuple[bool, Path, str]:
        """Enforces that all file interactions remain strictly within the workspace jail."""
        try:
            # Expand ~ to catch home-directory traversal attempts
            expanded_str = os.path.expanduser(str(target_path))
            p = Path(expanded_str)
            resolved = p.resolve() if p.is_absolute() else (self.workspace_root / p).resolve()
            try:
                resolved.relative_to(self.workspace_root)
                return True, resolved, ""
            except ValueError:
                return False, resolved, f"Security Violation: Path '{target_path}' escapes workspace jail ({self.workspace_root})."
        except Exception as e:
            return False, Path(target_path), f"Security Error: Invalid path: {str(e)}"

    def check_tool_permission(self, tool_name: str, args: Dict[str, any], approval_callback: Optional[Callable[[str, Dict], bool]] = None) -> Tuple[bool, str]:
        """Validates tool execution against policy, jail boundaries, and human approval."""
        # 1. Hard command check
        if tool_name == "run_command":
            cmd = args.get("command", "").lower().strip()
            for dangerous in self.hard_denylist:
                if dangerous in cmd:
                    return False, f"SECURITY DENIAL: Command '{cmd}' contains dangerous blacklisted string '{dangerous}'."

        # 2. Path jail check
        path_arg = args.get("path") or args.get("file_path") or args.get("filepath") or args.get("file")
        if path_arg:
            is_safe, resolved, err = self.validate_path(str(path_arg))
            if not is_safe:
                return False, err

        # 3. Policy evaluation
        policy = self.tool_policies.get(tool_name, PermissionLevel.ASK)
        if policy == PermissionLevel.DENY:
            return False, f"SECURITY DENIAL: Tool '{tool_name}' is set to DENY in security policy."

        if policy == PermissionLevel.ASK and not self.auto_approve_all:
            if approval_callback:
                approved = approval_callback(tool_name, args)
                if not approved:
                    return False, f"USER REJECTION: Execution of {tool_name} was rejected by developer."
            else:
                return False, f"PERMISSION REQUIRED: Tool '{tool_name}' requires approval but no interactive prompt was provided."

        return True, ""
