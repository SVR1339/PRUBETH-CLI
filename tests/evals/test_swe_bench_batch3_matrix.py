"""PRUBETH SWE-bench Batch 3 Matrix Tests (Challenges 25 through 32).

Exhaustively verifies distributed systems jitter backoff, token bucket rate limiters,
HTTP CRLF header sanitizers, file context manager migrations, weakref cyclic memory safety,
semver parsing, async deadlock-free lock sorting, and safe environment variable expansions.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.evals.benchmarks import (
    get_default_benchmark_suite,
    get_benchmark_by_id,
    EvalTask,
)


def _setup_task_workspace(task: EvalTask, ws: Path):
    for rel_path, content in task.seed_files.items():
        dest = ws / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


# ============================================================================
# 1. Total Suite Size & Lookup Invariants
# ============================================================================

def test_benchmark_suite_contains_32_challenges():
    """Default benchmark suite provides 32 canonical software repair challenges."""
    suite = get_default_benchmark_suite()
    assert len(suite) >= 32
    ids = [t.task_id for t in suite]
    assert "swe-25-exponential-backoff-jitter" in ids
    assert "swe-26-token-bucket-rate-limiter" in ids
    assert "swe-27-http-crlf-header-sanitizer" in ids
    assert "swe-28-unclosed-file-context-manager" in ids
    assert "swe-29-circular-reference-weakref" in ids
    assert "swe-30-semver-comparator" in ids
    assert "swe-31-async-deadlock-prevention" in ids
    assert "swe-32-polyglot-env-expander" in ids


@pytest.mark.parametrize("benchmark_id", [
    "swe-25-exponential-backoff-jitter",
    "swe-26-token-bucket-rate-limiter",
    "swe-27-http-crlf-header-sanitizer",
    "swe-28-unclosed-file-context-manager",
    "swe-29-circular-reference-weakref",
    "swe-30-semver-comparator",
    "swe-31-async-deadlock-prevention",
    "swe-32-polyglot-env-expander",
])
def test_batch3_benchmarks_retrievable_by_id(benchmark_id: str):
    task = get_benchmark_by_id(benchmark_id)
    assert task is not None
    assert task.task_id == benchmark_id
    assert len(task.seed_files) >= 1
    assert len(task.expected_files) >= 1
    assert len(task.verification_checks) >= 1


# ============================================================================
# 2. Reproduction and Fix Verification Matrix
# ============================================================================

def test_swe_25_jitter_backoff_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-25-exponential-backoff-jitter")
    assert task is not None
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # Apply fix
    f = tmp_path / "src" / "retry.py"
    f.write_text(
        "import random\n\n"
        "def compute_backoff(attempt: int, base: float = 1.0, max_backoff: float = 30.0) -> float:\n"
        "    backoff = min(max_backoff, base * (2 ** attempt))\n"
        "    return random.uniform(0, backoff)\n",
        encoding="utf-8"
    )
    assert task.verification_checks[0](tmp_path) is True


def test_swe_26_token_bucket_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-26-token-bucket-rate-limiter")
    assert task is not None
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # Apply fix
    f = tmp_path / "src" / "limiter.py"
    f.write_text(
        "import time\n\n"
        "class TokenBucket:\n"
        "    def __init__(self, capacity: int, fill_rate: float):\n"
        "        self.capacity = capacity\n"
        "        self.fill_rate = fill_rate\n"
        "        self.tokens = float(capacity)\n"
        "        self.last_refill = time.time()\n\n"
        "    def consume(self, tokens: int = 1) -> bool:\n"
        "        now = time.time()\n"
        "        elapsed = now - self.last_refill\n"
        "        self.tokens = min(float(self.capacity), self.tokens + elapsed * self.fill_rate)\n"
        "        self.last_refill = now\n"
        "        if self.tokens >= tokens:\n"
        "            self.tokens -= tokens\n"
        "            return True\n"
        "        return False\n",
        encoding="utf-8"
    )
    assert task.verification_checks[0](tmp_path) is True


def test_swe_27_http_crlf_sanitizer_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-27-http-crlf-header-sanitizer")
    assert task is not None
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # Apply fix
    f = tmp_path / "src" / "http_security.py"
    f.write_text(
        "def sanitize_header_value(val: str) -> str:\n"
        "    return val.replace('\\r', '').replace('\\n', '').strip()\n",
        encoding="utf-8"
    )
    assert task.verification_checks[0](tmp_path) is True


def test_swe_28_unclosed_file_context_manager_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-28-unclosed-file-context-manager")
    assert task is not None
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # Apply fix
    f = tmp_path / "src" / "report_generator.py"
    f.write_text(
        "def generate_report(path: str, lines: list[str]):\n"
        "    with open(path, 'w', encoding='utf-8') as f:\n"
        "        f.write('\\n'.join(lines))\n",
        encoding="utf-8"
    )
    assert task.verification_checks[0](tmp_path) is True


def test_swe_29_circular_reference_weakref_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-29-circular-reference-weakref")
    assert task is not None
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # Apply fix
    f = tmp_path / "src" / "tree_node.py"
    f.write_text(
        "import weakref\n\n"
        "class TreeNode:\n"
        "    def __init__(self, name: str):\n"
        "        self.name = name\n"
        "        self._parent = None\n\n"
        "    def set_parent(self, parent):\n"
        "        self._parent = weakref.ref(parent) if parent else None\n",
        encoding="utf-8"
    )
    assert task.verification_checks[0](tmp_path) is True


def test_swe_30_semver_comparator_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-30-semver-comparator")
    assert task is not None
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # Apply fix
    f = tmp_path / "src" / "versioning.py"
    f.write_text(
        "def parse_semver(v_str: str) -> tuple[int, int, int]:\n"
        "    clean = v_str.lstrip('v').strip()\n"
        "    parts = clean.split('.')\n"
        "    return (int(parts[0]), int(parts[1]), int(parts[2]))\n",
        encoding="utf-8"
    )
    assert task.verification_checks[0](tmp_path) is True


def test_swe_31_async_deadlock_prevention_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-31-async-deadlock-prevention")
    assert task is not None
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # Apply fix
    f = tmp_path / "src" / "transfers.py"
    f.write_text(
        "import asyncio\n\n"
        "async def transfer_funds(acc_a, acc_b, amount: float):\n"
        "    first, second = sorted([acc_a, acc_b], key=lambda a: a.id)\n"
        "    async with first.lock:\n"
        "        async with second.lock:\n"
        "            acc_a.balance -= amount\n"
        "            acc_b.balance += amount\n",
        encoding="utf-8"
    )
    assert task.verification_checks[0](tmp_path) is True


def test_swe_32_polyglot_env_expander_reproduction_and_fix(tmp_path: Path):
    task = get_benchmark_by_id("swe-32-polyglot-env-expander")
    assert task is not None
    _setup_task_workspace(task, tmp_path)
    assert task.verification_checks[0](tmp_path) is False

    # Apply fix
    f = tmp_path / "src" / "env_expander.py"
    f.write_text(
        "import re\n\n"
        "def expand_env(text: str, env_dict: dict) -> str:\n"
        "    def replacer(match):\n"
        "        key = match.group(1)\n"
        "        if ':-' in key:\n"
        "            k, default = key.split(':-', 1)\n"
        "            return env_dict.get(k, default)\n"
        "        return env_dict.get(key, '')\n"
        "    return re.sub(r'\\$\\{([^}]+)\\}', replacer, text)\n",
        encoding="utf-8"
    )
    assert task.verification_checks[0](tmp_path) is True
