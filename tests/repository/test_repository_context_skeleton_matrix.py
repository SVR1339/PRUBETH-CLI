"""Tests for RepositoryIntelligence project instructions, rule cascades, and context skeleton generation."""

import json
import pytest
from pathlib import Path
from prubeth.repository.intelligence import RepositoryIntelligence


@pytest.fixture
def intelligence_workspace(tmp_path):
    """Sets up a workspace with project rules, memory, and code files."""
    # 1. Project Rules (PRUBETH.md takes primary priority)
    (tmp_path / "PRUBETH.md").write_text('''
# PRUBETH Project Rules
- Invariant 1: Strictly British English.
- Invariant 2: Micro-footprint execution (< 33 MB idle RAM).
- Invariant 3: Zero cloud telemetry.
''', encoding="utf-8")

    # 2. Persistent Learnings
    mem_dir = tmp_path / ".prubeth" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    learnings = [
        {"id": 1, "directive": "Always use atomic_write_file to prevent file truncation."},
        {"id": 2, "directive": "Always run PolyglotSyntaxGate before applying edits."},
    ]
    (mem_dir / "learnings.json").write_text(json.dumps(learnings), encoding="utf-8")

    # 3. Source files
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "service.py").write_text('''
class ComputeService:
    def execute(self, job_id: str) -> bool:
        return True
''', encoding="utf-8")

    return tmp_path


def test_load_project_instructions_priority_and_learnings(intelligence_workspace):
    intel = RepositoryIntelligence(workspace_root=str(intelligence_workspace))
    instructions = intel.load_project_instructions()

    assert "### Workspace Project Rules (PRUBETH.md):" in instructions
    assert "Strictly British English" in instructions
    assert "Micro-footprint execution" in instructions
    assert "### Persistent Project Learnings & Invariants:" in instructions
    assert "atomic_write_file" in instructions


def test_extract_ast_signatures(intelligence_workspace):
    intel = RepositoryIntelligence(workspace_root=str(intelligence_workspace))
    file_path = intelligence_workspace / "src" / "service.py"
    sigs = intel.extract_ast_signatures(file_path)

    assert any("class ComputeService:" in s for s in sigs)
    assert any("def execute(job_id)" in s for s in sigs)


def test_build_context_skeleton(intelligence_workspace):
    intel = RepositoryIntelligence(workspace_root=str(intelligence_workspace))
    skeleton = intel.build_context_skeleton(max_files=10)

    assert "### Repository Architecture & Skeleton:" in skeleton
    assert "PRUBETH.md" in skeleton
    assert "src/service.py" in skeleton


# =========================================================================
# Parametrized Rule File Candidate Tests
# =========================================================================

RULE_FILE_CANDIDATES = [
    ("PRUBETH.md", "# Custom PRUBETH Directive"),
    ("AGENTS.md", "# Autonomous Agent Invariants"),
    ("GEMINI.md", "# Gemini Model Configurations"),
    ("CLAUDE.md", "# Claude Prompt Architecture"),
]

@pytest.mark.parametrize("filename,content", RULE_FILE_CANDIDATES)
def test_rule_file_discovery_candidates(tmp_path, filename, content):
    (tmp_path / filename).write_text(content, encoding="utf-8")
    intel = RepositoryIntelligence(workspace_root=str(tmp_path))
    instructions = intel.load_project_instructions()
    assert filename in instructions
    assert content in instructions


# =========================================================================
# Scale AST Signature Matrix
# =========================================================================

CLASS_SIGNATURE_SIZES = [5, 10, 20, 30]

@pytest.mark.parametrize("n", CLASS_SIGNATURE_SIZES)
def test_scale_ast_signature_extraction(tmp_path, n):
    lines = []
    for i in range(n):
        lines.append(f"class Component_{i}:\n    def run_{i}(self, arg_{i}: int):\n        pass\n")
    p = tmp_path / "scale_components.py"
    p.write_text("\n".join(lines), encoding="utf-8")

    intel = RepositoryIntelligence(workspace_root=str(tmp_path))
    sigs = intel.extract_ast_signatures(p)
    assert len(sigs) == n * 2  # Each class has 1 class signature + 1 method signature
