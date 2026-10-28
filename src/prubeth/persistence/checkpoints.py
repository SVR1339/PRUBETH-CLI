import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

class SnapshotManager:
    """Universal Workspace Snapshot and Rollback Engine.
    
    Provides deterministic workspace state preservation and instant rollback,
    operating with pure filesystem snapshots even when Git is absent.
    """

    def __init__(self, workspace_root: Optional[Path] = None, task_id: str = "default"):
        raw_root = (workspace_root or Path.cwd()).resolve()
        
        # Guard against running directly in Windows OS System directories (e.g. C:\Windows\System32)
        if os.name == "nt":
            win_root = os.environ.get("SystemRoot", "C:\\Windows").lower()
            if str(raw_root).lower().startswith(win_root):
                safe_dir = Path.home() / "prubeth-workspace"
                safe_dir.mkdir(parents=True, exist_ok=True)
                raw_root = safe_dir

        self.workspace_root = raw_root
        self.task_id = task_id
        try:
            self.snapshots_dir = self.workspace_root / ".prubeth" / "snapshots" / self.task_id
            self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            self.snapshots_dir = Path.home() / ".prubeth" / "snapshots" / self.task_id
            self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        self.ignored_dirs = {
            ".git", ".prubeth", "__pycache__", "node_modules", ".venv", "venv",
            ".pytest_cache", "dist", "build", "prubeth.egg-info", ".mypy_cache",
            "system32", "syswow64", "winsxs", "servicing", "drivers"
        }
        self.ignored_extensions = {
            ".dll", ".sys", ".exe", ".ocx", ".drv", ".mui", ".pdb", ".bin", ".dat"
        }

    def create_snapshot(self, label: str) -> str:
        """Captures a shadow copy of all relevant workspace files."""
        snapshot_path = self.snapshots_dir / label
        if snapshot_path.exists():
            try:
                shutil.rmtree(snapshot_path, ignore_errors=True)
            except Exception:
                pass
        try:
            snapshot_path.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            return f"Snapshot '{label}' skipped (write permission restricted)."

        copied_count = 0
        manifest = []
        try:
            for root, dirs, files in os.walk(self.workspace_root):
                dirs[:] = [d for d in dirs if d.lower() not in self.ignored_dirs]
                for file in files:
                    src_file = Path(root) / file
                    if src_file.suffix.lower() in self.ignored_extensions:
                        continue
                    try:
                        # Skip oversized binary files (> 10MB)
                        if src_file.stat().st_size > 10 * 1024 * 1024:
                            continue
                        rel_path = src_file.relative_to(self.workspace_root)
                        dst_file = snapshot_path / rel_path
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, dst_file)
                        manifest.append(str(rel_path).replace("\\", "/"))
                        copied_count += 1
                    except (PermissionError, OSError, ValueError):
                        continue
        except (PermissionError, OSError):
            pass

        # Write manifest of files in snapshot
        try:
            with open(snapshot_path / ".manifest.json", "w", encoding="utf-8") as f:
                import json
                json.dump({"timestamp": datetime.now().isoformat(), "files": manifest}, f, indent=2)
        except Exception:
            pass

        return f"Snapshot '{label}' created ({copied_count} files preserved)."

    def rollback_to_snapshot(self, label: str) -> bool:
        """Reverts workspace exactly to the labeled snapshot state."""
        snapshot_path = self.snapshots_dir / label
        if not snapshot_path.exists():
            return False

        manifest_file = snapshot_path / ".manifest.json"
        if not manifest_file.exists():
            return False

        import json
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        snapshot_files = set(manifest_data.get("files", []))

        # 1. Remove any files currently in workspace that were created AFTER snapshot
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            for file in files:
                current_file = Path(root) / file
                rel = current_file.relative_to(self.workspace_root).as_posix()
                if rel not in snapshot_files:
                    try:
                        current_file.unlink()
                    except Exception:
                        pass

        # 2. Restore files from snapshot
        for rel in snapshot_files:
            src = snapshot_path / rel
            dst = self.workspace_root / rel
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        return True

    def list_snapshots(self) -> List[str]:
        """Lists available snapshots for this task."""
        if not self.snapshots_dir.exists():
            return []
        return sorted([d.name for d in self.snapshots_dir.iterdir() if d.is_dir()])

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Returns structured metadata timeline for all checkpoints in chronological order."""
        import json
        timeline = []
        if not self.snapshots_dir.exists():
            return []

        for d in sorted(self.snapshots_dir.iterdir()):
            if d.is_dir():
                manifest_file = d / ".manifest.json"
                ts = ""
                files_count = 0
                if manifest_file.exists():
                    try:
                        data = json.loads(manifest_file.read_text(encoding="utf-8"))
                        ts = data.get("timestamp", "")
                        files_count = len(data.get("files", []))
                    except Exception:
                        pass
                timeline.append({
                    "label": d.name,
                    "timestamp": ts or datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
                    "files_count": files_count,
                    "path": str(d)
                })
        return timeline

    def compute_snapshot_diff(self, label: Optional[str] = None) -> str:
        """Computes a pure-Python unified diff against a snapshot without needing Git."""
        import difflib
        snapshots = self.list_snapshots()
        if not snapshots:
            return ""
        target_label = label or snapshots[-1]
        snapshot_path = self.snapshots_dir / target_label
        if not snapshot_path.exists():
            return ""

        diff_chunks = []
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            for file in files:
                current_file = Path(root) / file
                rel = current_file.relative_to(self.workspace_root).as_posix()
                snap_file = snapshot_path / rel

                cur_text = current_file.read_text(encoding="utf-8", errors="ignore") if current_file.is_file() else ""
                snap_text = snap_file.read_text(encoding="utf-8", errors="ignore") if snap_file.is_file() else ""

                if cur_text != snap_text:
                    orig_lines = snap_text.splitlines(keepends=True)
                    new_lines = cur_text.splitlines(keepends=True)
                    diff = list(difflib.unified_diff(
                        orig_lines,
                        new_lines,
                        fromfile=f"a/{rel}",
                        tofile=f"b/{rel}",
                        lineterm=""
                    ))
                    if diff:
                        diff_chunks.append("\n".join(diff))

        return "\n\n".join(diff_chunks)

    def delete_snapshot(self, label: str) -> bool:
        """Deletes an individual snapshot by label."""
        snapshot_path = self.snapshots_dir / label
        if snapshot_path.exists() and snapshot_path.is_dir():
            try:
                shutil.rmtree(snapshot_path, ignore_errors=True)
                return True
            except Exception:
                return False
        return False

    def clear_all_snapshots(self) -> int:
        """Removes all snapshots for this task, returning the count of cleared snapshots."""
        count = 0
        if self.snapshots_dir.exists():
            for item in list(self.snapshots_dir.iterdir()):
                if item.is_dir():
                    try:
                        shutil.rmtree(item, ignore_errors=True)
                        count += 1
                    except Exception:
                        pass
        return count
