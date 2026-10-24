import os
import sys
import tarfile
import hashlib
from pathlib import Path

def create_source_distribution(project_root: Path, dist_dir: Path, version: str = "1.0.0"):
    """Creates a standard sdist prubeth-1.0.0.tar.gz archive."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    tar_path = dist_dir / f"prubeth-{version}.tar.gz"
    
    included_files = [
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "NOTICE",
        "SECURITY.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md"
    ]
    
    with tarfile.open(tar_path, "w:gz") as tar:
        for fname in included_files:
            fpath = project_root / fname
            if fpath.exists():
                tar.add(fpath, arcname=f"prubeth-{version}/{fname}")
        
        src_dir = project_root / "src"
        if src_dir.exists():
            for root, _, files in os.walk(src_dir):
                for f in files:
                    if not f.endswith((".pyc", ".pyo")):
                        full_p = Path(root) / f
                        rel_p = full_p.relative_to(project_root)
                        tar.add(full_p, arcname=f"prubeth-{version}/{rel_p}")
    
    print(f"Created sdist: {tar_path} ({tar_path.stat().st_size} bytes)")
    return tar_path

def generate_checksums(dist_dir: Path):
    """Generates standard SHA256SUMS.txt for all files in dist/."""
    checksums = []
    for item in sorted(dist_dir.iterdir()):
        if item.is_file() and item.name != "SHA256SUMS.txt":
            sha256 = hashlib.sha256()
            with open(item, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
            digest = sha256.hexdigest()
            checksums.append(f"{digest}  {item.name}")
            print(f"{digest}  {item.name} ({item.stat().st_size} bytes)")
            
    sums_file = dist_dir / "SHA256SUMS.txt"
    sums_file.write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(f"\nWritten official checksums to: {sums_file}")

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    dist = root / "dist"
    create_source_distribution(root, dist)
    generate_checksums(dist)
