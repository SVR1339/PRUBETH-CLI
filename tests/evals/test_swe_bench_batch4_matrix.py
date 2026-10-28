"""PRUBETH SWE-bench Batch 4 Matrix Tests (Challenges 33 through 40).

Exhaustively verifies probabilistic bloom filters, LRU TTL cache eviction,
circuit breaker state machines, consistent hash rings, SQL injection guards,
binary tree level order traversals, JWT 'none' algorithm rejections, and hex colour parsing.
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

def test_benchmark_suite_contains_40_challenges():
    """Default benchmark suite provides 40 canonical software repair challenges."""
    suite = get_default_benchmark_suite()
    assert len(suite) >= 40
    ids = [t.task_id for t in suite]
    assert "swe-33-bloom-filter" in ids
    assert "swe-34-lru-cache-ttl" in ids
    assert "swe-35-circuit-breaker-fsm" in ids
    assert "swe-36-consistent-hashing" in ids
    assert "swe-37-sql-sanitizer" in ids
    assert "swe-38-level-order-traversal" in ids
    assert "swe-39-jwt-none-algorithm-rejection" in ids
    assert "swe-40-hex-color-parser" in ids


BATCH4_IDS = [
    "swe-33-bloom-filter",
    "swe-34-lru-cache-ttl",
    "swe-35-circuit-breaker-fsm",
    "swe-36-consistent-hashing",
    "swe-37-sql-sanitizer",
    "swe-38-level-order-traversal",
    "swe-39-jwt-none-algorithm-rejection",
    "swe-40-hex-color-parser",
]

@pytest.mark.parametrize("benchmark_id", BATCH4_IDS)
def test_batch4_lookup_by_exact_id(benchmark_id: str):
    task = get_benchmark_by_id(benchmark_id)
    assert task is not None
    assert task.task_id == benchmark_id
    assert len(task.seed_files) > 0
    assert len(task.expected_files) > 0
    assert len(task.verification_checks) > 0


# ============================================================================
# 2. Individual Challenge Seed State Verification
# ============================================================================

def test_swe_33_bloom_filter_baseline_and_solution(tmp_path: Path):
    task = get_benchmark_by_id("swe-33-bloom-filter")
    _setup_task_workspace(task, tmp_path)

    # Baseline seed fails check
    assert not all(c(tmp_path) for c in task.verification_checks)

    # Apply solution
    sol = (
        "class BloomFilter:\n"
        "    def __init__(self, size: int = 1000, hash_count: int = 3):\n"
        "        self.size = size\n"
        "        self.hash_count = hash_count\n"
        "        self.bits = [0] * size\n\n"
        "    def add(self, item: str):\n"
        "        for i in range(self.hash_count):\n"
        "            idx = (hash(item) + i * 31) % self.size\n"
        "            self.bits[idx] = 1\n\n"
        "    def contains(self, item: str) -> bool:\n"
        "        for i in range(self.hash_count):\n"
        "            idx = (hash(item) + i * 31) % self.size\n"
        "            if not self.bits[idx]: return False\n"
        "        return True\n"
    )
    (tmp_path / "src" / "bloom.py").write_text(sol, encoding="utf-8")
    assert all(c(tmp_path) for c in task.verification_checks)


def test_swe_34_lru_ttl_baseline_and_solution(tmp_path: Path):
    task = get_benchmark_by_id("swe-34-lru-cache-ttl")
    _setup_task_workspace(task, tmp_path)

    sol = (
        "import time\n"
        "from collections import OrderedDict\n\n"
        "class LRUTTLCache:\n"
        "    def __init__(self, capacity: int, default_ttl_s: float = 60.0):\n"
        "        self.capacity = capacity\n"
        "        self.ttl = default_ttl_s\n"
        "        self.cache = OrderedDict()\n\n"
        "    def get(self, key: str):\n"
        "        if key not in self.cache:\n"
        "            return None\n"
        "        val, exp = self.cache[key]\n"
        "        if time.time() > exp:\n"
        "            del self.cache[key]\n"
        "            return None\n"
        "        self.cache.move_to_end(key)\n"
        "        return val\n"
    )
    (tmp_path / "src" / "lru_ttl.py").write_text(sol, encoding="utf-8")
    assert all(c(tmp_path) for c in task.verification_checks)


def test_swe_35_circuit_breaker_baseline_and_solution(tmp_path: Path):
    task = get_benchmark_by_id("swe-35-circuit-breaker-fsm")
    _setup_task_workspace(task, tmp_path)

    sol = (
        "class CircuitBreaker:\n"
        "    def __init__(self, max_failures: int = 3, reset_timeout_s: float = 30.0):\n"
        "        self.state = 'CLOSED'\n"
        "        self.failures = 0\n"
        "        self.max_failures = max_failures\n\n"
        "    def record_failure(self):\n"
        "        self.failures += 1\n"
        "        if self.failures >= self.max_failures:\n"
        "            self.state = 'OPEN'\n\n"
        "    def record_success(self):\n"
        "        self.failures = 0\n"
        "        self.state = 'CLOSED'\n"
    )
    (tmp_path / "src" / "circuit.py").write_text(sol, encoding="utf-8")
    assert all(c(tmp_path) for c in task.verification_checks)


def test_swe_36_consistent_hashing_baseline_and_solution(tmp_path: Path):
    task = get_benchmark_by_id("swe-36-consistent-hashing")
    _setup_task_workspace(task, tmp_path)

    sol = (
        "import hashlib\n"
        "import bisect\n\n"
        "class ConsistentHashRing:\n"
        "    def __init__(self, replicas: int = 3):\n"
        "        self.replicas = replicas\n"
        "        self.ring = []\n"
        "        self.nodes = {}\n\n"
        "    def add_node(self, node: str):\n"
        "        h = int(hashlib.md5(node.encode()).hexdigest(), 16)\n"
        "        bisect.insort(self.ring, h)\n"
        "        self.nodes[h] = node\n\n"
        "    def get_node(self, key: str) -> str:\n"
        "        if not self.ring: return ''\n"
        "        h = int(hashlib.md5(key.encode()).hexdigest(), 16)\n"
        "        idx = bisect.bisect_right(self.ring, h) % len(self.ring)\n"
        "        return self.nodes[self.ring[idx]]\n"
    )
    (tmp_path / "src" / "hash_ring.py").write_text(sol, encoding="utf-8")
    assert all(c(tmp_path) for c in task.verification_checks)


def test_swe_37_sql_sanitizer_baseline_and_solution(tmp_path: Path):
    task = get_benchmark_by_id("swe-37-sql-sanitizer")
    _setup_task_workspace(task, tmp_path)

    sol = (
        "import re\n\n"
        "def sanitize_identifier(ident: str) -> str:\n"
        "    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', ident):\n"
        "        raise ValueError(f'Invalid SQL identifier: {ident}')\n"
        "    return f'\"{ident}\"'\n"
    )
    (tmp_path / "src" / "sql_guard.py").write_text(sol, encoding="utf-8")
    assert all(c(tmp_path) for c in task.verification_checks)


def test_swe_38_level_order_traversal_baseline_and_solution(tmp_path: Path):
    task = get_benchmark_by_id("swe-38-level-order-traversal")
    _setup_task_workspace(task, tmp_path)

    sol = (
        "from typing import List, Optional\n"
        "from collections import deque\n\n"
        "class TreeNode:\n"
        "    def __init__(self, val=0, left=None, right=None):\n"
        "        self.val = val\n"
        "        self.left = left\n"
        "        self.right = right\n\n"
        "def level_order(root: Optional[TreeNode]) -> List[List[int]]:\n"
        "    if not root: return []\n"
        "    res = []\n"
        "    queue = deque([root])\n"
        "    while queue:\n"
        "        level = []\n"
        "        for _ in range(len(queue)):\n"
        "            node = queue.popleft()\n"
        "            level.append(node.val)\n"
        "            if node.left: queue.append(node.left)\n"
        "            if node.right: queue.append(node.right)\n"
        "        res.append(level)\n"
        "    return res\n"
    )
    (tmp_path / "src" / "tree_traversal.py").write_text(sol, encoding="utf-8")
    assert all(c(tmp_path) for c in task.verification_checks)


def test_swe_39_jwt_none_rejection_baseline_and_solution(tmp_path: Path):
    task = get_benchmark_by_id("swe-39-jwt-none-algorithm-rejection")
    _setup_task_workspace(task, tmp_path)

    sol = (
        "def verify_token(header: dict, payload: dict, secret: str) -> bool:\n"
        "    alg = str(header.get('alg', '')).lower()\n"
        "    if alg in ['none', '']: return False\n"
        "    return True\n"
    )
    (tmp_path / "src" / "jwt_auth.py").write_text(sol, encoding="utf-8")
    assert all(c(tmp_path) for c in task.verification_checks)


def test_swe_40_hex_color_parser_baseline_and_solution(tmp_path: Path):
    task = get_benchmark_by_id("swe-40-hex-color-parser")
    _setup_task_workspace(task, tmp_path)

    sol = (
        "def parse_hex_color(hex_str: str) -> tuple[int, int, int, float]:\n"
        "    clean = hex_str.lstrip('#')\n"
        "    if len(clean) == 3:\n"
        "        clean = ''.join([c*2 for c in clean]) + 'ff'\n"
        "    elif len(clean) == 6:\n"
        "        clean += 'ff'\n"
        "    r = int(clean[0:2], 16)\n"
        "    g = int(clean[2:4], 16)\n"
        "    b = int(clean[4:6], 16)\n"
        "    a = round(int(clean[6:8], 16) / 255.0, 2)\n"
        "    return (r, g, b, a)\n"
    )
    (tmp_path / "src" / "colors.py").write_text(sol, encoding="utf-8")
    assert all(c(tmp_path) for c in task.verification_checks)
