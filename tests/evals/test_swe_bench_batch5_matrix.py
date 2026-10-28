"""PRUBETH SWE-bench Batch 5 Matrix Tests (Tasks 41 to 50).

Exhaustively verifies evaluation benchmarks 41 through 50:
- swe-41: Semver Parser and Comparator
- swe-42: Binary Search Bisect Left
- swe-43: LFU Cache
- swe-44: Topological Sorter with Cycle Detection
- swe-45: Sliding Window Log Rate Limiter
- swe-46: Markdown Table Parser
- swe-47: Trie Prefix Search with Autocomplete
- swe-48: Diff Patch Hunk Applicator
- swe-49: JSON Pointer RFC 6901
- swe-50: Priority Event Emitter
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.evals.benchmarks import (
    EvalTask,
    get_default_benchmark_suite,
    get_benchmark_by_id,
)

BATCH5_TASK_IDS = [
    "swe-41-semver-comparator",
    "swe-42-binary-search-bisect",
    "swe-43-lfu-cache",
    "swe-44-graph-topological-sort",
    "swe-45-rate-limiter-sliding-window-log",
    "swe-46-markdown-table-parser",
    "swe-47-trie-prefix-search",
    "swe-48-diff-patch-hunk-applicator",
    "swe-49-json-pointer-rfc6901",
    "swe-50-event-emitter-priority",
]


def _setup_task_workspace(task: EvalTask, ws: Path):
    for rel_path, content in task.seed_files.items():
        dest = ws / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


@pytest.mark.parametrize("task_id", BATCH5_TASK_IDS)
def test_swe_bench_batch5_task_retrieval(task_id: str):
    task = get_benchmark_by_id(task_id)
    assert task is not None
    assert task.task_id == task_id
    assert task.name
    assert task.prompt
    assert len(task.seed_files) >= 1
    assert len(task.expected_files) >= 1
    assert len(task.verification_checks) >= 1


@pytest.mark.parametrize("task_id", BATCH5_TASK_IDS)
def test_swe_bench_batch5_provisioning(tmp_path: Path, task_id: str):
    task = get_benchmark_by_id(task_id)
    assert task is not None

    ws = tmp_path / task_id
    _setup_task_workspace(task, ws)

    # Assert all seed files exist in the workspace
    for rel_path, content in task.seed_files.items():
        file_path = ws / rel_path
        assert file_path.exists(), f"Seed file '{rel_path}' not provisioned for {task_id}"
        assert file_path.read_text(encoding="utf-8") == content


def test_swe_41_semver_comparator_verification(tmp_path: Path):
    task = get_benchmark_by_id("swe-41-semver-comparator")
    assert task is not None
    ws = tmp_path / "swe41"
    _setup_task_workspace(task, ws)

    # Initially fails check because it's buggy seed
    assert all(chk(ws) for chk in task.verification_checks) is False

    # Simulate fix
    fix_code = (
        "def parse_semver(v: str) -> tuple[int, int, int]:\n"
        "    parts = v.split('.')\n"
        "    return (int(parts[0]), int(parts[1]), int(parts[2]))\n\n"
        "def compare_semver(v1: str, v2: str) -> int:\n"
        "    t1 = parse_semver(v1)\n"
        "    t2 = parse_semver(v2)\n"
        "    if t1 < t2: return -1\n"
        "    if t1 > t2: return 1\n"
        "    return 0\n"
    )
    (ws / "src/semver.py").write_text(fix_code, encoding="utf-8")
    assert all(chk(ws) for chk in task.verification_checks) is True


def test_swe_42_binary_search_bisect_verification(tmp_path: Path):
    task = get_benchmark_by_id("swe-42-binary-search-bisect")
    assert task is not None
    ws = tmp_path / "swe42"
    _setup_task_workspace(task, ws)
    assert all(chk(ws) for chk in task.verification_checks) is False

    fix_code = (
        "def bisect_left(arr: list[int], target: int) -> int:\n"
        "    low, high = 0, len(arr)\n"
        "    while low < high:\n"
        "        mid = (low + high) // 2\n"
        "        if arr[mid] < target: low = mid + 1\n"
        "        else: high = mid\n"
        "    return low\n"
    )
    (ws / "src/bisect_search.py").write_text(fix_code, encoding="utf-8")
    assert all(chk(ws) for chk in task.verification_checks) is True


def test_swe_44_topo_sort_verification(tmp_path: Path):
    task = get_benchmark_by_id("swe-44-graph-topological-sort")
    assert task is not None
    ws = tmp_path / "swe44"
    _setup_task_workspace(task, ws)
    assert all(chk(ws) for chk in task.verification_checks) is False

    fix_code = (
        "from collections import deque\n"
        "def topological_sort(graph: dict[str, list[str]]) -> list[str]:\n"
        "    in_degree = {u: 0 for u in graph}\n"
        "    for u in graph:\n"
        "        for v in graph[u]:\n"
        "            in_degree[v] = in_degree.get(v, 0) + 1\n"
        "    queue = deque([u for u in in_degree if in_degree[u] == 0])\n"
        "    res = []\n"
        "    while queue:\n"
        "        node = queue.popleft()\n"
        "        res.append(node)\n"
        "        for nxt in graph.get(node, []):\n"
        "            in_degree[nxt] -= 1\n"
        "            if in_degree[nxt] == 0:\n"
        "                queue.append(nxt)\n"
        "    if len(res) < len(in_degree):\n"
        "        raise ValueError('Detected cycle in graph')\n"
        "    return res\n"
    )
    (ws / "src/topo_sort.py").write_text(fix_code, encoding="utf-8")
    assert all(chk(ws) for chk in task.verification_checks) is True


def test_swe_49_json_pointer_verification(tmp_path: Path):
    task = get_benchmark_by_id("swe-49-json-pointer-rfc6901")
    assert task is not None
    ws = tmp_path / "swe49"
    _setup_task_workspace(task, ws)
    assert all(chk(ws) for chk in task.verification_checks) is False

    fix_code = (
        "def resolve_pointer(doc, pointer: str):\n"
        "    if not pointer: return doc\n"
        "    parts = pointer.lstrip('/').split('/')\n"
        "    curr = doc\n"
        "    for p in parts:\n"
        "        key = p.replace('~1', '/').replace('~0', '~')\n"
        "        if isinstance(curr, list):\n"
        "            curr = curr[int(key)]\n"
        "        else:\n"
        "            curr = curr[key]\n"
        "    return curr\n"
    )
    (ws / "src/json_pointer.py").write_text(fix_code, encoding="utf-8")
    assert all(chk(ws) for chk in task.verification_checks) is True


def test_swe_suite_total_count():
    suite = get_default_benchmark_suite()
    assert len(suite) >= 50
