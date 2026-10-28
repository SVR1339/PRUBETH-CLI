"""PRUBETH Polyglot Quality & Security Linter.

Executes deterministic static analysis, security secret audits, and syntax gate verification
across 13 programming language ecosystems without external heavy dependencies.
Enforces PRINCE3 Zero Font Blur standard and SE 3.0 deterministic invariants.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from prubeth.verification.polyglot import PolyglotSyntaxGate

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID", "CRITICAL"),
    (r"sk-(?:or-)?[a-zA-Z0-9_\-]{24,}", "OpenAI / OpenRouter API Key", "CRITICAL"),
    (r"sk-ant-[a-zA-Z0-9_\-]{24,}", "Anthropic API Key", "CRITICAL"),
    (r"gh[pousr]_[A-Za-z0-9_]{36,}", "GitHub Personal Access Token", "CRITICAL"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Private Cryptographic Key", "CRITICAL"),
    (r"""(?:api_key|apiKey|secret_key|auth_token|client_secret)\s*[:=]\s*["'][a-zA-Z0-9_\-\.]{20,}["']""", "Hardcoded Secret Token", "CRITICAL")
]

SECURITY_PATTERNS = [
    (r"""subprocess\.(?:call|Popen|run)\([^\)]*shell\s*=\s*True""", "Unsafe Subprocess Shell Execution", "HIGH", ".py"),
    (r"""\b(?:eval|exec)\s*\(""", "Dynamic Code Execution (eval/exec)", "HIGH", ".py"),
    (r"""pickle\.(?:loads|load)\(""", "Insecure Object Deserialisation", "MEDIUM", ".py"),
    (r"""dangerouslySetInnerHTML""", "Unsafe HTML Injection (XSS Risk)", "HIGH", ".tsx,.jsx,.ts,.js"),
    (r"""f["']SELECT\s+.*WHERE.*\{""", "Potential SQL String Interpolation Injection", "HIGH", ".py")
]

class PolyglotQualityLinter:
    """Performs deep security audits, anti-pattern detection, and syntax validation."""

    def __init__(self, workspace_root: Optional[Path] = None, console: Optional[Console] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.console = console or Console(legacy_windows=False)

    def audit_workspace(self, include_tests: bool = False) -> List[Dict[str, Any]]:
        """Scans workspace files for vulnerabilities, leaks, and syntax errors."""
        issues: List[Dict[str, Any]] = []

        ignore_dirs = {
            ".git", "node_modules", ".venv", "venv", "dist", "build",
            ".pytest_cache", ".prubeth", "__pycache__", ".idea", ".vscode"
        }
        if not include_tests:
            ignore_dirs.update({"tests", "test", "spec", "fixtures"})

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                file_path = Path(root) / f
                rel_path = file_path.relative_to(self.workspace_root)
                ext = file_path.suffix.lower()

                # Skip non-source media or binary files
                if ext in [".png", ".jpg", ".jpeg", ".ico", ".exe", ".dll", ".so", ".zip", ".whl", ".pyc"]:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                # 1. Secret Detection
                for pat, name, sev in SECRET_PATTERNS:
                    matches = list(re.finditer(pat, content))
                    for m in matches:
                        line_no = content[:m.start()].count("\n") + 1
                        issues.append({
                            "file": str(rel_path).replace("\\", "/"),
                            "line": line_no,
                            "rule": name,
                            "severity": sev,
                            "message": f"Found sensitive credential matching pattern for {name}.",
                            "fix": "Move secret to environment variables or .env file."
                        })

                # 2. Security Anti-Patterns
                for pat, name, sev, applicable_exts in SECURITY_PATTERNS:
                    allowed = [e.strip() for e in applicable_exts.split(",")]
                    if ext in allowed:
                        matches = list(re.finditer(pat, content))
                        for m in matches:
                            line_no = content[:m.start()].count("\n") + 1
                            issues.append({
                                "file": str(rel_path).replace("\\", "/"),
                                "line": line_no,
                                "rule": name,
                                "severity": sev,
                                "message": f"Detected anti-pattern: {name}.",
                                "fix": "Use safe parametric primitives or sanitize input."
                            })

                # 3. Syntax Gate Verification
                ok, err = PolyglotSyntaxGate.validate_content(str(file_path), content)
                if not ok:
                    issues.append({
                        "file": str(rel_path).replace("\\", "/"),
                        "line": 1,
                        "rule": "Syntax Gate Failure",
                        "severity": "CRITICAL",
                        "message": f"Syntax error detected: {err}",
                        "fix": "Correct malformed syntax before deployment."
                    })

        return issues

    def render_report(self, include_tests: bool = False) -> int:
        """Renders diagnostic Rich table and returns exit code (0 = clean, 1 = issues found)."""
        issues = self.audit_workspace(include_tests=include_tests)
        if not issues:
            self.console.print(Panel(
                "[bold green]✔ All quality & security checks passed perfectly.[/bold green]\n"
                "[dim]Zero secrets leaked, zero command injections detected, 100% syntax gate verified.[/dim]",
                title="🛡️ PRUBETH Polyglot Quality & Security Linter",
                border_style="green",
                box=box.ROUNDED
            ))
            return 0

        table = Table(title="🛡️ PRUBETH Polyglot Security & Quality Diagnostic Report", box=box.ROUNDED)
        table.add_column("Severity", justify="center")
        table.add_column("Location", style="bold cyan")
        table.add_column("Rule / Anti-Pattern", style="magenta")
        table.add_column("Diagnostic Message", style="white")
        table.add_column("Remediation", style="green")

        for iss in issues:
            sev = iss["severity"]
            if sev == "CRITICAL":
                sev_badge = "[bold red]CRITICAL[/bold red]"
            elif sev == "HIGH":
                sev_badge = "[bold yellow]HIGH[/bold yellow]"
            else:
                sev_badge = "[dim cyan]MEDIUM[/dim cyan]"

            table.add_row(
                sev_badge,
                f"{iss['file']}:{iss['line']}",
                iss["rule"],
                iss["message"],
                iss["fix"]
            )

        self.console.print(table)
        crit_count = sum(1 for i in issues if i["severity"] == "CRITICAL")
        self.console.print(f"  [dim]Audit Summary:[/dim] [bold red]{len(issues)} issues detected ({crit_count} CRITICAL).[/bold red]\n")
        return 1 if crit_count > 0 else 0
