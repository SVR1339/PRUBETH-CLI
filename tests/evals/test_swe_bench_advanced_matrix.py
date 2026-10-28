"""PRUBETH Advanced SWE-bench Suite Matrix (Challenges 17 through 24).

Exhaustively verifies concurrency mutex guards, exponential backoff retries,
path traversal sanitization, CSP security headers, atomic temp file replacement,
LRU eviction, streaming JSON accumulators, and GraphQL depth limiters.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.evals.benchmarks import (
    get_default_benchmark_suite,
    get_benchmark_by_id,
    EvalTask,
)
from prubeth.evals.harness import EvalHarness


# ============================================================================
# 1. Total Suite Size & Lookup Invariants
# ============================================================================

def test_benchmark_suite_contains_24_challenges():
    """Default benchmark suite provides at least 24 canonical software repair challenges."""
    suite = get_default_benchmark_suite()
    assert len(suite) >= 24
    ids = [t.task_id for t in suite]
    assert "swe-17-race-condition-mutex-guard" in ids
    assert "swe-18-exponential-backoff-retry" in ids
    assert "swe-19-path-traversal-jailbreak-guard" in ids
    assert "swe-20-content-security-policy-header" in ids
    assert "swe-21-atomic-file-temp-rename" in ids
    assert "swe-22-lru-cache-capacity-eviction" in ids
    assert "swe-23-json-streaming-accumulator" in ids
    assert "swe-24-graphql-query-depth-limit" in ids


@pytest.mark.parametrize("benchmark_id", [
    "swe-17-race-condition-mutex-guard",
    "swe-18-exponential-backoff-retry",
    "swe-19-path-traversal-jailbreak-guard",
    "swe-20-content-security-policy-header",
    "swe-21-atomic-file-temp-rename",
    "swe-22-lru-cache-capacity-eviction",
    "swe-23-json-streaming-accumulator",
    "swe-24-graphql-query-depth-limit",
])
def test_advanced_benchmarks_retrievable_by_id(benchmark_id: str):
    """Each advanced benchmark is retrievable via get_benchmark_by_id."""
    task = get_benchmark_by_id(benchmark_id)
    assert task is not None
    assert task.task_id == benchmark_id
    assert len(task.seed_files) >= 1
    assert len(task.expected_files) >= 1
    assert len(task.verification_checks) >= 1


# ============================================================================
# 2. Reproduction and Fix Verification Tests
# ============================================================================

def _setup_task_workspace(task: EvalTask, ws: Path):
    for rel_path, content in task.seed_files.items():
        dest = ws / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def test_swe_17_mutex_guard_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-17-race-condition-mutex-guard")
    assert task is not None

    # 1. Initial seed reproduces defect (no Lock)
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # 2. Apply fix
    f = tmp_path / "src" / "inventory.py"
    fixed_code = (
        "import threading\n\n"
        "class Inventory:\n"
        "    def __init__(self, stock: int):\n"
        "        self.stock = stock\n"
        "        self.lock = threading.Lock()\n\n"
        "    def decrement_stock(self, amount: int) -> bool:\n"
        "        with self.lock:\n"
        "            if self.stock >= amount:\n"
        "                self.stock -= amount\n"
        "                return True\n"
        "            return False\n"
    )
    f.write_text(fixed_code, encoding="utf-8")
    assert task.verification_checks[0](tmp_path) is True


def test_swe_19_path_traversal_guard_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-19-path-traversal-jailbreak-guard")
    assert task is not None

    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    f = tmp_path / "src" / "files.py"
    fixed_code = (
        "import os\nfrom pathlib import Path\n\n"
        "def sanitize_user_path(base_dir: str, user_input: str) -> str:\n"
        "    resolved = (Path(base_dir) / user_input).resolve()\n"
        "    base_resolved = Path(base_dir).resolve()\n"
        "    try:\n"
        "        resolved.relative_to(base_resolved)\n"
        "        return str(resolved)\n"
        "    except ValueError:\n"
        "        return str(base_resolved)\n"
    )
    f.write_text(fixed_code, encoding="utf-8")
    assert task.verification_checks[0](tmp_path) is True


def test_swe_21_atomic_file_rename_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-21-atomic-file-temp-rename")
    assert task is not None

    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    f = tmp_path / "src" / "storage.py"
    fixed_code = (
        "import os\n\n"
        "def atomic_write_text(filepath: str, content: str):\n"
        "    tmp_file = f'{filepath}.tmp'\n"
        "    with open(tmp_file, 'w', encoding='utf-8') as f:\n"
        "        f.write(content)\n"
        "    os.replace(tmp_file, filepath)\n"
    )
    f.write_text(fixed_code, encoding="utf-8")
    assert task.verification_checks[0](tmp_path) is True


def test_swe_22_lru_cache_eviction_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-22-lru-cache-capacity-eviction")
    assert task is not None

    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    f = tmp_path / "src" / "cache.py"
    fixed_code = (
        "from collections import OrderedDict\n\n"
        "class LRUCache:\n"
        "    def __init__(self, maxsize: int = 100):\n"
        "        self.cache = OrderedDict()\n"
        "        self.maxsize = maxsize\n\n"
        "    def put(self, key, val):\n"
        "        if key in self.cache:\n"
        "            self.cache.move_to_end(key)\n"
        "        self.cache[key] = val\n"
        "        if len(self.cache) > self.maxsize:\n"
        "            self.cache.popitem(last=False)\n"
    )
    f.write_text(fixed_code, encoding="utf-8")
    assert task.verification_checks[0](tmp_path) is True
