"""PRUBETH Cryptographic Integrity Engine & Polyglot Quality Linter Matrix.

Exhaustively verifies runtime AST attestation, sandbox traversal defenses,
database WAL integrity, secret scanner patterns, and polyglot code security rules.
"""

from __future__ import annotations

import os
import tempfile
import sqlite3
import json
from pathlib import Path
import pytest

from prubeth.security.integrity import PrubethIntegrityEngine
from prubeth.security.linter import PolyglotQualityLinter, SECRET_PATTERNS, SECURITY_PATTERNS


# ============================================================================
# 1. PrubethIntegrityEngine Attestation Tests
# ============================================================================

def test_integrity_engine_ast_audit_passes():
    """All internal PRUBETH modules must parse cleanly without AST corruption."""
    engine = PrubethIntegrityEngine()
    is_valid, module_count, corrupted = engine.audit_module_ast_integrity()
    assert is_valid is True
    assert module_count > 20
    assert len(corrupted) == 0


def test_integrity_engine_sandbox_jail_blocks_traversal():
    """Adversarial escape vectors must all be blocked by the sandbox validator."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        engine = PrubethIntegrityEngine(workspace_root=ws)
        is_safe, leaks = engine.audit_sandbox_jail_integrity()
        assert is_safe is True
        assert len(leaks) == 0


def test_integrity_engine_database_wal_integrity_check():
    """SQLite WAL PRAGMA integrity_check verifies database health."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        db_dir = ws / ".prubeth"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_file = db_dir / "tasks.db"

        # Create healthy SQLite database
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE test (id INT, name TEXT);")
        conn.commit()
        conn.close()

        engine = PrubethIntegrityEngine(workspace_root=ws)
        ok, detail = engine.audit_database_wal_integrity()
        assert ok is True
        assert "verified" in detail or "ok" in detail.lower()


def test_integrity_engine_attestation_hash_deterministic():
    """Runtime attestation hash must be a 64-character SHA-256 hex string."""
    engine = PrubethIntegrityEngine()
    h1 = engine.compute_runtime_attestation_hash()
    h2 = engine.compute_runtime_attestation_hash()
    assert len(h1) == 64
    assert h1 == h2


def test_integrity_engine_full_attestation_structure():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        engine = PrubethIntegrityEngine(workspace_root=ws)
        report = engine.run_full_attestation()

        assert "all_valid" in report
        assert "attestation_token" in report
        assert "sha256_full" in report
        assert "ast_ok" in report
        assert "sandbox_ok" in report
        assert "settings_ok" in report
        assert "db_ok" in report
        assert len(report["sha256_full"]) == 64
        assert report["attestation_token"].startswith("PRUBETH-INTEGRITY-ATTESTED-")


# ============================================================================
# 2. PolyglotQualityLinter — Secret Scanner Patterns
# ============================================================================

@pytest.mark.parametrize("pattern_name,sample_secret", [
    ("AWS Access Key ID", "AKIAIOSFODNN7EXAMPLE"),
    ("OpenAI / OpenRouter API Key", "sk-1234567890abcdef1234567890abcdef"),
    ("Anthropic API Key", "sk-ant-1234567890abcdef1234567890abcdef"),
    ("GitHub Personal Access Token", "ghp_123456789012345678901234567890123456"),
    ("Private Cryptographic Key", "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0"),
    ("Hardcoded Secret Token", 'api_key = "abcdef1234567890abcdef1234567890"'),
])
def test_linter_detects_all_secret_patterns(pattern_name: str, sample_secret: str):
    """The linter regex patterns must match all canonical secret token formats."""
    matched = False
    for regex_str, name, sev in SECRET_PATTERNS:
        if name == pattern_name:
            import re
            if re.search(regex_str, sample_secret):
                matched = True
            break
    assert matched is True, f"Failed to match pattern '{pattern_name}' with sample '{sample_secret}'"


# ============================================================================
# 3. PolyglotQualityLinter — Vulnerability Anti-Patterns
# ============================================================================

@pytest.mark.parametrize("vuln_name,sample_code,ext", [
    ("Unsafe Subprocess Shell Execution", "subprocess.Popen(['ls'], shell=True)", ".py"),
    ("Dynamic Code Execution (eval/exec)", "result = eval(\"2 + 2\")", ".py"),
    ("Insecure Object Deserialisation", "data = pickle.loads(raw_bytes)", ".py"),
    ("Unsafe HTML Injection (XSS Risk)", "<div dangerouslySetInnerHTML={{ __html: userHtml }} />", ".tsx"),
    ("Potential SQL String Interpolation Injection", "query = f\"SELECT * FROM users WHERE id = {user_id}\"", ".py"),
])
def test_linter_detects_vulnerability_patterns(vuln_name: str, sample_code: str, ext: str):
    matched = False
    for regex_str, name, sev, applicable_exts in SECURITY_PATTERNS:
        if name == vuln_name:
            import re
            if ext in applicable_exts.split(",") and re.search(regex_str, sample_code):
                matched = True
            break
    assert matched is True, f"Failed to detect vulnerability '{vuln_name}' in code: {sample_code}"


# ============================================================================
# 4. PolyglotQualityLinter — Workspace Scan Clean vs Contaminated
# ============================================================================

def test_linter_clean_workspace_zero_issues():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        (ws / "src").mkdir()
        (ws / "src" / "app.py").write_text("def hello(name: str) -> str:\n    return f'Hello, {name}!'\n", encoding="utf-8")

        linter = PolyglotQualityLinter(workspace_root=ws)
        issues = linter.audit_workspace(include_tests=False)
        assert len(issues) == 0


def test_linter_contaminated_workspace_flags_issues():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        (ws / "src").mkdir()
        (ws / "src" / "vuln.py").write_text(
            "import os\n"
            "api_key = 'abcdef1234567890abcdef1234567890'\n"
            "eval(\"print(1)\")\n",
            encoding="utf-8"
        )

        linter = PolyglotQualityLinter(workspace_root=ws)
        issues = linter.audit_workspace(include_tests=False)
        assert len(issues) >= 2
        rules = [i["rule"] for i in issues]
        assert any("Secret" in r or "Token" in r for r in rules)
        assert any("Dynamic" in r or "eval" in r.lower() for r in rules)
