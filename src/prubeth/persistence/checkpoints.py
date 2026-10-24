import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

class SnapshotManager:
    """Universal Workspace Snapshot and Rollback Engine.
    
    Provides deterministic workspace state preservation and instant rollback,
    operating with pure filesystem snapshots even when Git is absent.
    """

    def __init__(self, workspace_root: Optional[Path] = None, task_id: str = "default"):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.task_id = task_id
        self.snapshots_dir = self.workspace_root / ".prubeth" / "snapshots" / self.task_id
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.ignored_dirs = {".git", ".prubeth", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}

    def create_snapshot(self, label: str) -> str:
        """Captures a shadow copy of all relevant workspace files."""
        snapshot_path = self.snapshots_dir / label
        if snapshot_path.exists():
            shutil.rmtree(snapshot_path)
        snapshot_path.mkdir(parents=True, exist_ok=True)

        copied_count = 0
        manifest = []
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            for file in files:
                src_file = Path(root) / file
                rel_path = src_file.relative_to(self.workspace_root)
                dst_file = snapshot_path / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                manifest.append(str(rel_path).replace("\\", "/"))
                copied_count += 1

        # Write manifest of files in snapshot
        with open(snapshot_path / ".manifest.json", "w", encoding="utf-8") as f:
            import json
            json.dump({"timestamp": datetime.now().isoformat(), "files": manifest}, f, indent=2)

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
        return [d.name for d in self.snapshots_dir.iterdir() if d.is_dir()]
