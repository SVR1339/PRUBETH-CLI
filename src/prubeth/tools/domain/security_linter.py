"""PRUBETH Automated Security, Secrets, and Vulnerability Scanner Tool."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Dict, Any, List

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel

SECRET_PATTERNS = [
    (re.compile(r"""AIza[0-9A-Za-z\-_]{30,40}"""), "Google Cloud / Firebase API Key", "CRITICAL"),
    (re.compile(r"""sk-(?:proj-|ant-|or-)?[a-zA-Z0-9\-_]{20,}"""), "OpenAI / Anthropic Secret Key", "CRITICAL"),
    (re.compile(r"""ghp_[a-zA-Z0-9]{36}"""), "GitHub Personal Access Token", "CRITICAL"),
    (re.compile(r"""AKIA[0-9A-Z]{16}"""), "AWS Access Key ID", "CRITICAL"),
    (re.compile(r"""(?i)(?:api_key|apikey|secret|token|password)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{20,})["']"""), "Hardcoded Secret / Token", "HIGH"),
]

INSECURE_PATTERNS = [
    (re.compile(r"""\beval\s*\("""), "Dangerous eval() usage", "HIGH"),
    (re.compile(r"""\bexec\s*\("""), "Dangerous exec() usage", "HIGH"),
    (re.compile(r"""subprocess\.(?:run|Popen|call)\(.*shell\s*=\s*True"""), "Subprocess shell=True injection risk", "MEDIUM"),
    (re.compile(r"""hashlib\.(?:md5|sha1)\("""), "Weak cryptographic hash (MD5/SHA1)", "LOW"),
    (re.compile(r"""(?i)(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?\s*%\s*\w+"""), "Potential SQL string formatting injection", "HIGH"),
    (re.compile(r"""(?i)f["'].*?(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?\{"""), "Potential SQL f-string injection", "HIGH"),
]


class SecurityLinterTool(BaseTool):
    """Scans workspace files for leaked credentials, secrets, injection vectors, and dangerous patterns."""

    name = "security_linter"
    description = "Scans files for hardcoded API keys, secrets, injection vulnerabilities, and dangerous constructs."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Target directory or file path to scan (default current directory).",
                required=False,
                default="."
            ),
            ToolParameter(
                name="min_severity",
                type="string",
                description="Minimum severity threshold: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'.",
                required=False,
                default="LOW"
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path_str = arguments.get("path", ".").strip() or "."
        min_sev = arguments.get("min_severity", "LOW").upper().strip()

        sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        min_rank = sev_rank.get(min_sev, 1)

        root = Path(path_str)
        if not root.exists():
            return ToolResult.fail(f"Path '{path_str}' does not exist.", exit_code=1)

        findings: List[Dict[str, Any]] = []
        ignored_dirs = {".git", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}

        files = [root] if root.is_file() else []
        if not root.is_file():
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in ignored_dirs and not d.startswith(".")]
                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in (".py", ".ts", ".js", ".json", ".yaml", ".yml", ".env", ".toml", ".sh", ".rs", ".go"):
                        files.append(Path(dirpath) / fn)

        for f in files:
            # Skip test fixtures that test security patterns intentionally
            if "test_security" in f.name or "test_key_verifier" in f.name:
                continue

            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()

                # 1. Check Secret Patterns
                for pat, desc, sev in SECRET_PATTERNS:
                    if sev_rank.get(sev, 1) < min_rank:
                        continue
                    for idx, line in enumerate(lines, start=1):
                        if pat.search(line):
                            findings.append({
                                "file": str(f.as_posix()),
                                "line": idx,
                                "type": "SECRET",
                                "severity": sev,
                                "description": desc,
                                "snippet": line.strip()[:100]
                            })

                # 2. Check Insecure Code Patterns
                for pat, desc, sev in INSECURE_PATTERNS:
                    if sev_rank.get(sev, 1) < min_rank:
                        continue
                    for idx, line in enumerate(lines, start=1):
                        if pat.search(line):
                            findings.append({
                                "file": str(f.as_posix()),
                                "line": idx,
                                "type": "VULNERABILITY",
                                "severity": sev,
                                "description": desc,
                                "snippet": line.strip()[:100]
                            })
            except Exception:
                continue

        has_critical = any(item["severity"] in ("CRITICAL", "HIGH") for item in findings)
        summary = (
            f"Security Audit for '{path_str}':\n"
            f"  Files Scanned: {len(files)}\n"
            f"  Issues Found:  {len(findings)} ({sum(1 for x in findings if x['severity'] == 'CRITICAL')} critical, {sum(1 for x in findings if x['severity'] == 'HIGH')} high)\n"
        )
        for it in findings[:25]:
            summary += f"- [{it['severity']}] {it['description']} at {it['file']}:{it['line']}\n"

        meta = {"findings": findings, "count": len(findings)}
        if not has_critical:
            return ToolResult.ok(summary, metadata=meta)
        else:
            return ToolResult.fail(summary, exit_code=1, metadata=meta)
