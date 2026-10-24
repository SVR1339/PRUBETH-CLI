"""PRUBETH Continuous Memory & Anti-Pattern Vault.

Persists learned project conventions, architectural decisions, and
anti-patterns across CLI sessions so the agent never repeats mistakes.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

class MemoryVault:
    """Subsystem 12: Continuous Intelligence & Anti-Pattern Ledger."""

    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or (Path.cwd() / ".prubeth" / "memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.anti_patterns_file = self.memory_dir / "anti-patterns.md"
        self.decisions_file = self.memory_dir / "decisions.md"
        self._ensure_files()

    def _ensure_files(self):
        """Initializes markdown ledgers if they do not exist."""
        if not self.anti_patterns_file.exists():
            header = (
                "# PRUBETH Learned Anti-Patterns Ledger\n\n"
                "This ledger records past diagnostic failures, bug root causes, and verified fixes.\n"
                "The agent consults this memory before planning code edits to prevent regressions.\n\n"
                "---\n\n"
            )
            self.anti_patterns_file.write_text(header, encoding="utf-8")

        if not self.decisions_file.exists():
            header = (
                "# PRUBETH Architectural Decisions Ledger\n\n"
                "This ledger records permanent design decisions, schema invariants, and conventions.\n\n"
                "---\n\n"
            )
            self.decisions_file.write_text(header, encoding="utf-8")

    def record_anti_pattern(
        self,
        failing_component: str,
        error_symptom: str,
        root_cause: str,
        prevention_rule: str
    ):
        """Appends a distilled anti-pattern lesson learned from a self-healing loop."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"### [Anti-Pattern] {failing_component} ({timestamp})\n"
            f"- **Error Symptom**: `{error_symptom}`\n"
            f"- **Root Cause**: {root_cause}\n"
            f"- **Rule to Prevent Recurrence**: {prevention_rule}\n\n"
            "---\n\n"
        )
        with open(self.anti_patterns_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def record_decision(
        self,
        decision_title: str,
        rationale: str,
        affected_modules: List[str]
    ):
        """Appends an architectural invariant or design decision."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mods_str = ", ".join(f"`{m}`" for m in affected_modules)
        entry = (
            f"### [Decision] {decision_title} ({timestamp})\n"
            f"- **Affected Modules**: {mods_str}\n"
            f"- **Rationale**: {rationale}\n\n"
            "---\n\n"
        )
        with open(self.decisions_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def get_memory_context(self, max_chars: int = 4000) -> str:
        """Returns condensed anti-patterns and decisions formatted for system prompt injection."""
        context_parts = []

        if self.anti_patterns_file.exists():
            content = self.anti_patterns_file.read_text(encoding="utf-8", errors="replace")
            # Skip introductory header
            entries = content.split("---")
            if len(entries) > 1:
                recent_anti = "---".join(entries[-4:]).strip()
                if recent_anti:
                    context_parts.append(f"## Learned Project Anti-Patterns (DO NOT REPEAT):\n{recent_anti}")

        if self.decisions_file.exists():
            content = self.decisions_file.read_text(encoding="utf-8", errors="replace")
            entries = content.split("---")
            if len(entries) > 1:
                recent_dec = "---".join(entries[-3:]).strip()
                if recent_dec:
                    context_parts.append(f"## Architectural Invariants & Decisions:\n{recent_dec}")

        combined = "\n\n".join(context_parts)
        return combined[:max_chars]

    def list_anti_patterns(self) -> List[Dict[str, str]]:
        """Parses recorded anti-patterns into structured objects."""
        if not self.anti_patterns_file.exists():
            return []
        content = self.anti_patterns_file.read_text(encoding="utf-8", errors="replace")
        blocks = content.split("### [Anti-Pattern] ")
        results = []
        for block in blocks[1:]:
            lines = block.strip().splitlines()
            comp = lines[0].split("(")[0].strip() if lines else "Unknown"
            symptom = ""
            root_cause = ""
            rule = ""
            for l in lines:
                if "**Error Symptom**:" in l:
                    symptom = l.split("**Error Symptom**:", 1)[1].strip().strip("`")
                elif "**Root Cause**:" in l:
                    root_cause = l.split("**Root Cause**:", 1)[1].strip()
                elif "**Rule to Prevent Recurrence**:" in l:
                    rule = l.split("**Rule to Prevent Recurrence**:", 1)[1].strip()
            results.append({
                "component": comp,
                "title": comp,
                "symptom": symptom,
                "root_cause": root_cause,
                "prevention_rule": rule,
                "rule": rule
            })
        return results

    def get_anti_patterns(self) -> List[Dict[str, str]]:
        """Alias for list_anti_patterns."""
        return self.list_anti_patterns()

    def list_decisions(self) -> List[Dict[str, str]]:
        """Parses recorded architectural decisions into structured objects."""
        if not self.decisions_file.exists():
            return []
        content = self.decisions_file.read_text(encoding="utf-8", errors="replace")
        blocks = content.split("### [Decision] ")
        results = []
        for block in blocks[1:]:
            lines = block.strip().splitlines()
            title = lines[0].split("(")[0].strip() if lines else "Decision"
            affected = ""
            rationale = ""
            for l in lines:
                if "**Affected Modules**:" in l:
                    affected = l.split("**Affected Modules**:", 1)[1].strip()
                elif "**Rationale**:" in l:
                    rationale = l.split("**Rationale**:", 1)[1].strip()
            results.append({
                "title": title,
                "affected_modules": affected,
                "rationale": rationale
            })
        return results

    def get_decisions(self) -> List[Dict[str, str]]:
        """Alias for list_decisions."""
        return self.list_decisions()
