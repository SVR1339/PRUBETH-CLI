"""PRUBETH Test-Time Self-Verification & AST Contract Matrix Tests.

Exhaustively verifies TestTimeVerifier: pre-flight AST syntax gates, Python
interface signature compatibility checking, backward breaking-change detection,
and visual AST diff analysis.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.runtime.verification import TestTimeVerifier


# ============================================================================
# 1. Clean Backward-Compatible Patch Safety
# ============================================================================

def test_verify_patch_safety_clean_python(tmp_path: Path):
    verifier = TestTimeVerifier(workspace_root=tmp_path)

    old_code = "def compute(a: int, b: int) -> int:\n    return a + b\n"
    new_code = "def compute(a: int, b: int, debug: bool = False) -> int:\n    if debug: print(a, b)\n    return a + b\n"

    ok, msg = verifier.verify_patch_safety("src/math.py", old_code, new_code)
    assert ok is True
    assert "passed" in msg.lower()


def test_verify_patch_safety_syntax_error_rejected(tmp_path: Path):
    verifier = TestTimeVerifier(workspace_root=tmp_path)

    old_code = "def compute(a: int) -> int:\n    return a\n"
    broken_code = "def compute(a: int:\n    return a\n"

    ok, msg = verifier.verify_patch_safety("src/math.py", old_code, broken_code)
    assert ok is False
    assert "Syntax Verification Failure" in msg or "SyntaxError" in msg


# ============================================================================
# 2. Breaking Contract Change Detection
# ============================================================================

def test_verify_patch_safety_detects_removed_required_arg(tmp_path: Path):
    verifier = TestTimeVerifier(workspace_root=tmp_path)

    old_code = "def query(user_id: str, limit: int = 10):\n    pass\n"
    # New signature drops an existing parameter (breaking contract)
    breaking_code = "def query(limit: int = 10):\n    pass\n"

    ok, msg = verifier.verify_patch_safety("src/db.py", old_code, breaking_code)
    assert ok is False
    assert "Contract Verification Failure" in msg
    assert "dropped parameters" in msg


# ============================================================================
# 3. Non-Python Polyglot File Safety
# ============================================================================

def test_verify_patch_safety_clean_json(tmp_path: Path):
    verifier = TestTimeVerifier(workspace_root=tmp_path)

    old_json = '{"version": "1.0"}'
    new_json = '{"version": "2.0", "active": true}'

    ok, msg = verifier.verify_patch_safety("config.json", old_json, new_json)
    assert ok is True


def test_verify_patch_safety_broken_json_rejected(tmp_path: Path):
    verifier = TestTimeVerifier(workspace_root=tmp_path)

    old_json = '{"version": "1.0"}'
    broken_json = '{"version": "2.0",}'  # trailing comma

    ok, msg = verifier.verify_patch_safety("config.json", old_json, broken_json)
    assert ok is False


# ============================================================================
# 4. AST Contract Analysis & Diff Meta
# ============================================================================

def test_analyze_ast_contract_changes_detects_additions(tmp_path: Path):
    verifier = TestTimeVerifier(workspace_root=tmp_path)

    old_code = "def existing_func(): pass\n"
    new_code = (
        "def existing_func(): pass\n"
        "def new_feature(x: int) -> int:\n"
        '    """New docstring."""\n'
        "    return x * 2\n"
    )

    analysis = verifier.analyze_ast_contract_changes(old_code, new_code)
    assert analysis.get("compatible") is True
    assert "new_feature" in analysis.get("added_symbols", [])


def test_analyze_ast_contract_changes_detects_deletions(tmp_path: Path):
    verifier = TestTimeVerifier(workspace_root=tmp_path)

    old_code = "def legacy_func(): pass\ndef keep_func(): pass\n"
    new_code = "def keep_func(): pass\n"

    analysis = verifier.analyze_ast_contract_changes(old_code, new_code)
    assert "legacy_func" in analysis.get("removed_symbols", [])


def test_analyze_ast_contract_changes_with_classes(tmp_path: Path):
    verifier = TestTimeVerifier(workspace_root=tmp_path)

    old_code = "class BaseService: pass\n"
    new_code = (
        "class BaseService: pass\n"
        "class EnterpriseService(BaseService):\n"
        '    """Enterprise implementation."""\n'
        "    pass\n"
    )

    analysis = verifier.analyze_ast_contract_changes(old_code, new_code)
    assert "EnterpriseService" in analysis.get("added_symbols", [])
