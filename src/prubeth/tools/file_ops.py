"""PRUBETH Precision File Mutation & Surgical Patching Micro-Algorithms.

Implements crash-safe atomic file replacement, line-ending invariant preservation,
and fuzzy whitespace-tolerant patch replacement.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Tuple, Optional


def detect_line_ending(text: str) -> str:
    """Detects predominant line ending ('\\r\\n' vs '\\n') in content."""
    crlf_count = text.count("\r\n")
    lf_count = text.count("\n") - crlf_count
    return "\r\n" if crlf_count > lf_count else "\n"


def atomic_write_file(path: Union[str, Path], content: str, encoding: str = "utf-8") -> None:
    """Writes content to target path atomically with zero possibility of partial file corruption.
    
    1. Writes to temporary sibling file in same directory.
    2. Calls fsync to ensure data is physically committed to disk.
    3. Executes atomic os.replace() which replaces the target inode atomically.
    """
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Use sibling temp file to guarantee same filesystem/partition for atomic rename
    tmp_path = target.parent / f".{target.name}.prubeth_tmp_{uuid.uuid4().hex[:8]}"

    # Normalize line endings to match file conventions if file exists
    if target.exists():
        try:
            sample = target.read_text(encoding=encoding, errors="ignore")[:4096]
            le = detect_line_ending(sample)
            if le == "\r\n":
                content = content.replace("\r\n", "\n").replace("\n", "\r\n")
        except Exception:
            pass

    try:
        with open(tmp_path, "w", encoding=encoding, errors="replace") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        # Atomic replacement (POSIX rename / Windows MoveFileEx with replace)
        os.replace(str(tmp_path), str(target))
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise


def fuzzy_replace_text(source: str, target: str, replacement: str) -> Tuple[bool, str, str]:
    """Surgically replaces target in source with tolerance for minor whitespace/indentation shifts.
    
    Returns:
        (success: bool, modified_content: str, message: str)
    """
    if target in source:
        # Exact match
        return True, source.replace(target, replacement, 1), "Exact match replaced."

    # 1. Normalize line endings
    norm_source = source.replace("\r\n", "\n")
    norm_target = target.replace("\r\n", "\n")
    norm_repl = replacement.replace("\r\n", "\n")

    if norm_target in norm_source:
        res = norm_source.replace(norm_target, norm_repl, 1)
        orig_le = detect_line_ending(source)
        if orig_le == "\r\n":
            res = res.replace("\n", "\r\n")
        return True, res, "Line-ending normalized match replaced."

    # 2. Whitespace-insensitive block matcher
    source_lines = norm_source.splitlines()
    target_lines = norm_target.splitlines()

    if not target_lines:
        return False, source, "Empty target."

    # Strip whitespace from target lines to create match signature
    target_sig = [l.strip() for l in target_lines if l.strip()]
    if not target_sig:
        return False, source, "Target contains only whitespace."

    # Slide over source lines to find matching block signature
    sig_len = len(target_sig)
    for i in range(len(source_lines) - len(target_lines) + 1):
        window = [source_lines[i + j].strip() for j in range(len(target_lines))]
        window_sig = [l for l in window if l]

        if window_sig == target_sig:
            # Found matching block! Detect indentation of first line
            orig_indent = ""
            m = re.match(r"^(\s*)", source_lines[i])
            if m:
                orig_indent = m.group(1)

            # Re-indent replacement to match original indentation
            repl_lines = norm_repl.splitlines()
            target_indent = ""
            m_t = re.match(r"^(\s*)", target_lines[0])
            if m_t:
                target_indent = m_t.group(1)

            adjusted_repl = []
            for r_line in repl_lines:
                if r_line.startswith(target_indent):
                    adjusted_repl.append(orig_indent + r_line[len(target_indent):])
                else:
                    adjusted_repl.append(orig_indent + r_line.lstrip())

            # Splice lines
            new_lines = source_lines[:i] + adjusted_repl + source_lines[i + len(target_lines):]
            res = "\n".join(new_lines)
            if detect_line_ending(source) == "\r\n":
                res = res.replace("\n", "\r\n")
            return True, res, "Fuzzy indentation-tolerant match replaced."

    return False, source, "Target block could not be located in file."
