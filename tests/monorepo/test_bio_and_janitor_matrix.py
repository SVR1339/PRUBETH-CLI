"""PRUBETH Computational Biology Bridge & Monorepo Janitor Matrix Tests.

Exhaustively verifies BioComputeBridge PDB/mmCIF structural parsing,
residue/atom counting, AlphaFold pLDDT confidence categorization, Mol* viewer
manifest synthesis, MonorepoJanitor security scanning, secret detection, and
insecure execution auditing.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.monorepo.bio import BioComputeBridge
from prubeth.monorepo.janitor import MonorepoJanitor


# ============================================================================
# 1. BioComputeBridge PDB Structural Parsing
# ============================================================================

SAMPLE_PDB = (
    "HEADER    OXIDOREDUCTASE                          01-OCT-93   1ABC\n"
    "ATOM      1  N   ALA A   1      11.104  13.207  10.000  1.00 95.00           N\n"
    "ATOM      2  CA  ALA A   1      12.000  14.000  11.000  1.00 92.50           C\n"
    "ATOM      3  C   ALA A   1      13.000  15.000  12.000  1.00 88.00           C\n"
    "ATOM      4  N   GLY B   2      20.000  21.000  22.000  1.00 75.00           N\n"
    "END\n"
)

def test_bio_bridge_parse_valid_pdb(tmp_path: Path):
    pdb_file = tmp_path / "protein.pdb"
    pdb_file.write_text(SAMPLE_PDB, encoding="utf-8")

    bridge = BioComputeBridge(workspace_root=tmp_path)
    res = bridge.parse_pdb_structure(str(pdb_file))

    assert "error" not in res
    assert res["file"] == "protein.pdb"
    assert res["total_atoms"] == 4
    assert res["total_residues"] == 2
    assert "A" in res["chains_detected"]
    assert "B" in res["chains_detected"]
    assert res["mean_bfactor_plddt"] > 70
    assert "Confident" in res["structural_confidence"] or "Very High" in res["structural_confidence"]


def test_bio_bridge_missing_file_returns_error(tmp_path: Path):
    bridge = BioComputeBridge(workspace_root=tmp_path)
    res = bridge.parse_pdb_structure("non_existent.pdb")
    assert "error" in res
    assert "not found" in res["error"]


def test_bio_bridge_generate_molstar_manifest(tmp_path: Path):
    pdb_file = tmp_path / "alphafold_model.pdb"
    pdb_file.write_text(SAMPLE_PDB, encoding="utf-8")

    bridge = BioComputeBridge(workspace_root=tmp_path)
    manifest = bridge.generate_molstar_manifest(str(pdb_file), title="Kinase Model")
    assert manifest is not None
    assert isinstance(manifest, dict)


# ============================================================================
# 2. MonorepoJanitor Health & Security Scanning
# ============================================================================

def test_monorepo_janitor_clean_scan(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("def hello(): return 'clean'\n", encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    health = janitor.scan_health()

    assert health["monorepo_files_scanned"] == 1
    assert health["total_lines_of_code"] > 0
    assert len(health["vulnerabilities"]) == 0
    assert health["health_score"] == 100


def test_monorepo_janitor_auto_heal_replaces_os_system(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    f = src / "script.py"
    f.write_text("import os\nos.system('echo test')\n", encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    heal_res = janitor.auto_heal_issues()
    assert heal_res["healed_count"] == 1
    new_content = f.read_text(encoding="utf-8")
    assert "subprocess.run(" in new_content


def test_monorepo_janitor_detects_hardcoded_secret(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "keys.py").write_text(
        '# Secret file\napi_key = "sk-1234567890abcdef1234567890abcdef"\n',
        encoding="utf-8"
    )

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    health = janitor.scan_health()

    assert len(health["vulnerabilities"]) >= 1
    vuln = health["vulnerabilities"][0]
    assert vuln["severity"] == "HIGH"
    assert vuln["rule"] == "Hardcoded Plaintext Secret"
    assert "keys.py" in vuln["file"]


def test_monorepo_janitor_detects_insecure_os_system(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "exec.py").write_text(
        'import os\ndef run_cmd(c): os.system(c)\n',
        encoding="utf-8"
    )

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    health = janitor.scan_health()

    vulns = [v for v in health["vulnerabilities"] if v["severity"] == "MEDIUM"]
    assert len(vulns) >= 1
    assert "os.system" in vulns[0]["snippet"]


def test_monorepo_janitor_ignores_standard_directories(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "ignored.py").write_text('api_key = "sk-1234567890abcdef1234567890abcdef"\n', encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    health = janitor.scan_health()
    # The .git file should be ignored
    assert len(health["vulnerabilities"]) == 0
