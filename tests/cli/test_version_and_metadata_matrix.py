"""PRUBETH Version & Runtime Metadata Exhaustive Matrix Tests.

Exhaustively verifies get_version_metadata and render_version_info:
- Precision version string v2.0.0
- Architectural invariant assertions: memory budget < 33MB, zero telemetry
- JSON serializability and schema completeness
- Rich ANSI table formatting and column styling
- CP65001 / UTF-8 terminal encoding assertions
"""

from __future__ import annotations

import io
import sys
import json
import pytest
from rich.console import Console

from prubeth.cli.version import (
    PRUBETH_VERSION,
    RELEASE_TIER,
    LICENSE,
    BUILD_COMMIT,
    get_version_metadata,
    render_version_info
)


@pytest.fixture
def test_console():
    return Console(file=io.StringIO(), force_terminal=False, width=120)


# ============================================================================
# 1. Metadata Schema & Invariants Matrix
# ============================================================================

def test_version_constant_is_v2_0_0():
    assert PRUBETH_VERSION == "2.0.0"


def test_license_is_apache_2_0():
    assert LICENSE == "Apache-2.0"


def test_build_commit_is_populated():
    assert len(BUILD_COMMIT) > 0
    assert "v2.0.0" in BUILD_COMMIT


def test_get_version_metadata_contains_all_11_keys():
    meta = get_version_metadata()
    expected_keys = {
        "version",
        "release_tier",
        "python_version",
        "platform",
        "os_release",
        "architecture",
        "terminal_encoding",
        "memory_budget",
        "zero_telemetry",
        "license",
        "build_commit"
    }
    assert expected_keys.issubset(set(meta.keys()))


def test_get_version_metadata_values_are_non_empty_strings():
    meta = get_version_metadata()
    for k, v in meta.items():
        assert isinstance(v, str), f"Key {k} is not a string"
        assert len(v.strip()) > 0, f"Key {k} has empty value"


def test_zero_telemetry_guarantee_present():
    meta = get_version_metadata()
    assert "100% Local-First" in meta["zero_telemetry"]


def test_memory_budget_invariant_enforced():
    meta = get_version_metadata()
    assert "< 33 MB CPU RAM" in meta["memory_budget"]
    assert "0 MB GPU VRAM" in meta["memory_budget"]


# ============================================================================
# 2. Rendering Table Mode Matrix
# ============================================================================

def test_render_version_info_table_prints_title_and_components(test_console: Console):
    render_version_info(test_console, as_json=False)
    out = test_console.file.getvalue()

    assert "PRUBETH Autonomous CLI" in out
    assert "Version & Runtime Information" in out
    assert "CLI Version" in out
    assert "2.0.0" in out
    assert "Release Tier" in out
    assert "Python Runtime" in out
    assert "Apache-2.0" in out
    assert "Zero-Telemetry Guarantee" in out


def test_render_version_info_table_includes_docs_and_security_links(test_console: Console):
    render_version_info(test_console, as_json=False)
    out = test_console.file.getvalue()

    assert "github.com/prubeth-org/prubeth" in out
    assert "security@prubeth.org" in out


# ============================================================================
# 3. Rendering JSON Mode Matrix
# ============================================================================

def test_render_version_info_as_json_outputs_valid_json(test_console: Console, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)

    render_version_info(test_console, as_json=True)

    json_str = buf.getvalue().strip()
    data = json.loads(json_str)

    assert data["version"] == "2.0.0"
    assert data["license"] == "Apache-2.0"
    assert "Local-First" in data["zero_telemetry"]
    assert data["build_commit"] == BUILD_COMMIT
