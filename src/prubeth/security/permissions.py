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

    def __init__(self, workspace_root: Optional[str] = None, auto_approve_all: bool = False, developer_mode: bool = False):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.developer_mode = developer_mode or auto_approve_all or (os.environ.get("PRUBETH_DEVELOPER_MODE") == "1")
        self.auto_approve_all = auto_approve_all or self.developer_mode

        # Default per-tool permission rules
        self.tool_policies: Dict[str, PermissionLevel] = {
            "read_file": PermissionLevel.ALLOW,
            "find_files": PermissionLevel.ALLOW,
            "grep_search": PermissionLevel.ALLOW,
            "list_dir": PermissionLevel.ALLOW,
            "glob_search": PermissionLevel.ALLOW,
            "git_status": PermissionLevel.ALLOW,
            "git_diff": PermissionLevel.ALLOW,
            "git_log": PermissionLevel.ALLOW,
            "code_search": PermissionLevel.ALLOW,
            "resolve_symbol": PermissionLevel.ALLOW,
            "find_symbol_references": PermissionLevel.ALLOW,
            "code_structure": PermissionLevel.ALLOW,
            "find_callers": PermissionLevel.ALLOW,
            "find_callees": PermissionLevel.ALLOW,
            "find_type_definition": PermissionLevel.ALLOW,
            "find_implementations": PermissionLevel.ALLOW,
            "detect_circular_imports": PermissionLevel.ALLOW,
            "trace_data_flow": PermissionLevel.ALLOW,
            "find_dead_code": PermissionLevel.ALLOW,
            "rank_central_files": PermissionLevel.ALLOW,
            "explain_symbol": PermissionLevel.ALLOW,
            "lint_checker": PermissionLevel.ALLOW,
            "type_checker": PermissionLevel.ALLOW,
            "coverage_analyser": PermissionLevel.ALLOW,
            "patch_verifier": PermissionLevel.ALLOW,
            "todo": PermissionLevel.ALLOW,
            "test_gen": PermissionLevel.ALLOW,
            "security_linter": PermissionLevel.ALLOW,
            "crash_debugger": PermissionLevel.ALLOW,
            "spec_contract": PermissionLevel.ALLOW,
            "test_runner": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "benchmark": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "heal": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "write_file": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "edit_file": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "delete_file": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "copy_file": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "move_file": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "run_command": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "run_python": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
            "git_commit": PermissionLevel.ALLOW if self.auto_approve_all else PermissionLevel.ASK,
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
            (re.compile(r'sk-ant-[a-zA-Z0-9_\-]{20,}'), '[REDACTED_ANTHROPIC_KEY]'),
            (re.compile(r'sk-(?:proj-|or-)?[a-zA-Z0-9_\-]{20,}'), '[REDACTED_OPENAI_KEY]'),
            (re.compile(r'AIza[0-9A-Za-z\-_]{30,40}'), '[REDACTED_GEMINI_KEY]'),
            (re.compile(r'ghp_[a-zA-Z0-9]{36}'), '[REDACTED_GITHUB_TOKEN]'),
            (re.compile(r'(?i)(?:api_key|apikey|secret|token|password|auth|bearer)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?'), r'***REDACTED***'),
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
            raw_path_str = str(target_path).strip()

            # Cross-platform check: Windows drive specs (e.g. C:\...) or UNC paths (\\...)
            # On non-Windows platforms (POSIX/Linux/macOS), pathlib does not treat drive letters
            # as absolute roots, causing them to incorrectly resolve relative to workspace.
            if re.match(r'^[a-zA-Z]:[/\\]', raw_path_str) or raw_path_str.startswith('\\\\'):
                if os.name != 'nt':
                    return False, Path(raw_path_str), f"Security Violation: Path '{target_path}' escapes workspace jail ({self.workspace_root})."

            # Expand ~ to catch home-directory traversal attempts
            expanded_str = os.path.expanduser(raw_path_str)
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

    def enable_unrestricted_developer_mode(self) -> None:
        """Enables unconstrained developer clearance across all workspace and runtime tools.
        
        Preserves solely the lethal blacklist (e.g. root filesystem destruction) while eliminating
        all interactive blocking prompts for standard engineering tools.
        """
        self.developer_mode = True
        self.auto_approve_all = True
        for tool_name in self.tool_policies:
            self.tool_policies[tool_name] = PermissionLevel.ALLOW

    def is_developer_unrestricted(self) -> bool:
        """Returns True if developer is operating with frictionless clearance."""
        return self.developer_mode or self.auto_approve_all

    def grant_full_clearance(self) -> None:
        """Alias for enable_unrestricted_developer_mode."""
        self.enable_unrestricted_developer_mode()

    def configure_tool_policy(self, tool_name: str, level: PermissionLevel) -> None:
        """Customizes policy level for an individual tool."""
        self.tool_policies[tool_name] = level

    def is_catastrophic_command(self, cmd: str) -> Tuple[bool, str]:
        """Checks if a command contains non-negotiable catastrophic destruction strings."""
        lowered = cmd.lower().strip()
        for dangerous in self.hard_denylist:
            if dangerous in lowered:
                return True, dangerous
        return False, ""

    def is_dummy_secret(self, text: str) -> bool:
        """Checks if a potential secret match is an innocuous test/dummy fixture."""
        lowered = text.lower()
        dummy_markers = ["test", "dummy", "fake", "mock", "sample", "example", "placeholder", "0000"]
        return any(m in lowered for m in dummy_markers)
