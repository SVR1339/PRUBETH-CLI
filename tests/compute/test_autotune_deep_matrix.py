"""PRUBETH Kernel Autotuner & Compute Optimization Matrix Tests.

Exhaustively verifies KernelAutotuner (Subsystem 14): directory initialization,
generate_kernel (Triton, CUDA, C++ fallbacks), benchmark_kernel (high-resolution
timing, speedup calculation, bandwidth metrics, file persistence), and tune_kernel
iterative optimization search loop.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from prubeth.compute.autotune import KernelAutotuner


# ============================================================================
# 1. Directory and Initialization
# ============================================================================

def test_autotuner_creates_kernels_dir(tmp_path: Path):
    tuner = KernelAutotuner(workspace_root=tmp_path)
    assert (tmp_path / ".prubeth" / "kernels").exists()
    assert tuner.kernels_dir == tmp_path / ".prubeth" / "kernels"


# ============================================================================
# 2. Kernel Generation
# ============================================================================

@patch("prubeth.models.gateway.UniversalModelGateway.generate")
def test_generate_kernel_fallback_triton(mock_gen, tmp_path: Path):
    mock_gen.side_effect = ConnectionError("Offline test mode")
    tuner = KernelAutotuner(workspace_root=tmp_path)
    spec = tuner.generate_kernel(target_op="Matrix Multiply", framework="triton")
    assert "kernel_name" in spec
    assert "code" in spec
    assert "matrix_multiply" in spec["kernel_name"]
    assert "torch.matmul" in spec["code"]
    assert "benchmark_harness" in spec
    assert "theoretical_peak_analysis" in spec


@patch("prubeth.models.gateway.UniversalModelGateway.generate")
def test_generate_kernel_fallback_cuda(mock_gen, tmp_path: Path):
    mock_gen.side_effect = ConnectionError("Offline test mode")
    tuner = KernelAutotuner(workspace_root=tmp_path)
    spec = tuner.generate_kernel(target_op="Softmax", framework="cuda")
    assert "kernel_name" in spec
    assert "softmax" in spec["kernel_name"]
    assert "code" in spec


@patch("prubeth.models.gateway.UniversalModelGateway.generate")
def test_generate_kernel_llm_json_response(mock_generate, tmp_path: Path):
    payload = {
        "kernel_name": "custom_flash_attention",
        "code": "def custom_flash_attention(): pass",
        "benchmark_harness": "def bench(): pass",
        "theoretical_peak_analysis": "O(N) IO complexity."
    }
    mock_generate.return_value = MagicMock(text=json.dumps(payload))

    tuner = KernelAutotuner(workspace_root=tmp_path)
    spec = tuner.generate_kernel(target_op="FlashAttention", framework="triton")
    assert spec["kernel_name"] == "custom_flash_attention"
    assert "IO complexity" in spec["theoretical_peak_analysis"]


# ============================================================================
# 3. Kernel Benchmarking
# ============================================================================

def test_benchmark_kernel_writes_file_and_calculates_metrics(tmp_path: Path):
    tuner = KernelAutotuner(workspace_root=tmp_path)
    code = "import torch\ndef kernel(): pass\n"
    res = tuner.benchmark_kernel(target_op="Vector Add", candidate_code=code)

    assert res["target_op"] == "Vector Add"
    assert "speedup_factor" in res
    assert "x" in res["speedup_factor"]
    assert "memory_bandwidth_gbps" in res
    assert "GB/s" in res["memory_bandwidth_gbps"]
    assert Path(res["file_path"]).exists()
    assert Path(res["file_path"]).read_text(encoding="utf-8") == code


def test_benchmark_kernel_timing_values_positive(tmp_path: Path):
    tuner = KernelAutotuner(workspace_root=tmp_path)
    res = tuner.benchmark_kernel(target_op="LayerNorm", candidate_code="def ln(): pass")
    assert res["baseline_latency_ms"] > 0
    assert res["optimized_latency_ms"] >= 0


# ============================================================================
# 4. Iterative Tuning Search Loop
# ============================================================================

@patch("prubeth.models.gateway.UniversalModelGateway.generate")
def test_tune_kernel_runs_iterations(mock_gen, tmp_path: Path):
    mock_gen.side_effect = ConnectionError("Offline test mode")
    tuner = KernelAutotuner(workspace_root=tmp_path)
    best = tuner.tune_kernel(target_op="GEMM", iterations=2)
    assert best is not None
    assert best["target_op"] == "GEMM"
    assert "speedup" in best
    assert "latency" in best
    assert "bandwidth" in best
    assert Path(best["kernel_file"]).exists()


@patch("prubeth.models.gateway.UniversalModelGateway.generate")
def test_tune_kernel_single_iteration(mock_gen, tmp_path: Path):
    mock_gen.side_effect = ConnectionError("Offline test mode")
    tuner = KernelAutotuner(workspace_root=tmp_path)
    best = tuner.tune_kernel(target_op="RMSNorm", iterations=1)
    assert best["target_op"] == "RMSNorm"
    assert "speedup" in best
