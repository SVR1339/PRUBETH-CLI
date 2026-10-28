"""PRUBETH Monorepo Janitor Deep Health & Self-Healing Matrix Tests.

Exhaustively verifies MonorepoJanitor:
- Recursive whole-monorepo health audits
- Invariant enforcement: ignored directory isolation (.git, node_modules, .venv, etc.)
- Secret pattern and insecure execution detection
- AST dead import symbol analysis
- Health score calculation logic (0 to 100 boundary)
- Automated self-healing: os.system replacement with subprocess.run
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.monorepo.janitor import MonorepoJanitor


@pytest.fixture
def clean_monorepo(tmp_path: Path):
    pkg_a = tmp_path / "packages" / "core"
    pkg_a.mkdir(parents=True)
    (pkg_a / "service.py").write_text(
        "import math\n"
        "def compute_radius(area: float) -> float:\n"
        "    return math.sqrt(area / math.pi)\n",
        encoding="utf-8"
    )

    pkg_b = tmp_path / "packages" / "api"
    pkg_b.mkdir(parents=True)
    (pkg_b / "handler.py").write_text(
        "from typing import List\n"
        "def handle_items(items: List[str]) -> int:\n"
        "    return len(items)\n",
        encoding="utf-8"
    )
    return tmp_path


# ============================================================================
# 1. Clean Monorepo Invariant Scans
# ============================================================================

def test_clean_monorepo_scores_100(clean_monorepo: Path):
    janitor = MonorepoJanitor(workspace_root=clean_monorepo)
    report = janitor.scan_health()

    assert report["monorepo_files_scanned"] == 2
    assert report["total_lines_of_code"] > 0
    assert len(report["vulnerabilities"]) == 0
    assert len(report["dead_imports"]) == 0
    assert report["health_score"] == 100


def test_ignored_directories_are_not_scanned(tmp_path: Path):
    # Put bad code inside ignored folders
    for ign in [".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".prubeth"]:
        bad_dir = tmp_path / ign
        bad_dir.mkdir(parents=True, exist_ok=True)
        (bad_dir / "bad.py").write_text('os.system("rm -rf /")\napi_key = "12345678901234567890"\n', encoding="utf-8")

    # Put 1 clean file in root
    (tmp_path / "clean.py").write_text("def ping(): return True\n", encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    report = janitor.scan_health()

    assert report["monorepo_files_scanned"] == 1
    assert len(report["vulnerabilities"]) == 0
    assert report["health_score"] == 100


# ============================================================================
# 2. Vulnerability Detection Matrix
# ============================================================================

@pytest.mark.parametrize("secret_line", [
    'api_key = "1234567890abcdef1234567890"\n',
    'secret = "my_super_secret_token_1234"\n',
    'token = "ghp_1234567890123456789012345"\n',
    'password = "EnterpriseMasterPassword2026"\n',
])
def test_janitor_detects_various_secret_assignments(tmp_path: Path, secret_line: str):
    (tmp_path / "creds.py").write_text(secret_line, encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    report = janitor.scan_health()

    assert len(report["vulnerabilities"]) == 1
    vuln = report["vulnerabilities"][0]
    assert vuln["severity"] == "HIGH"
    assert vuln["rule"] == "Hardcoded Plaintext Secret"
    assert report["health_score"] == 90  # 100 - 10


def test_janitor_detects_os_system_execution(tmp_path: Path):
    (tmp_path / "task.py").write_text('import os\nos.system("echo test")\n', encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    report = janitor.scan_health()

    assert len(report["vulnerabilities"]) == 1
    vuln = report["vulnerabilities"][0]
    assert vuln["severity"] == "MEDIUM"
    assert "os.system" in vuln["rule"]


# ============================================================================
# 3. Dead Import Symbol Detection Matrix
# ============================================================================

def test_janitor_detects_dead_import(tmp_path: Path):
    (tmp_path / "unused.py").write_text(
        "import math\n"
        "import json\n"
        "def run():\n"
        "    return math.pi\n",
        encoding="utf-8"
    )

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    report = janitor.scan_health()

    dead = report["dead_imports"]
    assert len(dead) == 1
    assert dead[0]["symbol"] == "json"
    assert report["health_score"] == 99  # 100 - 1


def test_janitor_ignores_sys_and_os_dead_imports(tmp_path: Path):
    (tmp_path / "sys_os.py").write_text(
        "import sys\n"
        "import os\n"
        "def run(): pass\n",
        encoding="utf-8"
    )

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    report = janitor.scan_health()
    assert len(report["dead_imports"]) == 0


def test_janitor_health_score_lower_bound_zero(tmp_path: Path):
    # Create 15 vulnerabilities -> 100 - 150 = -50 -> bounded at 0
    lines = [f'api_key = "secret_token_number_{i:04d}_abcdef"\n' for i in range(15)]
    (tmp_path / "many_vulns.py").write_text("".join(lines), encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    report = janitor.scan_health()
    assert report["health_score"] == 0


# ============================================================================
# 4. Automated Self-Healing Matrix
# ============================================================================

def test_janitor_auto_heals_os_system_to_subprocess(tmp_path: Path):
    file_p = tmp_path / "legacy.py"
    file_p.write_text('os.system("dir")\n', encoding="utf-8")

    janitor = MonorepoJanitor(workspace_root=tmp_path)
    heal_res = janitor.auto_heal_issues()

    assert heal_res["healed_count"] == 1
    assert len(heal_res["actions"]) == 1
    assert "Replaced os.system with subprocess.run" in heal_res["actions"][0]

    updated_content = file_p.read_text(encoding="utf-8")
    assert "subprocess.run(" in updated_content
    assert "import subprocess" in updated_content

    # Idempotent re-run: nothing left to heal
    heal_res_2 = janitor.auto_heal_issues()
    assert heal_res_2["healed_count"] == 0
