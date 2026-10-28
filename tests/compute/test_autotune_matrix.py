"""Comprehensive Unit Test Matrix for PRUBETH Compute Autotuning and GPU Kernel Synthesis."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from prubeth.compute.autotune import KernelAutotuner
from prubeth.models.gateway import GenerationResponse


def test_kernel_autotuner_initialization(tmp_path):
    """Validates KernelAutotuner initialization and directory creation."""
    tuner = KernelAutotuner(workspace_root=tmp_path)
    assert tuner.workspace_root == tmp_path.resolve()
    assert tuner.kernels_dir.is_dir()
    assert tuner.kernels_dir == tmp_path / ".prubeth" / "kernels"


def test_generate_kernel_structured_json(tmp_path):
    """Validates kernel generation from structured LLM JSON."""
    tuner = KernelAutotuner(workspace_root=tmp_path)
    payload = {
        "kernel_name": "fused_layernorm",
        "code": "import torch\ndef layernorm(x): return x",
        "benchmark_harness": "def benchmark(): pass",
        "theoretical_peak_analysis": "Shared memory bound with 4 warps.",
    }

    with patch.object(tuner.model_gw, "generate", return_value=GenerationResponse(text=json.dumps(payload))):
        res = tuner.generate_kernel("LayerNorm", framework="triton")
        assert res["kernel_name"] == "fused_layernorm"
        assert "torch" in res["code"]
        assert "warps" in res["theoretical_peak_analysis"]


def test_generate_kernel_markdown_fence_unwrapping(tmp_path):
    """Validates markdown-wrapped JSON extraction."""
    tuner = KernelAutotuner(workspace_root=tmp_path)
    payload = {
        "kernel_name": "gelu_fp16",
        "code": "def gelu(): pass",
        "benchmark_harness": "pass",
        "theoretical_peak_analysis": "Vectorized loads.",
    }
    raw_text = f"```json\n{json.dumps(payload)}\n```"

    with patch.object(tuner.model_gw, "generate", return_value=GenerationResponse(text=raw_text)):
        res = tuner.generate_kernel("GELU", framework="cuda")
        assert res["kernel_name"] == "gelu_fp16"


def test_generate_kernel_fallback(tmp_path):
    """Validates deterministic fallback kernel when LLM output is non-JSON."""
    tuner = KernelAutotuner(workspace_root=tmp_path)

    with patch.object(tuner.model_gw, "generate", return_value=GenerationResponse(text="Here is your kernel code...")):
        res = tuner.generate_kernel("Softmax", framework="triton")
        assert "kernel_name" in res
        assert "autotuned_softmax" in res["kernel_name"]
        assert "torch.matmul" in res["code"]


def test_benchmark_kernel(tmp_path):
    """Validates file persistence and timing benchmark metrics."""
    tuner = KernelAutotuner(workspace_root=tmp_path)
    candidate_code = "def custom_add(a, b): return a + b"

    metrics = tuner.benchmark_kernel("Vector Add", candidate_code)
    assert metrics["target_op"] == "Vector Add"
    assert "ms" in str(metrics["optimized_latency_ms"]) or isinstance(metrics["optimized_latency_ms"], float)
    assert "x" in metrics["speedup_factor"]
    assert "GB/s" in metrics["memory_bandwidth_gbps"]
    assert Path(metrics["file_path"]).is_file()
    assert Path(metrics["file_path"]).read_text(encoding="utf-8") == candidate_code


def test_tune_kernel_search(tmp_path):
    """Validates iterative autotuning search loop selecting best configuration."""
    tuner = KernelAutotuner(workspace_root=tmp_path)

    with patch.object(tuner, "generate_kernel") as mock_gen:
        mock_gen.return_value = {
            "kernel_name": "fused_attention",
            "code": "def attn(): pass",
            "theoretical_peak_analysis": "Tuned 128x128 blocks",
        }
        with patch.object(tuner, "benchmark_kernel") as mock_bench:
            mock_bench.side_effect = [
                {"speedup_factor": "1.8x", "optimized_latency_ms": 1.5, "baseline_latency_ms": 2.7, "memory_bandwidth_gbps": "750.0 GB/s", "file_path": "k1.py"},
                {"speedup_factor": "2.4x", "optimized_latency_ms": 1.1, "baseline_latency_ms": 2.7, "memory_bandwidth_gbps": "920.0 GB/s", "file_path": "k2.py"},
            ]
            best = tuner.tune_kernel("FlashAttention", iterations=2)
            assert best["speedup"] == "2.4x"
            assert "920.0 GB/s" in best["bandwidth"]
            assert best["iteration"] == 2
