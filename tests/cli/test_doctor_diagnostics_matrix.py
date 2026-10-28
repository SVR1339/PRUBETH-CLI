"""PRUBETH Doctor Qualification & Diagnostic Suite Matrix Tests.

Exhaustively verifies system readiness checks across Python runtime, terminal UTF-8 rendering,
memory footprint, cloud gateways, local offline engines, sandbox jail, and database WAL.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from prubeth.cli.doctor import PrubethDoctor


# ============================================================================
# 1. Full 8-Pillar Diagnostic Execution
# ============================================================================

def test_doctor_diagnose_all_returns_8_pillars():
    doctor = PrubethDoctor()
    overall_ok, results = doctor.diagnose_all()

    # Must contain qualification pillars (minimum 8)
    assert len(results) >= 8
    pillar_names = [r["pillar"] for r in results]
    assert any("Python Runtime" in p for p in pillar_names)
    assert any("Terminal Subsystem" in p for p in pillar_names)
    assert any("Hardware Memory Footprint" in p for p in pillar_names)
    assert any("Cloud AI Provider Gateways" in p for p in pillar_names)
    assert any("Local Offline Engine" in p for p in pillar_names)
    assert any("DevSecOps Sandbox" in p for p in pillar_names)
    assert any("Persistence" in p for p in pillar_names)
    assert any("Cognitive Shifter" in p for p in pillar_names)
    assert any("Cryptographic Runtime Integrity" in p for p in pillar_names)


# ============================================================================
# 2. Python Runtime Pillar
# ============================================================================

def test_doctor_python_version_check():
    doctor = PrubethDoctor()
    _, results = doctor.diagnose_all()
    py_pillar = next(r for r in results if "Python Runtime" in r["pillar"])

    # On test environment Python is 3.12, so status is PASS
    assert py_pillar["status"] == "PASS"
    assert "Python" in py_pillar["detail"]


# ============================================================================
# 3. Memory Footprint Invariance Pillar
# ============================================================================

def test_doctor_memory_footprint_pillar():
    doctor = PrubethDoctor()
    _, results = doctor.diagnose_all()
    mem_pillar = next(r for r in results if "Hardware Memory Footprint" in r["pillar"])

    assert mem_pillar["status"] in ("PASS", "WARN")
    assert "CPU RAM" in mem_pillar["detail"]
    assert "0 MB GPU VRAM" in mem_pillar["detail"]


# ============================================================================
# 4. DevSecOps Sandbox Jail Pillar
# ============================================================================

def test_doctor_sandbox_path_jail_pillar():
    doctor = PrubethDoctor()
    _, results = doctor.diagnose_all()
    sec_pillar = next(r for r in results if "DevSecOps Sandbox" in r["pillar"])

    assert sec_pillar["status"] == "PASS"
    assert "strictly blocked" in sec_pillar["detail"].lower()


# ============================================================================
# 5. Local Offline Engine Probing Pillar
# ============================================================================

def test_doctor_local_offline_engine_pillar():
    doctor = PrubethDoctor()
    with patch.object(doctor.gw, "detect_local_model", return_value={"provider": "ollama", "model": "qwen2.5-coder:7b"}):
        _, results = doctor.diagnose_all()
        local_pillar = next(r for r in results if "Local Offline Engine" in r["pillar"])
        assert local_pillar["status"] == "PASS"
        assert "ollama" in local_pillar["detail"]
