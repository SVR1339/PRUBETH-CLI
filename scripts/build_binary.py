"""PRUBETH Standalone Executable Packaging Script (Subsystem 18).

Compiles PRUBETH into a single-file, zero-dependency native executable (prubeth.exe / prubeth).
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

def build_standalone_binary():
    """Compiles PRUBETH CLI into a native standalone executable."""
    root_dir = Path(__file__).resolve().parent.parent
    entry_point = root_dir / "src" / "prubeth" / "cli" / "main.py"
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"

    print(f"Building PRUBETH Standalone Native Binary...")
    print(f"Entry point: {entry_point}")
    print(f"Target OS: {sys.platform}")

    # Check for pyinstaller
    pyinstaller_cmd = shutil.which("pyinstaller")
    if not pyinstaller_cmd:
        print("[WARN] PyInstaller is not installed in the current environment.")
        print("To compile the single-file binary, run: pip install pyinstaller")
        print("Then execute: python scripts/build_binary.py")
        return False

    cmd = [
        pyinstaller_cmd,
        "--onefile",
        "--name", "prubeth",
        "--clean",
        "--paths", str(root_dir / "src"),
        str(entry_point)
    ]

    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(root_dir))
    if res.returncode == 0:
        exe_name = "prubeth.exe" if sys.platform.startswith("win") else "prubeth"
        output_binary = dist_dir / exe_name
        print(f"\n[SUCCESS] Compiled standalone binary at: {output_binary}")
        return True
    else:
        print(f"\n[FAILED] Compilation exited with code {res.returncode}")
        return False

if __name__ == "__main__":
    build_standalone_binary()
