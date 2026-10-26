"""PRUBETH Intelligent Context Expander & @mention Resolver.

Parses inline @file, @symbol, @search, @diff, and @dir tags in developer prompts,
extracts and formats code slices with line numbers and token guards, and injects
them seamlessly into the LLM context window.
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional

from prubeth.repository.index import CodebaseIndex

class ContextExpander:
    """Interprets @mentions in prompts and resolves code slices."""

    def __init__(self, workspace_root: Optional[Path] = None, index: Optional[CodebaseIndex] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.index = index or CodebaseIndex(self.workspace_root)

    def resolve_mentions(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Scans prompt text for @mentions, resolves them, and appends code attachments.
        
        Supported patterns:
          - @file/path.py or @src/auth.py:10-50
          - @file:src/auth.py
          - @symbol:MyClass or @sym:my_function
          - @search:query
          - @diff or @git:diff
          - @tree or @dir:src
        """
        attachments: List[Dict[str, Any]] = []
        cleaned_prompt = text

        # 1. Match @diff
        if "@diff" in text or "@git:diff" in text:
            cleaned_prompt = cleaned_prompt.replace("@git:diff", "").replace("@diff", "").strip()
            from prubeth.persistence.checkpoints import SnapshotManager
            snap_mgr = SnapshotManager(workspace_root=self.workspace_root)
            diff_text = snap_mgr.compute_snapshot_diff() or "No uncommitted changes in working tree."
            attachments.append({
                "type": "diff",
                "label": "Working Tree Diff",
                "content": f"```diff\n{diff_text[:4000]}\n```"
            })

        # 2. Match @git or @git:status (Claude Code Parity)
        if "@git:status" in cleaned_prompt or "@git" in cleaned_prompt:
            cleaned_prompt = cleaned_prompt.replace("@git:status", "").replace("@git", "").strip()
            git_info = []
            try:
                import subprocess
                res_b = subprocess.run(["git", "branch", "--show-current"], cwd=str(self.workspace_root), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2)
                branch = res_b.stdout.strip() if res_b.returncode == 0 else ""
                res_s = subprocess.run(["git", "status", "--short"], cwd=str(self.workspace_root), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2)
                status_out = res_s.stdout.strip() if res_s.returncode == 0 else ""
                if branch or status_out:
                    git_info.append(f"Branch: {branch or 'HEAD'}")
                    git_info.append(f"Working Tree Status:\n{status_out or 'Clean'}")
            except Exception:
                pass
            if not git_info:
                from prubeth.persistence.checkpoints import SnapshotManager
                snap_mgr = SnapshotManager(workspace_root=self.workspace_root)
                history = snap_mgr.list_snapshots()
                git_info.append("Version Control: Pure Filesystem Snapshots (Git not detected)")
                git_info.append(f"Recorded Checkpoints: {len(history)}")
            attachments.append({
                "type": "git",
                "label": "Git Repository & Working Tree Status",
                "content": "```\n" + "\n".join(git_info) + "\n```"
            })

        # 3. Match @search:query
        search_matches = re.findall(r"@search:([A-Za-z0-9_\-\s]+)", cleaned_prompt)
        for q in search_matches:
            cleaned_prompt = cleaned_prompt.replace(f"@search:{q}", "").strip()
            results = self.index.search(q.strip(), top_k=3)
            if results:
                content_parts = []
                for r in results:
                    content_parts.append(
                        f"### {r.file_path} (Lines {r.start_line}-{r.end_line}, score: {r.score})\n"
                        f"```\n{r.snippet}\n```"
                    )
                attachments.append({
                    "type": "search",
                    "label": f"Search Results for '{q.strip()}'",
                    "content": "\n\n".join(content_parts)
                })

        # 3. Match @symbol:Name or @sym:Name
        sym_matches = re.findall(r"@(?:symbol|sym):([A-Za-z0-9_\.\:]+)", cleaned_prompt)
        for sym_name in sym_matches:
            cleaned_prompt = cleaned_prompt.replace(f"@symbol:{sym_name}", "").replace(f"@sym:{sym_name}", "").strip()
            sym = self.index.resolve_symbol(sym_name)
            if sym:
                attachments.append({
                    "type": "symbol",
                    "label": f"Symbol Definition: {sym.signature} ({sym.file_path}:{sym.start_line})",
                    "content": f"```\n# {sym.file_path}:{sym.start_line}-{sym.end_line}\n{sym.body_snippet}\n```"
                })

        # 4. Match @file:path or @path/file.ext[:start-end]
        # Match explicit @file:foo.py
        file_explicit = re.findall(r"@file:([A-Za-z0-9_\-\.\/\\]+(?::\d+-\d+)?)", cleaned_prompt)
        for f in file_explicit:
            cleaned_prompt = cleaned_prompt.replace(f"@file:{f}", "").strip()
            att = self._read_file_mention(f)
            if att:
                attachments.append(att)

        # Match inline file paths like @src/prubeth/cli/main.py or @tests/test_harness.py:10-50
        path_matches = re.findall(r"@((?:[A-Za-z0-9_\-]+[\\/])+[A-Za-z0-9_\-\.]+\.[a-zA-Z0-9]+(?::\d+-\d+)?)", cleaned_prompt)
        for f in path_matches:
            cleaned_prompt = cleaned_prompt.replace(f"@{f}", "").strip()
            att = self._read_file_mention(f)
            if att:
                attachments.append(att)

        # Match standalone file names like @main.py or @README.md
        standalone = re.findall(r"@([A-Za-z0-9_\-]+\.(?:py|json|md|toml|yaml|yml|ts|js|go|rs|txt|html)(?::\d+-\d+)?)", cleaned_prompt)
        for f in standalone:
            cleaned_prompt = cleaned_prompt.replace(f"@{f}", "").strip()
            att = self._read_file_mention(f)
            if att:
                attachments.append(att)

        # Assemble full expanded text
        if not attachments:
            return text, []

        expanded_parts = [cleaned_prompt.strip() or "Inspect and execute based on attached context:"]
        expanded_parts.append("\n\n--- [PRUBETH Attached Context & Code Slices] ---")
        for att in attachments:
            expanded_parts.append(f"\n#### [{att['type'].upper()}] {att['label']}\n{att['content']}")
        expanded_parts.append("------------------------------------------------\n")

        return "\n".join(expanded_parts), attachments

    def _read_file_mention(self, mention_str: str) -> Optional[Dict[str, Any]]:
        """Safely reads file contents with optional line slice (e.g. auth.py:10-30)."""
        line_slice = None
        file_path_str = mention_str
        if ":" in mention_str:
            parts = mention_str.split(":", 1)
            file_path_str = parts[0]
            slice_parts = parts[1].split("-")
            if len(slice_parts) == 2 and slice_parts[0].isdigit() and slice_parts[1].isdigit():
                line_slice = (int(slice_parts[0]), int(slice_parts[1]))

        target_file = (self.workspace_root / file_path_str).resolve()
        if not target_file.is_file():
            # Try searching relative to root
            candidates = list(self.workspace_root.glob(f"**/{file_path_str}"))
            if candidates:
                target_file = candidates[0]
            else:
                return None

        try:
            rel_path = target_file.relative_to(self.workspace_root).as_posix()
            lines = target_file.read_text(encoding="utf-8", errors="replace").splitlines()
            
            start_l = 1
            end_l = len(lines)
            if line_slice:
                start_l = max(1, line_slice[0])
                end_l = min(len(lines), line_slice[1])
                sliced_lines = lines[start_l - 1 : end_l]
            else:
                # Limit full file to max 400 lines
                if len(lines) > 400:
                    sliced_lines = lines[:400] + [f"\n... [Truncated {len(lines) - 400} additional lines] ..."]
                else:
                    sliced_lines = lines

            formatted_snippet = "\n".join(
                f"{i + start_l:4d} | {line}" for i, line in enumerate(sliced_lines)
            )

            return {
                "type": "file",
                "label": f"{rel_path}:{start_l}-{end_l}",
                "file_path": rel_path,
                "content": f"```{target_file.suffix.lstrip('.') or 'text'}\n{formatted_snippet}\n```"
            }
        except Exception:
            return None
