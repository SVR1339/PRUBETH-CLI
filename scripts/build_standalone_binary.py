"""PRUBETH Native Standalone Binary Compiler.

Builds native single-file binaries (e.g. prubeth.exe on Windows, prubeth on Linux/macOS)
and universal standalone zipapps (prubeth.pyz) for zero-dependency execution.
"""

import os
import sys
import shutil
import zipapp
import hashlib
import subprocess
from pathlib import Path

def generate_zipapp(project_root: Path, output_file: Path):
    """Packages PRUBETH into a universal, standalone executable zipapp (.pyz)."""
    build_staging = project_root / "build" / "zipapp_staging"
    if build_staging.exists():
        shutil.rmtree(build_staging)
    build_staging.mkdir(parents=True, exist_ok=True)

    # 1. Copy src/prubeth
    src_prubeth = project_root / "src" / "prubeth"
    shutil.copytree(src_prubeth, build_staging / "prubeth")

    # 2. Copy site-packages dependencies (rich, etc.)
    import rich
    rich_dir = Path(rich.__file__).parent
    shutil.copytree(rich_dir, build_staging / "rich")

    # 3. Create __main__.py entry point
    main_py = build_staging / "__main__.py"
    main_py.write_text(
        "import sys\n"
        "from prubeth.cli.main import main\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8"
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    zipapp.create_archive(
        source=build_staging,
        target=output_file,
        interpreter="/usr/bin/env python3" if sys.platform != "win32" else None,
        main=None,
        compressed=True
    )
    shutil.rmtree(build_staging, ignore_errors=True)
    print(f"Created Standalone Universal ZipApp: {output_file} ({output_file.stat().st_size} bytes)")
    return output_file

def compile_pyinstaller_binary(project_root: Path, dist_bin_dir: Path):
    """Compiles standalone native binary distribution (prubeth/prubeth.exe)."""
    entry_point = project_root / "src" / "prubeth" / "cli" / "main.py"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--name", "prubeth",
        "--clean",
        "--noconfirm",
        "--distpath", str(dist_bin_dir),
        "--workpath", str(project_root / "build" / "pyinstaller"),
        "--specpath", str(project_root / "build"),
        "--paths", str(project_root / "src"),
        str(entry_point)
    ]
    print(f"Executing PyInstaller onedir compilation: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(project_root))
    if res.returncode == 0:
        bin_name = "prubeth.exe" if sys.platform == "win32" else "prubeth"
        target_bin = dist_bin_dir / "prubeth" / bin_name
        if target_bin.exists():
            print(f"Compiled Standalone Native Binary: {target_bin} ({target_bin.stat().st_size} bytes)")
            archive_target = dist_bin_dir.parent / "prubeth-windows-x64"
            shutil.make_archive(str(archive_target), "zip", root_dir=dist_bin_dir / "prubeth")
            print(f"Created Standalone Release Archive: {archive_target}.zip")
            return target_bin
    print("PyInstaller build warning: compilation did not complete cleanly.")
    return None

def update_checksums(dist_dir: Path):
    """Appends all binaries and artifacts to SHA256SUMS.txt."""
    sums_file = dist_dir / "SHA256SUMS.txt"
    entries = {}
    if sums_file.exists():
        for line in sums_file.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                entries[parts[1]] = parts[0]

    for root, _, files in os.walk(dist_dir):
        for f in files:
            if f == "SHA256SUMS.txt":
                continue
            fpath = Path(root) / f
            rel = fpath.relative_to(dist_dir).as_posix()
            sha = hashlib.sha256()
            with open(fpath, "rb") as fp:
                while chunk := fp.read(65536):
                    sha.update(chunk)
            entries[rel] = sha.hexdigest()

    lines = [f"{h}  {fn}" for fn, h in sorted(entries.items())]
    sums_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {sums_file} with {len(lines)} verified release artifacts.")

def main():
    project_root = Path(__file__).resolve().parent.parent
    dist_dir = project_root / "dist"
    dist_bin = dist_dir / "bin"
    dist_bin.mkdir(parents=True, exist_ok=True)

    # 1. Build Universal ZipApp (.pyz)
    zipapp_target = dist_dir / "prubeth.pyz"
    generate_zipapp(project_root, zipapp_target)

    # 2. Build Native Standalone Binary
    compile_pyinstaller_binary(project_root, dist_bin)

    # 3. Update Checksums
    update_checksums(dist_dir)

if __name__ == "__main__":
    main()
