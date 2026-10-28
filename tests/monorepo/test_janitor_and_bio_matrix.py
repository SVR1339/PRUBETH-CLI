"""Comprehensive Unit Test Matrix for PRUBETH Monorepo Janitor and Bio-Compute Engine."""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.monorepo.janitor import MonorepoJanitor
from prubeth.monorepo.bio import BioComputeBridge


def test_monorepo_janitor_initialization(tmp_path):
    """Validates MonorepoJanitor initialization and default ignored directories."""
    janitor = MonorepoJanitor(workspace_root=tmp_path)
    assert janitor.workspace_root == tmp_path.resolve()
    assert ".git" in janitor.ignored
    assert "node_modules" in janitor.ignored
    assert ".venv" in janitor.ignored


def test_monorepo_janitor_clean_monorepo(tmp_path):
    """Validates 100% health score on clean, vulnerability-free codebase."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "math_utils.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8"
    )

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    res = janitor.scan_health()

    assert res["monorepo_files_scanned"] == 1
    assert res["total_lines_of_code"] == 2
    assert res["vulnerabilities"] == []
    assert res["dead_imports"] == []
    assert res["health_score"] == 100


def test_monorepo_janitor_detects_secrets_and_insecure_exec(tmp_path):
    """Validates detection of hardcoded plaintext API keys and os.system usage."""
    (tmp_path / "vulnerable.py").write_text(
        "import os\n"
        "api_key = 'sk-1234567890abcdef1234567890abcdef'\n"
        "os.system('ls -la')\n",
        encoding="utf-8"
    )

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    res = janitor.scan_health()

    assert len(res["vulnerabilities"]) == 2
    rules = [v["rule"] for v in res["vulnerabilities"]]
    assert "Hardcoded Plaintext Secret" in rules
    assert "Insecure os.system Subshell Execution" in rules
    assert res["health_score"] < 100


def test_monorepo_janitor_detects_dead_imports(tmp_path):
    """Validates AST-driven detection of unused imported symbols."""
    (tmp_path / "unused.py").write_text(
        "import math\n"
        "from collections import defaultdict\n\n"
        "def compute(x):\n"
        "    return x * 2\n",
        encoding="utf-8"
    )

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    res = janitor.scan_health()

    dead_symbols = [d["symbol"] for d in res["dead_imports"]]
    assert "math" in dead_symbols
    assert "defaultdict" in dead_symbols


def test_monorepo_janitor_auto_heal_insecure_exec(tmp_path):
    """Validates automated remediation replacing os.system with subprocess.run."""
    script = tmp_path / "runner.py"
    script.write_text("import os\n\ndef run():\n    os.system('echo test')\n", encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    heal_res = janitor.auto_heal_issues()

    assert heal_res["healed_count"] == 1
    remediated_content = script.read_text(encoding="utf-8")
    assert "subprocess.run(" in remediated_content
    assert "import subprocess" in remediated_content
    assert "os.system(" not in remediated_content


def test_bio_bridge_parse_missing_file(tmp_path):
    """Validates graceful error handling when structure file is missing."""
    bridge = BioComputeBridge(workspace_root=tmp_path)
    res = bridge.parse_pdb_structure("non_existent.pdb")
    assert "error" in res
    assert "not found" in res["error"]


@pytest.mark.parametrize("b_factor,expected_category", [
    (95.0, "Very High (>90)"),
    (82.5, "Confident (70-90)"),
    (55.0, "Low (<70)"),
])
def test_bio_bridge_parse_pdb_and_plddt(tmp_path, b_factor: float, expected_category: str):
    """Validates atom/residue extraction and AlphaFold pLDDT confidence categorisation."""
    pdb_file = tmp_path / "protein.pdb"
    # Canonical PDB ATOM record: cols 1-6 (ATOM), 13-16 (name), 18-20 (res), 22 (chain), 23-26 (seq), 61-66 (b_factor)
    atom_line = f"ATOM      1  CA  MET A   1      20.154  12.012  15.890  1.00 {b_factor:5.2f}           C\n"
    pdb_file.write_text(atom_line, encoding="utf-8")

    bridge = BioComputeBridge(workspace_root=tmp_path)
    res = bridge.parse_pdb_structure(str(pdb_file))

    assert res["file"] == "protein.pdb"
    assert res["total_atoms"] == 1
    assert res["total_residues"] == 1
    assert res["chains_detected"] == ["A"]
    assert res["mean_bfactor_plddt"] == b_factor
    assert res["structural_confidence"] == expected_category


def test_bio_bridge_generate_molstar_manifest(tmp_path):
    """Validates generation of Mol* 3D molecular visualization manifest."""
    pdb_file = tmp_path / "target.pdb"
    pdb_file.write_text(
        "ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00 92.00           N\n"
        "ATOM      2  CA  ALA A   1      11.000  11.000  11.000  1.00 94.00           C\n",
        encoding="utf-8"
    )

    bridge = BioComputeBridge(workspace_root=tmp_path)
    manifest = bridge.generate_molstar_manifest(str(pdb_file), title="Kinase Receptor")

    assert manifest["title"] == "Kinase Receptor"
    assert manifest["format"] == "pdb"
    assert manifest["status"] == "READY_FOR_3D_RENDERING"
    assert manifest["metrics"]["total_atoms"] == 2
    assert manifest["metrics"]["mean_bfactor_plddt"] == 93.0
    assert manifest["metrics"]["structural_confidence"] == "Very High (>90)"
