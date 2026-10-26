import os
import glob
import hashlib
from pathlib import Path

dist_dir = Path(r"C:\Users\asus\.gemini\antigravity\scratch\prubeth-autonomous-cli\dist")
lines = []

# Binaries
bin_exe = dist_dir / "bin" / "prubeth" / "prubeth.exe"
if bin_exe.exists():
    h = hashlib.sha256(bin_exe.read_bytes()).hexdigest()
    lines.append(f"{h}  bin/prubeth/prubeth.exe")

for f in sorted(dist_dir.glob("*.*")):
    if f.name == "SHA256SUMS.txt":
        continue
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    lines.append(f"{h}  {f.name}")

out_file = dist_dir / "SHA256SUMS.txt"
out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Generated {out_file} with {len(lines)} release entries:")
for l in lines:
    print(" ", l)
