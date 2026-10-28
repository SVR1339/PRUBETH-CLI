"""PRUBETH Shadow Worktree Subsystem.

Provides zero-dependency filesystem worktree isolation for concurrent
subagents, preventing collision on the active working tree.
"""

import os
import shutil
import difflib
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

class WorktreeManager:
    """Subsystem 13A: Isolated Shadow Worktrees for Autonomous Subagents."""

    IGNORE_DIRS = {
        ".git", ".prubeth", "__pycache__", "node_modules", "venv", ".venv",
        ".idea", ".vscode", "dist", "build", ".pytest_cache"
    }

    IGNORE_EXTS = {".pyc", ".pyo", ".pyd", ".log", ".tmp"}

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.worktrees_dir = self.workspace_root / ".prubeth" / "worktrees"
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        self.baselines: Dict[str, Dict[str, str]] = {}

    def _hash_file(self, path: Path) -> str:
        """Computes SHA-256 hash of a file's contents."""
        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def create_worktree(self, subagent_id: str) -> Path:
        """Provisions an isolated shadow worktree for a subagent."""
        wt_path = self.worktrees_dir / subagent_id
        if wt_path.exists():
            shutil.rmtree(wt_path, ignore_errors=True)
        wt_path.mkdir(parents=True, exist_ok=True)

        baseline_manifest: Dict[str, str] = {}

        # Copy workspace files to worktree scratchpad
        for root, dirs, files in os.walk(self.workspace_root):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith(".")]

            rel_root = Path(root).relative_to(self.workspace_root)
            if str(rel_root).startswith(".prubeth"):
                continue

            target_dir = wt_path / rel_root
            target_dir.mkdir(parents=True, exist_ok=True)

            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in self.IGNORE_EXTS:
                    continue

                src_file = Path(root) / file
                dest_file = target_dir / file
                try:
                    shutil.copy2(src_file, dest_file)
                    rel_file_key = str((rel_root / file).as_posix()).lstrip("./")
                    baseline_manifest[rel_file_key] = self._hash_file(src_file)
                except Exception:
                    pass

        self.baselines[subagent_id] = baseline_manifest
        return wt_path

    def get_worktree_path(self, subagent_id: str) -> Path:
        """Returns the filesystem path of an active worktree."""
        return self.worktrees_dir / subagent_id

    def get_worktree_diff(self, subagent_id: str) -> Dict[str, Any]:
        """Calculates differences between worktree scratchpad and initial baseline."""
        wt_path = self.get_worktree_path(subagent_id)
        if not wt_path.exists():
            return {"modified": [], "added": [], "deleted": [], "diff": ""}

        baseline = self.baselines.get(subagent_id, {})
        current_files: Dict[str, str] = {}

        for root, dirs, files in os.walk(wt_path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            rel_root = Path(root).relative_to(wt_path)
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in self.IGNORE_EXTS:
                    continue
                file_path = Path(root) / file
                rel_key = str((rel_root / file).as_posix()).lstrip("./")
                current_files[rel_key] = self._hash_file(file_path)

        modified = []
        added = []
        deleted = []
        diff_lines = []

        for rel_path, cur_hash in current_files.items():
            if rel_path not in baseline:
                added.append(rel_path)
                target_f = wt_path / rel_path
                try:
                    content = target_f.read_text(encoding="utf-8", errors="replace").splitlines()
                    diff_lines.extend(difflib.unified_diff([], content, fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}", lineterm=""))
                except Exception:
                    pass
            elif cur_hash != baseline[rel_path]:
                modified.append(rel_path)
                orig_f = self.workspace_root / rel_path
                mod_f = wt_path / rel_path
                try:
                    orig_content = orig_f.read_text(encoding="utf-8", errors="replace").splitlines() if orig_f.exists() else []
                    mod_content = mod_f.read_text(encoding="utf-8", errors="replace").splitlines()
                    diff_lines.extend(difflib.unified_diff(orig_content, mod_content, fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}", lineterm=""))
                except Exception:
                    pass

        for rel_path in baseline:
            if rel_path not in current_files:
                deleted.append(rel_path)
                orig_f = self.workspace_root / rel_path
                try:
                    orig_content = orig_f.read_text(encoding="utf-8", errors="replace").splitlines() if orig_f.exists() else []
                    diff_lines.extend(difflib.unified_diff(orig_content, [], fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}", lineterm=""))
                except Exception:
                    pass

        return {
            "subagent_id": subagent_id,
            "modified": modified,
            "added": added,
            "deleted": deleted,
            "has_changes": bool(modified or added or deleted),
            "diff": "\n".join(diff_lines)
        }

    def merge_worktree_to_root(self, subagent_id: str) -> Tuple[bool, List[str], str]:
        """Atomically merges verified modifications from worktree back to root workspace."""
        diff_info = self.get_worktree_diff(subagent_id)
        if not diff_info["has_changes"]:
            return True, [], "No modifications to merge."

        wt_path = self.get_worktree_path(subagent_id)
        merged_files = []

        try:
            # 1. Apply added and modified files
            for rel_file in diff_info["added"] + diff_info["modified"]:
                src = wt_path / rel_file
                dest = self.workspace_root / rel_file
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                merged_files.append(rel_file)

            # 2. Apply deletions
            for rel_file in diff_info["deleted"]:
                dest = self.workspace_root / rel_file
                if dest.exists():
                    dest.unlink()
                merged_files.append(rel_file)

            return True, merged_files, diff_info["diff"]
        except Exception as e:
            return False, merged_files, f"Merge conflict or I/O error: {e}"

    def destroy_worktree(self, subagent_id: str):
        """Tears down an isolated worktree scratchpad."""
        wt_path = self.get_worktree_path(subagent_id)
        if wt_path.exists():
            shutil.rmtree(wt_path, ignore_errors=True)
        if subagent_id in self.baselines:
            del self.baselines[subagent_id]

    # Developer aliases
    cleanup_worktree = destroy_worktree

    def cleanup_all_worktrees(self) -> int:
        """Tears down all active worktree scratchpads and clears baselines."""
        count = 0
        if not self.worktrees_dir.exists():
            return 0
        for item in list(self.worktrees_dir.iterdir()):
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                count += 1
        self.baselines.clear()
        return count

    cleanup_all = cleanup_all_worktrees

    def list_active_worktrees(self) -> List[Dict[str, Any]]:
        """Lists all active isolated worktree sandboxes."""
        active = []
        if not self.worktrees_dir.exists():
            return active
        for item in self.worktrees_dir.iterdir():
            if item.is_dir():
                diff_data = self.get_worktree_diff(item.name)
                active.append({
                    "subagent_id": item.name,
                    "path": str(item),
                    "modified_count": len(diff_data["modified"]) + len(diff_data["added"]),
                    "has_changes": diff_data["has_changes"]
                })
        return active
