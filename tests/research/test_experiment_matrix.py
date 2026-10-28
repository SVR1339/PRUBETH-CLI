"""Comprehensive Unit Test Matrix for PRUBETH Empirical AI Research Subsystem."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest

from prubeth.research.experiment import ResearchExperimentLoop
from prubeth.models.gateway import GenerationResponse


def test_research_loop_initialization(tmp_path):
    """Validates ResearchExperimentLoop initialization and directory setup."""
    loop = ResearchExperimentLoop(workspace_root=tmp_path)
    assert loop.workspace_root == tmp_path.resolve()
    assert loop.research_dir.is_dir()
    assert loop.research_dir == tmp_path / ".prubeth" / "research"


def test_run_experiment_with_llm_report(tmp_path):
    """Validates experiment execution and markdown report generation from model response."""
    loop = ResearchExperimentLoop(workspace_root=tmp_path)
    mock_md = (
        "# Title: Quantization Invariants in Transformer Kernels\n\n"
        "## 1. Abstract\nFP8 KV-cache preserves accuracy within 0.05% perplexity.\n"
    )

    with patch.object(loop.model_gw, "generate", return_value=GenerationResponse(text=mock_md)):
        res = loop.run_experiment("FP8 KV-cache maintains perplexity within 0.1% of FP16")
        assert res["experiment_id"].startswith("exp_")
        assert Path(res["report_path"]).is_file()
        assert Path(res["report_path"]).read_text(encoding="utf-8") == mock_md.strip()
        assert "Completed empirical study" in res["summary"]


def test_run_experiment_fallback_on_error(tmp_path):
    """Validates fallback report generation when model call raises an exception."""
    loop = ResearchExperimentLoop(workspace_root=tmp_path)

    with patch.object(loop.model_gw, "generate", side_effect=RuntimeError("Gateway timeout")):
        res = loop.run_experiment("Rotary embeddings scale linearly to 1M context")
        assert res["experiment_id"].startswith("exp_")
        report_file = Path(res["report_path"])
        assert report_file.is_file()
        content = report_file.read_text(encoding="utf-8")
        assert "Empirical Study" in content
        assert "Rotary embeddings" in content
        assert "speedup" in content
