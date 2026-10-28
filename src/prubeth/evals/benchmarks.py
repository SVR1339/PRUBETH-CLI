"""PRUBETH Built-in Autonomous Benchmark Suite (SWE-bench & Polyglot Coding Matrix).

Provides curated, repeatable evaluation tasks measuring multi-file bug repair,
syntax restoration, contract preservation, CVE patch remediation, and performance tuning.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from prubeth.evals.harness import EvalTask


def get_default_benchmark_suite() -> List[EvalTask]:
    """Returns the canonical PRUBETH SWE-bench & Polyglot evaluation suite."""
    return [
        EvalTask(
            task_id="swe-01-python-division-guard",
            name="Python Safe Division & ZeroDivisionError Guard",
            prompt="In src/math_utils.py, implement safe_divide(a, b, default=0.0) that handles zero division cleanly without raising an unhandled exception.",
            seed_files={
                "src/math_utils.py": (
                    "def safe_divide(a: float, b: float, default: float = 0.0) -> float:\n"
                    "    # BUG: raises ZeroDivisionError when b == 0\n"
                    "    return a / b\n"
                )
            },
            expected_files=["src/math_utils.py"],
            verification_checks=[
                lambda ws: "try:" in (ws / "src/math_utils.py").read_text(encoding="utf-8")
                or "if b == 0" in (ws / "src/math_utils.py").read_text(encoding="utf-8")
                or "if not b" in (ws / "src/math_utils.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-02-ts-optional-chaining",
            name="TypeScript User Profile Null Check & Optional Chaining",
            prompt="In src/user_service.ts, fix getAvatarUrl to safely navigate user.profile.avatar and return a default placeholder '/default.png' when null.",
            seed_files={
                "src/user_service.ts": (
                    "interface User {\n"
                    "  id: string;\n"
                    "  profile?: { avatar?: string };\n"
                    "}\n\n"
                    "export function getAvatarUrl(user?: User): string {\n"
                    "  // BUG: crashes if user or profile is undefined\n"
                    "  return user.profile.avatar;\n"
                    "}\n"
                )
            },
            expected_files=["src/user_service.ts"],
            verification_checks=[
                lambda ws: "?." in (ws / "src/user_service.ts").read_text(encoding="utf-8")
                or "/default.png" in (ws / "src/user_service.ts").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-03-cve-sql-parameterization",
            name="CVE-Style Security Fix: SQL Injection Remediation",
            prompt="In src/db/users.py, remediate the SQL injection vulnerability in find_user_by_name by using parameterized query arguments instead of string formatting.",
            seed_files={
                "src/db/users.py": (
                    "def find_user_by_name(cursor, username: str):\n"
                    "    # VULNERABILITY: Raw SQL string formatting (SQL injection risk)\n"
                    "    query = f\"SELECT id, name FROM users WHERE username = '{username}'\"\n"
                    "    return cursor.execute(query).fetchall()\n"
                )
            },
            expected_files=["src/db/users.py"],
            verification_checks=[
                lambda ws: "f\"SELECT" not in (ws / "src/db/users.py").read_text(encoding="utf-8")
                and ("%s" in (ws / "src/db/users.py").read_text(encoding="utf-8") or "?" in (ws / "src/db/users.py").read_text(encoding="utf-8"))
            ]
        ),
        EvalTask(
            task_id="swe-04-go-nil-slice-guard",
            name="Go Nil Slice Length Verification",
            prompt="In src/pkg/handler.go, add safe handling to prevent panic when slice is nil or empty in ProcessItems.",
            seed_files={
                "src/pkg/handler.go": (
                    "package pkg\n\n"
                    "func ProcessItems(items []string) string {\n"
                    "    // BUG: may panic on empty/nil slice access\n"
                    "    return items[0]\n"
                    "}\n"
                )
            },
            expected_files=["src/pkg/handler.go"],
            verification_checks=[
                lambda ws: "len(items) == 0" in (ws / "src/pkg/handler.go").read_text(encoding="utf-8")
                or "items == nil" in (ws / "src/pkg/handler.go").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-05-rust-option-unwrap-safe",
            name="Rust Panic Elimination: Replace Unwrap with Option Match",
            prompt="In src/lookup.rs, eliminate unwrap() panic by returning Option<String> in find_item.",
            seed_files={
                "src/lookup.rs": (
                    "use std::collections::HashMap;\n\n"
                    "pub fn find_item(map: &HashMap<String, String>, key: &str) -> String {\n"
                    "    // BUG: unwrap() causes panic on missing key\n"
                    "    map.get(key).unwrap().clone()\n"
                    "}\n"
                )
            },
            expected_files=["src/lookup.rs"],
            verification_checks=[
                lambda ws: ".unwrap()" not in (ws / "src/lookup.rs").read_text(encoding="utf-8")
                or "Option" in (ws / "src/lookup.rs").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-06-memory-leak-clearance",
            name="Synthetic Memory Leak Debugging: Cache Invalidation",
            prompt="In src/cache.py, add clear() and remove_expired() methods to LRUMemoryCache to prevent unbounded memory growth.",
            seed_files={
                "src/cache.py": (
                    "class LRUMemoryCache:\n"
                    "    def __init__(self):\n"
                    "        self._store = {}\n\n"
                    "    def set(self, k, v):\n"
                    "        self._store[k] = v\n"
                )
            },
            expected_files=["src/cache.py"],
            verification_checks=[
                lambda ws: "def clear" in (ws / "src/cache.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-07-multimodule-refactor",
            name="Multi-Module Refactoring & Dependency Synchronisation",
            prompt="Extract format_currency from src/billing.py into a new module src/formatters.py and import it back into src/billing.py.",
            seed_files={
                "src/billing.py": (
                    "def format_currency(amount: float) -> str:\n"
                    "    return f'${amount:.2f}'\n\n"
                    "def calculate_invoice(subtotal: float) -> str:\n"
                    "    return format_currency(subtotal * 1.2)\n"
                )
            },
            expected_files=["src/billing.py", "src/formatters.py"],
            verification_checks=[
                lambda ws: "format_currency" in (ws / "src/formatters.py").read_text(encoding="utf-8")
                and "from src.formatters import format_currency" in (ws / "src/billing.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-08-polyglot-json-serializer",
            name="Polyglot JSON Serializer Fallback",
            prompt="In src/serializer.py, add support for datetime object serialization fallback using isoformat().",
            seed_files={
                "src/serializer.py": (
                    "import json\n"
                    "from datetime import datetime\n\n"
                    "def dumps_payload(data: dict) -> str:\n"
                    "    return json.dumps(data)\n"
                )
            },
            expected_files=["src/serializer.py"],
            verification_checks=[
                lambda ws: "default=" in (ws / "src/serializer.py").read_text(encoding="utf-8")
                or "isoformat" in (ws / "src/serializer.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-09-concurrency-race-mutex",
            name="Concurrency Race Condition & Threading Lock Guard",
            prompt="In src/counter.py, protect shared increment counter with threading.Lock to eliminate race conditions.",
            seed_files={
                "src/counter.py": (
                    "import threading\n\n"
                    "class ThreadSafeCounter:\n"
                    "    def __init__(self):\n"
                    "        self.count = 0\n\n"
                    "    def increment(self):\n"
                    "        # BUG: non-atomic increment under multi-threaded load\n"
                    "        self.count += 1\n"
                )
            },
            expected_files=["src/counter.py"],
            verification_checks=[
                lambda ws: "Lock(" in (ws / "src/counter.py").read_text(encoding="utf-8")
                or "with self." in (ws / "src/counter.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-10-async-timeout-handler",
            name="Async Client Request Timeout Protection",
            prompt="In src/client.py, wrap fetch_resource in asyncio.wait_for with a default 5.0s timeout to prevent hanging connections.",
            seed_files={
                "src/client.py": (
                    "import asyncio\n\n"
                    "async def fetch_resource(client, url: str) -> str:\n"
                    "    # BUG: hangs indefinitely if endpoint does not respond\n"
                    "    return await client.get(url)\n"
                )
            },
            expected_files=["src/client.py"],
            verification_checks=[
                lambda ws: "wait_for(" in (ws / "src/client.py").read_text(encoding="utf-8")
                or "timeout" in (ws / "src/client.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-11-schema-migration-v2",
            name="Database Schema Migration with Default Column Backfill",
            prompt="In src/migrations/v2_add_status.sql, write an ALTER TABLE statement adding column status VARCHAR(32) DEFAULT 'active'.",
            seed_files={
                "src/migrations/v2_add_status.sql": (
                    "-- Migration v2\n"
                )
            },
            expected_files=["src/migrations/v2_add_status.sql"],
            verification_checks=[
                lambda ws: "ALTER TABLE" in (ws / "src/migrations/v2_add_status.sql").read_text(encoding="utf-8").upper()
                and "status" in (ws / "src/migrations/v2_add_status.sql").read_text(encoding="utf-8").lower()
            ]
        ),
        EvalTask(
            task_id="swe-12-regex-redos-mitigation",
            name="ReDoS Vulnerability Remediation with Bounded Quantifiers",
            prompt="In src/validators.py, replace catastrophic backtracking regex (a+)+$ with bounded length check and safe regex ^[a-zA-Z0-9_-]{1,64}$.",
            seed_files={
                "src/validators.py": (
                    "import re\n\n"
                    "def validate_username(s: str) -> bool:\n"
                    "    # VULNERABLE: catastrophic backtracking regex\n"
                    "    return bool(re.match(r'^(a+)+$', s))\n"
                )
            },
            expected_files=["src/validators.py"],
            verification_checks=[
                lambda ws: "(a+)+" not in (ws / "src/validators.py").read_text(encoding="utf-8")
                and "re.match" in (ws / "src/validators.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-13-dockerfile-security-nonroot",
            name="Container Hardening: Non-Root User Least Privilege",
            prompt="In Dockerfile, add a non-root system user 'appuser' and switch USER appuser before CMD.",
            seed_files={
                "Dockerfile": (
                    "FROM python:3.11-slim\n"
                    "WORKDIR /app\n"
                    "COPY . /app\n"
                    "CMD [\"python\", \"-m\", \"prubeth.cli.main\"]\n"
                )
            },
            expected_files=["Dockerfile"],
            verification_checks=[
                lambda ws: "USER " in (ws / "Dockerfile").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-14-rate-limiter-token-bucket",
            name="Token Bucket Rate Limiter Implementation",
            prompt="In src/limiter.py, implement allow_request() in TokenBucketLimiter with capacity and refill rate.",
            seed_files={
                "src/limiter.py": (
                    "import time\n\n"
                    "class TokenBucketLimiter:\n"
                    "    def __init__(self, capacity: int, refill_rate_per_s: float):\n"
                    "        self.capacity = capacity\n"
                    "        self.refill_rate = refill_rate_per_s\n"
                    "        self.tokens = float(capacity)\n"
                    "        self.last_update = time.time()\n\n"
                    "    def allow_request(self) -> bool:\n"
                    "        return True\n"
                )
            },
            expected_files=["src/limiter.py"],
            verification_checks=[
                lambda ws: "self.tokens" in (ws / "src/limiter.py").read_text(encoding="utf-8")
                and "time.time()" in (ws / "src/limiter.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-15-jwt-signature-algorithm-guard",
            name="JWT Algorithm Confusion Attack Guard",
            prompt="In src/auth.py, ensure decode_token explicitly enforces algorithms=['HS256'] to prevent 'none' algorithm bypass.",
            seed_files={
                "src/auth.py": (
                    "import jwt\n\n"
                    "def decode_token(token: str, secret: str):\n"
                    "    # BUG: allows arbitrary algorithms or None\n"
                    "    return jwt.decode(token, secret)\n"
                )
            },
            expected_files=["src/auth.py"],
            verification_checks=[
                lambda ws: "algorithms=" in (ws / "src/auth.py").read_text(encoding="utf-8")
                or "HS256" in (ws / "src/auth.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-16-circuit-breaker-fallback-handler",
            name="Resilient Microservice Fallback on Circuit Open",
            prompt="In src/service.py, implement call_service_with_fallback that catches CircuitOpenError and returns cached default.",
            seed_files={
                "src/service.py": (
                    "class CircuitOpenError(Exception):\n"
                    "    pass\n\n"
                    "def call_service_with_fallback(service_fn, fallback_val):\n"
                    "    return service_fn()\n"
                )
            },
            expected_files=["src/service.py"],
            verification_checks=[
                lambda ws: "CircuitOpenError" in (ws / "src/service.py").read_text(encoding="utf-8")
                and ("try:" in (ws / "src/service.py").read_text(encoding="utf-8") or "except" in (ws / "src/service.py").read_text(encoding="utf-8"))
            ]
        ),
        EvalTask(
            task_id="swe-17-race-condition-mutex-guard",
            name="Concurrency Race Condition Mutex Guard",
            prompt="In src/inventory.py, protect decrement_stock with a threading.Lock to prevent race conditions during concurrent orders.",
            seed_files={
                "src/inventory.py": (
                    "class Inventory:\n"
                    "    def __init__(self, stock: int):\n"
                    "        self.stock = stock\n\n"
                    "    def decrement_stock(self, amount: int) -> bool:\n"
                    "        if self.stock >= amount:\n"
                    "            self.stock -= amount\n"
                    "            return True\n"
                    "        return False\n"
                )
            },
            expected_files=["src/inventory.py"],
            verification_checks=[
                lambda ws: "Lock" in (ws / "src/inventory.py").read_text(encoding="utf-8")
                or "with" in (ws / "src/inventory.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-18-exponential-backoff-retry",
            name="Resilient HTTP Client Exponential Backoff Retry",
            prompt="In src/http_client.py, implement fetch_with_retry with exponential backoff on ConnectionError.",
            seed_files={
                "src/http_client.py": (
                    "import time\n\n"
                    "def fetch_with_retry(request_fn, max_retries: int = 3):\n"
                    "    # BUG: fails immediately on ConnectionError without retry\n"
                    "    return request_fn()\n"
                )
            },
            expected_files=["src/http_client.py"],
            verification_checks=[
                lambda ws: "time.sleep" in (ws / "src/http_client.py").read_text(encoding="utf-8")
                or "range" in (ws / "src/http_client.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-19-path-traversal-jailbreak-guard",
            name="Security Vulnerability: Directory Traversal Sanitizer",
            prompt="In src/files.py, implement sanitize_user_path ensuring that requested path does not escape the base directory.",
            seed_files={
                "src/files.py": (
                    "import os\nfrom pathlib import Path\n\n"
                    "def sanitize_user_path(base_dir: str, user_input: str) -> str:\n"
                    "    # BUG: vulnerable to ../../../etc/passwd traversal\n"
                    "    return os.path.join(base_dir, user_input)\n"
                )
            },
            expected_files=["src/files.py"],
            verification_checks=[
                lambda ws: "resolve" in (ws / "src/files.py").read_text(encoding="utf-8")
                or "relative_to" in (ws / "src/files.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-20-content-security-policy-header",
            name="Web Application Security: CSP Header Enforcement",
            prompt="In src/middleware.py, add Content-Security-Policy header enforcing default-src 'self'.",
            seed_files={
                "src/middleware.py": (
                    "def secure_response_headers(headers: dict) -> dict:\n"
                    "    headers['X-Frame-Options'] = 'DENY'\n"
                    "    return headers\n"
                )
            },
            expected_files=["src/middleware.py"],
            verification_checks=[
                lambda ws: "Content-Security-Policy" in (ws / "src/middleware.py").read_text(encoding="utf-8")
                or "default-src" in (ws / "src/middleware.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-21-atomic-file-temp-rename",
            name="Reliable Storage: Atomic File Write via Temp Replacement",
            prompt="In src/storage.py, implement atomic_write_text using a temporary file and os.replace.",
            seed_files={
                "src/storage.py": (
                    "def atomic_write_text(filepath: str, content: str):\n"
                    "    # BUG: direct non-atomic write risks data corruption during power loss\n"
                    "    with open(filepath, 'w', encoding='utf-8') as f:\n"
                    "        f.write(content)\n"
                )
            },
            expected_files=["src/storage.py"],
            verification_checks=[
                lambda ws: "replace" in (ws / "src/storage.py").read_text(encoding="utf-8")
                or ".tmp" in (ws / "src/storage.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-22-lru-cache-capacity-eviction",
            name="Performance: LRU Cache Eviction on Capacity Overflow",
            prompt="In src/cache.py, ensure put(key, val) evicts the oldest item when size exceeds maxsize.",
            seed_files={
                "src/cache.py": (
                    "from collections import OrderedDict\n\n"
                    "class LRUCache:\n"
                    "    def __init__(self, maxsize: int = 100):\n"
                    "        self.cache = OrderedDict()\n"
                    "        self.maxsize = maxsize\n\n"
                    "    def put(self, key, val):\n"
                    "        self.cache[key] = val\n"
                )
            },
            expected_files=["src/cache.py"],
            verification_checks=[
                lambda ws: "popitem" in (ws / "src/cache.py").read_text(encoding="utf-8")
                or "len" in (ws / "src/cache.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-23-json-streaming-accumulator",
            name="LLM Streaming: Chunked JSON Buffer Accumulator",
            prompt="In src/stream.py, implement parse_chunked_json that accumulates split JSON tokens and parses when complete.",
            seed_files={
                "src/stream.py": (
                    "import json\n\n"
                    "class JSONStreamAccumulator:\n"
                    "    def __init__(self):\n"
                    "        self.buffer = ''\n\n"
                    "    def feed_chunk(self, chunk: str):\n"
                    "        self.buffer += chunk\n"
                )
            },
            expected_files=["src/stream.py"],
            verification_checks=[
                lambda ws: "json.loads" in (ws / "src/stream.py").read_text(encoding="utf-8")
                or "try:" in (ws / "src/stream.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-24-graphql-query-depth-limit",
            name="API Guard: GraphQL Query Nesting Depth Limiter",
            prompt="In src/graphql_guard.py, implement calculate_depth(query_dict) returning the maximum nesting depth.",
            seed_files={
                "src/graphql_guard.py": (
                    "def calculate_depth(node: dict) -> int:\n"
                    "    # BUG: returns 0 always\n"
                    "    return 0\n"
                )
            },
            expected_files=["src/graphql_guard.py"],
            verification_checks=[
                lambda ws: "max" in (ws / "src/graphql_guard.py").read_text(encoding="utf-8")
                or "isinstance" in (ws / "src/graphql_guard.py").read_text(encoding="utf-8")
                or "depth" in (ws / "src/graphql_guard.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-25-exponential-backoff-jitter",
            name="Distributed Systems: Full Jitter Exponential Backoff Calculation",
            prompt="In src/retry.py, implement compute_backoff(attempt: int, base: float = 1.0, max_backoff: float = 30.0) with random jitter between 0 and min(max_backoff, base * 2**attempt).",
            seed_files={
                "src/retry.py": (
                    "def compute_backoff(attempt: int, base: float = 1.0, max_backoff: float = 30.0) -> float:\n"
                    "    # BUG: returns static constant delay\n"
                    "    return 1.0\n"
                )
            },
            expected_files=["src/retry.py"],
            verification_checks=[
                lambda ws: "random" in (ws / "src/retry.py").read_text(encoding="utf-8")
                or "uniform" in (ws / "src/retry.py").read_text(encoding="utf-8")
                or "min" in (ws / "src/retry.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-26-token-bucket-rate-limiter",
            name="Concurrency: Token Bucket Rate Limiter with Timestamp Refills",
            prompt="In src/limiter.py, implement TokenBucket.consume(tokens: int = 1) -> bool that replenishes tokens based on elapsed time and verifies available quota.",
            seed_files={
                "src/limiter.py": (
                    "import time\n\n"
                    "class TokenBucket:\n"
                    "    def __init__(self, capacity: int, fill_rate: float):\n"
                    "        self.capacity = capacity\n"
                    "        self.fill_rate = fill_rate\n"
                    "        self.tokens = float(capacity)\n"
                    "        self.last_refill = time.time()\n\n"
                    "    def consume(self, tokens: int = 1) -> bool:\n"
                    "        # BUG: tokens never replenish\n"
                    "        return True\n"
                )
            },
            expected_files=["src/limiter.py"],
            verification_checks=[
                lambda ws: "time.time()" in (ws / "src/limiter.py").read_text(encoding="utf-8")
                and ("min(" in (ws / "src/limiter.py").read_text(encoding="utf-8") or "-=" in (ws / "src/limiter.py").read_text(encoding="utf-8"))
            ]
        ),
        EvalTask(
            task_id="swe-27-http-crlf-header-sanitizer",
            name="Security: HTTP Response Splitting & CRLF Injection Sanitizer",
            prompt="In src/http_security.py, implement sanitize_header_value(val: str) -> str that strips CRLF characters to prevent HTTP response splitting.",
            seed_files={
                "src/http_security.py": (
                    "def sanitize_header_value(val: str) -> str:\n"
                    "    # BUG: passes raw untrusted string\n"
                    "    return val\n"
                )
            },
            expected_files=["src/http_security.py"],
            verification_checks=[
                lambda ws: "replace" in (ws / "src/http_security.py").read_text(encoding="utf-8")
                or "translate" in (ws / "src/http_security.py").read_text(encoding="utf-8")
                or "\\r" in (ws / "src/http_security.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-28-unclosed-file-context-manager",
            name="Resource Safety: Safe File Context Manager Migration",
            prompt="In src/report_generator.py, refactor generate_report(path, lines) to use 'with open(...) as f:' context manager instead of raw unclosed open().",
            seed_files={
                "src/report_generator.py": (
                    "def generate_report(path: str, lines: list[str]):\n"
                    "    # BUG: file descriptor leak\n"
                    "    f = open(path, 'w', encoding='utf-8')\n"
                    "    f.write('\\n'.join(lines))\n"
                )
            },
            expected_files=["src/report_generator.py"],
            verification_checks=[
                lambda ws: "with open(" in (ws / "src/report_generator.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-29-circular-reference-weakref",
            name="Memory Management: Weakref Parent Pointers in Tree Nodes",
            prompt="In src/tree_node.py, ensure TreeNode.set_parent(parent) stores a weakref.ref(parent) to prevent cyclic reference memory leaks.",
            seed_files={
                "src/tree_node.py": (
                    "class TreeNode:\n"
                    "    def __init__(self, name: str):\n"
                    "        self.name = name\n"
                    "        self.parent = None\n\n"
                    "    def set_parent(self, parent):\n"
                    "        # BUG: strong reference creates cycle\n"
                    "        self.parent = parent\n"
                )
            },
            expected_files=["src/tree_node.py"],
            verification_checks=[
                lambda ws: "weakref" in (ws / "src/tree_node.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-30-semver-comparator",
            name="Package Management: Semantic Version Parser and Comparator",
            prompt="In src/versioning.py, implement parse_semver(v_str: str) -> tuple[int, int, int] that extracts (major, minor, patch) integers from a semver string like 'v2.1.3'.",
            seed_files={
                "src/versioning.py": (
                    "def parse_semver(v_str: str) -> tuple[int, int, int]:\n"
                    "    # BUG: returns dummy 0,0,0\n"
                    "    return (0, 0, 0)\n"
                )
            },
            expected_files=["src/versioning.py"],
            verification_checks=[
                lambda ws: "split" in (ws / "src/versioning.py").read_text(encoding="utf-8")
                and "int" in (ws / "src/versioning.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-31-async-deadlock-prevention",
            name="AsyncIO: Deadlock Prevention with Sorted Resource Acquisition",
            prompt="In src/transfers.py, implement async def transfer_funds(acc_a, acc_b, amount) acquiring locks in consistent sorted ID order to eliminate dining philosopher deadlocks.",
            seed_files={
                "src/transfers.py": (
                    "import asyncio\n\n"
                    "async def transfer_funds(acc_a, acc_b, amount: float):\n"
                    "    # BUG: naive acquisition causes AB-BA deadlock\n"
                    "    async with acc_a.lock:\n"
                    "        async with acc_b.lock:\n"
                    "            acc_a.balance -= amount\n"
                    "            acc_b.balance += amount\n"
                )
            },
            expected_files=["src/transfers.py"],
            verification_checks=[
                lambda ws: "sorted" in (ws / "src/transfers.py").read_text(encoding="utf-8")
                or "<" in (ws / "src/transfers.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-32-polyglot-env-expander",
            name="Config Engine: Environment Variable Expander with Default Fallbacks",
            prompt="In src/env_expander.py, implement expand_env(text: str, env_dict: dict) supporting '${VAR:-default}' syntax safely.",
            seed_files={
                "src/env_expander.py": (
                    "def expand_env(text: str, env_dict: dict) -> str:\n"
                    "    # BUG: returns unexpanded text\n"
                    "    return text\n"
                )
            },
            expected_files=["src/env_expander.py"],
            verification_checks=[
                lambda ws: "re.sub" in (ws / "src/env_expander.py").read_text(encoding="utf-8")
                or ":-" in (ws / "src/env_expander.py").read_text(encoding="utf-8")
                or "get(" in (ws / "src/env_expander.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-33-bloom-filter",
            name="Probabilistic Data Structures: Bloom Filter with Bit Vector",
            prompt="In src/bloom.py, implement BloomFilter(size, hash_count) with add(item) and contains(item).",
            seed_files={
                "src/bloom.py": (
                    "class BloomFilter:\n"
                    "    def __init__(self, size: int = 1000, hash_count: int = 3):\n"
                    "        self.size = size\n"
                    "        self.hash_count = hash_count\n"
                    "        self.bits = [0] * size\n\n"
                    "    def add(self, item: str):\n"
                    "        # BUG: stub implementation\n"
                    "        pass\n\n"
                    "    def contains(self, item: str) -> bool:\n"
                    "        return False\n"
                )
            },
            expected_files=["src/bloom.py"],
            verification_checks=[
                lambda ws: "hash(" in (ws / "src/bloom.py").read_text(encoding="utf-8")
                or "%" in (ws / "src/bloom.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-34-lru-cache-ttl",
            name="Cache Infrastructure: LRU Cache with Time-to-Live Expiration",
            prompt="In src/lru_ttl.py, implement LRUTTLCache(capacity, default_ttl_s) evicting expired entries before capacity evictions.",
            seed_files={
                "src/lru_ttl.py": (
                    "import time\n"
                    "from collections import OrderedDict\n\n"
                    "class LRUTTLCache:\n"
                    "    def __init__(self, capacity: int, default_ttl_s: float = 60.0):\n"
                    "        self.capacity = capacity\n"
                    "        self.ttl = default_ttl_s\n"
                    "        self.cache = OrderedDict()\n\n"
                    "    def get(self, key: str):\n"
                    "        return None\n\n"
                    "    def set(self, key: str, value):\n"
                    "        pass\n"
                )
            },
            expected_files=["src/lru_ttl.py"],
            verification_checks=[
                lambda ws: "time.time()" in (ws / "src/lru_ttl.py").read_text(encoding="utf-8")
                or "OrderedDict" in (ws / "src/lru_ttl.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-35-circuit-breaker-fsm",
            name="Resilience Engineering: Circuit Breaker FSM (CLOSED, OPEN, HALF_OPEN)",
            prompt="In src/circuit.py, implement CircuitBreaker with record_success and record_failure tripping to OPEN after max_failures.",
            seed_files={
                "src/circuit.py": (
                    "class CircuitBreaker:\n"
                    "    def __init__(self, max_failures: int = 3, reset_timeout_s: float = 30.0):\n"
                    "        self.state = 'CLOSED'\n"
                    "        self.failures = 0\n"
                    "        self.max_failures = max_failures\n\n"
                    "    def record_failure(self):\n"
                    "        pass\n\n"
                    "    def record_success(self):\n"
                    "        pass\n"
                )
            },
            expected_files=["src/circuit.py"],
            verification_checks=[
                lambda ws: "OPEN" in (ws / "src/circuit.py").read_text(encoding="utf-8")
                and "CLOSED" in (ws / "src/circuit.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-36-consistent-hashing",
            name="Distributed Systems: Consistent Hash Ring with Virtual Nodes",
            prompt="In src/hash_ring.py, implement ConsistentHashRing with add_node(node), remove_node(node), and get_node(key).",
            seed_files={
                "src/hash_ring.py": (
                    "import hashlib\n"
                    "import bisect\n\n"
                    "class ConsistentHashRing:\n"
                    "    def __init__(self, replicas: int = 3):\n"
                    "        self.replicas = replicas\n"
                    "        self.ring = []\n"
                    "        self.nodes = {}\n\n"
                    "    def add_node(self, node: str):\n"
                    "        pass\n\n"
                    "    def get_node(self, key: str) -> str:\n"
                    "        return ''\n"
                )
            },
            expected_files=["src/hash_ring.py"],
            verification_checks=[
                lambda ws: "bisect" in (ws / "src/hash_ring.py").read_text(encoding="utf-8")
                or "hash" in (ws / "src/hash_ring.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-37-sql-sanitizer",
            name="DevSecOps: SQL Identifier Sanitizer & Identifier Quoter",
            prompt="In src/sql_guard.py, implement sanitize_identifier(ident: str) verifying alphanumeric characters and quoting safely against SQLi.",
            seed_files={
                "src/sql_guard.py": (
                    "import re\n\n"
                    "def sanitize_identifier(ident: str) -> str:\n"
                    "    # BUG: allows arbitrary injection characters\n"
                    "    return ident\n"
                )
            },
            expected_files=["src/sql_guard.py"],
            verification_checks=[
                lambda ws: "re." in (ws / "src/sql_guard.py").read_text(encoding="utf-8")
                or "isalnum" in (ws / "src/sql_guard.py").read_text(encoding="utf-8")
                or "ValueError" in (ws / "src/sql_guard.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-38-level-order-traversal",
            name="Algorithms: Binary Tree Level Order Traversal",
            prompt="In src/tree_traversal.py, implement level_order(root) returning list of values layer by layer.",
            seed_files={
                "src/tree_traversal.py": (
                    "from typing import List, Optional\n"
                    "from collections import deque\n\n"
                    "class TreeNode:\n"
                    "    def __init__(self, val=0, left=None, right=None):\n"
                    "        self.val = val\n"
                    "        self.left = left\n"
                    "        self.right = right\n\n"
                    "def level_order(root: Optional[TreeNode]) -> List[List[int]]:\n"
                    "    # BUG: empty return\n"
                    "    return []\n"
                )
            },
            expected_files=["src/tree_traversal.py"],
            verification_checks=[
                lambda ws: "deque" in (ws / "src/tree_traversal.py").read_text(encoding="utf-8")
                or "pop" in (ws / "src/tree_traversal.py").read_text(encoding="utf-8")
                or "queue" in (ws / "src/tree_traversal.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-39-jwt-none-algorithm-rejection",
            name="Security: JWT 'none' Algorithm Attack Prevention",
            prompt="In src/jwt_auth.py, verify_token(header, payload, secret) rejecting tokens specifying alg='none' or alg='None'.",
            seed_files={
                "src/jwt_auth.py": (
                    "def verify_token(header: dict, payload: dict, secret: str) -> bool:\n"
                    "    # BUG: vulnerable to 'none' algorithm exploit\n"
                    "    if header.get('alg') == 'none':\n"
                    "        return True\n"
                    "    return False\n"
                )
            },
            expected_files=["src/jwt_auth.py"],
            verification_checks=[
                lambda ws: "False" in (ws / "src/jwt_auth.py").read_text(encoding="utf-8")
                and "lower()" in (ws / "src/jwt_auth.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-40-hex-color-parser",
            name="Frontend Utilities: Hex Color Code Parser (RGB and RGBA)",
            prompt="In src/colors.py, implement parse_hex_color(hex_str: str) -> tuple[int, int, int, float] parsing '#fff', '#ffffff', and '#ffffffff'.",
            seed_files={
                "src/colors.py": (
                    "def parse_hex_color(hex_str: str) -> tuple[int, int, int, float]:\n"
                    "    # BUG: dummy black\n"
                    "    return (0, 0, 0, 1.0)\n"
                )
            },
            expected_files=["src/colors.py"],
            verification_checks=[
                lambda ws: "int(" in (ws / "src/colors.py").read_text(encoding="utf-8")
                and "16" in (ws / "src/colors.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-41-semver-comparator",
            name="Package Management: Semantic Version Parser and Comparator",
            prompt="In src/semver.py, implement parse_semver(v: str) -> tuple[int, int, int] and compare_semver(v1: str, v2: str) -> int.",
            seed_files={
                "src/semver.py": (
                    "def parse_semver(v: str) -> tuple[int, int, int]:\n"
                    "    # BUG: dummy return\n"
                    "    return (0, 0, 0)\n\n"
                    "def compare_semver(v1: str, v2: str) -> int:\n"
                    "    return 0\n"
                )
            },
            expected_files=["src/semver.py"],
            verification_checks=[
                lambda ws: "split(" in (ws / "src/semver.py").read_text(encoding="utf-8")
                and "int(" in (ws / "src/semver.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-42-binary-search-bisect",
            name="Algorithms: Bisect Left and Right in Sorted Array with Duplicates",
            prompt="In src/bisect_search.py, implement bisect_left(arr: list[int], target: int) -> int returning first insertion index.",
            seed_files={
                "src/bisect_search.py": (
                    "def bisect_left(arr: list[int], target: int) -> int:\n"
                    "    # BUG: incorrect linear fallback\n"
                    "    return 0\n"
                )
            },
            expected_files=["src/bisect_search.py"],
            verification_checks=[
                lambda ws: "// 2" in (ws / "src/bisect_search.py").read_text(encoding="utf-8")
                or ">> 1" in (ws / "src/bisect_search.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-43-lfu-cache",
            name="Systems: Least Frequently Used (LFU) In-Memory Cache with Tie-Breaking",
            prompt="In src/lfu_cache.py, implement LFUCache with capacity, get(key), and put(key, value) evicting min frequency and oldest accessed.",
            seed_files={
                "src/lfu_cache.py": (
                    "class LFUCache:\n"
                    "    def __init__(self, capacity: int):\n"
                    "        self.capacity = capacity\n"
                    "    def get(self, key: str):\n"
                    "        return None\n"
                    "    def put(self, key: str, value: any) -> None:\n"
                    "        pass\n"
                )
            },
            expected_files=["src/lfu_cache.py"],
            verification_checks=[
                lambda ws: "freq" in (ws / "src/lfu_cache.py").read_text(encoding="utf-8").lower()
                and ("min" in (ws / "src/lfu_cache.py").read_text(encoding="utf-8").lower() or "collections" in (ws / "src/lfu_cache.py").read_text(encoding="utf-8"))
            ]
        ),
        EvalTask(
            task_id="swe-44-graph-topological-sort",
            name="Build Systems: Dependency Graph Topological Sorter with Cycle Detection",
            prompt="In src/topo_sort.py, implement topological_sort(graph: dict[str, list[str]]) -> list[str] raising ValueError on circular dependencies.",
            seed_files={
                "src/topo_sort.py": (
                    "def topological_sort(graph: dict[str, list[str]]) -> list[str]:\n"
                    "    # BUG: returns unsorted keys without cycle check\n"
                    "    return list(graph.keys())\n"
                )
            },
            expected_files=["src/topo_sort.py"],
            verification_checks=[
                lambda ws: "in_degree" in (ws / "src/topo_sort.py").read_text(encoding="utf-8")
                or "deque" in (ws / "src/topo_sort.py").read_text(encoding="utf-8")
                or "visited" in (ws / "src/topo_sort.py").read_text(encoding="utf-8").lower()
            ]
        ),
        EvalTask(
            task_id="swe-45-rate-limiter-sliding-window-log",
            name="Networking: Sliding Window Log Rate Limiter",
            prompt="In src/sliding_limiter.py, implement SlidingWindowRateLimiter(window_s: float, max_requests: int) with allow_request(key: str, now: float) -> bool.",
            seed_files={
                "src/sliding_limiter.py": (
                    "class SlidingWindowRateLimiter:\n"
                    "    def __init__(self, window_s: float, max_requests: int):\n"
                    "        self.window_s = window_s\n"
                    "        self.max_requests = max_requests\n"
                    "    def allow_request(self, key: str, now: float) -> bool:\n"
                    "        # BUG: allow all\n"
                    "        return True\n"
                )
            },
            expected_files=["src/sliding_limiter.py"],
            verification_checks=[
                lambda ws: "append" in (ws / "src/sliding_limiter.py").read_text(encoding="utf-8")
                and ("window_s" in (ws / "src/sliding_limiter.py").read_text(encoding="utf-8") or "now -" in (ws / "src/sliding_limiter.py").read_text(encoding="utf-8"))
            ]
        ),
        EvalTask(
            task_id="swe-46-markdown-table-parser",
            name="Document Processing: Markdown Pipe Table to Structured JSON Records",
            prompt="In src/md_tables.py, parse_markdown_table(table_str: str) -> list[dict[str, str]] parsing headers and stripped cell values.",
            seed_files={
                "src/md_tables.py": (
                    "def parse_markdown_table(table_str: str) -> list[dict[str, str]]:\n"
                    "    # BUG: dummy empty list\n"
                    "    return []\n"
                )
            },
            expected_files=["src/md_tables.py"],
            verification_checks=[
                lambda ws: "splitlines" in (ws / "src/md_tables.py").read_text(encoding="utf-8")
                and "|" in (ws / "src/md_tables.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-47-trie-prefix-search",
            name="Information Retrieval: Trie Prefix Tree with Autocomplete",
            prompt="In src/trie.py, implement Trie with insert(word), search(word) -> bool, and starts_with(prefix) -> list[str].",
            seed_files={
                "src/trie.py": (
                    "class Trie:\n"
                    "    def __init__(self):\n"
                    "        self.root = {}\n"
                    "    def insert(self, word: str) -> None:\n"
                    "        pass\n"
                    "    def search(self, word: str) -> bool:\n"
                    "        return False\n"
                    "    def starts_with(self, prefix: str) -> list[str]:\n"
                    "        return []\n"
                )
            },
            expected_files=["src/trie.py"],
            verification_checks=[
                lambda ws: "children" in (ws / "src/trie.py").read_text(encoding="utf-8").lower()
                or "root" in (ws / "src/trie.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-48-diff-patch-hunk-applicator",
            name="Version Control: Fuzzy Unified Diff Hunk Line Offsets",
            prompt="In src/hunk_patcher.py, implement apply_hunk(original_lines: list[str], hunk: dict) -> list[str] supporting offset tolerance.",
            seed_files={
                "src/hunk_patcher.py": (
                    "def apply_hunk(original_lines: list[str], hunk: dict) -> list[str]:\n"
                    "    # BUG: untouched lines\n"
                    "    return original_lines\n"
                )
            },
            expected_files=["src/hunk_patcher.py"],
            verification_checks=[
                lambda ws: "offset" in (ws / "src/hunk_patcher.py").read_text(encoding="utf-8").lower()
                or "tolerance" in (ws / "src/hunk_patcher.py").read_text(encoding="utf-8").lower()
                or "range" in (ws / "src/hunk_patcher.py").read_text(encoding="utf-8").lower()
            ]
        ),
        EvalTask(
            task_id="swe-49-json-pointer-rfc6901",
            name="Specifications: RFC 6901 JSON Pointer Resolver with Escaped Tildes",
            prompt="In src/json_pointer.py, implement resolve_pointer(doc: dict | list, pointer: str) -> any handling '~1' (/), '~0' (~), and array indices.",
            seed_files={
                "src/json_pointer.py": (
                    "def resolve_pointer(doc, pointer: str):\n"
                    "    # BUG: dummy returns None\n"
                    "    return None\n"
                )
            },
            expected_files=["src/json_pointer.py"],
            verification_checks=[
                lambda ws: "~1" in (ws / "src/json_pointer.py").read_text(encoding="utf-8")
                or "replace" in (ws / "src/json_pointer.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-50-event-emitter-priority",
            name="Architecture: Async Event Emitter with Priority Ordering and Once Listeners",
            prompt="In src/events.py, implement PriorityEventEmitter with on(event, callback, priority=0), once(event, callback), and emit(event, *args).",
            seed_files={
                "src/events.py": (
                    "class PriorityEventEmitter:\n"
                    "    def __init__(self):\n"
                    "        self.listeners = {}\n"
                    "    def on(self, event: str, callback, priority: int = 0) -> None:\n"
                    "        pass\n"
                    "    def once(self, event: str, callback) -> None:\n"
                    "        pass\n"
                    "    def emit(self, event: str, *args) -> None:\n"
                    "        pass\n"
                )
            },
            expected_files=["src/events.py"],
            verification_checks=[
                lambda ws: "sort" in (ws / "src/events.py").read_text(encoding="utf-8").lower()
                or "priority" in (ws / "src/events.py").read_text(encoding="utf-8").lower()
            ]
        ),
        EvalTask(
            task_id="swe-51-token-bucket-rate-limiter",
            name="Distributed Systems: Token Bucket Rate Limiter with Burst Allowance",
            prompt="In src/rate_limiter.py, implement TokenBucket(capacity, refill_rate) with allow(tokens=1) -> bool.",
            seed_files={
                "src/rate_limiter.py": (
                    "class TokenBucket:\n"
                    "    def __init__(self, capacity: float, refill_rate: float):\n"
                    "        self.capacity = capacity\n"
                    "        self.refill_rate = refill_rate\n"
                    "        self.tokens = capacity\n"
                    "    def allow(self, tokens: float = 1.0) -> bool:\n"
                    "        # BUG: no token consumption or time refill\n"
                    "        return True\n"
                )
            },
            expected_files=["src/rate_limiter.py"],
            verification_checks=[
                lambda ws: "time" in (ws / "src/rate_limiter.py").read_text(encoding="utf-8")
                and "tokens" in (ws / "src/rate_limiter.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-52-lru-ttl-cache",
            name="Data Structures: LRU Cache with Per-Key Time-to-Live Expiration",
            prompt="In src/lru_ttl.py, implement LRUTTLCache(capacity) with get(key) -> any and put(key, value, ttl_s=None).",
            seed_files={
                "src/lru_ttl.py": (
                    "class LRUTTLCache:\n"
                    "    def __init__(self, capacity: int):\n"
                    "        self.capacity = capacity\n"
                    "        self.cache = {}\n"
                    "    def get(self, key):\n"
                    "        return None\n"
                    "    def put(self, key, value, ttl_s: float = None):\n"
                    "        pass\n"
                )
            },
            expected_files=["src/lru_ttl.py"],
            verification_checks=[
                lambda ws: "time" in (ws / "src/lru_ttl.py").read_text(encoding="utf-8")
                or "pop" in (ws / "src/lru_ttl.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-53-semver-range-matcher",
            name="Package Management: Semantic Version Range Matcher (^, ~, >=, <=)",
            prompt="In src/semver_range.py, implement matches_range(version: str, range_expr: str) -> bool.",
            seed_files={
                "src/semver_range.py": (
                    "def matches_range(version: str, range_expr: str) -> bool:\n"
                    "    # BUG: dummy returns False\n"
                    "    return False\n"
                )
            },
            expected_files=["src/semver_range.py"],
            verification_checks=[
                lambda ws: "split" in (ws / "src/semver_range.py").read_text(encoding="utf-8")
                or "int" in (ws / "src/semver_range.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-54-diff3-three-way-merge",
            name="Version Control: Diff3 Three-Way Merge Conflict Resolution",
            prompt="In src/merge3.py, implement merge_three_way(base: str, ours: str, theirs: str) -> tuple[bool, str].",
            seed_files={
                "src/merge3.py": (
                    "def merge_three_way(base: str, ours: str, theirs: str) -> tuple[bool, str]:\n"
                    "    # BUG: returns dummy\n"
                    "    return True, ours\n"
                )
            },
            expected_files=["src/merge3.py"],
            verification_checks=[
                lambda ws: "<<<<<<<" in (ws / "src/merge3.py").read_text(encoding="utf-8")
                or "=======" in (ws / "src/merge3.py").read_text(encoding="utf-8")
                or "splitlines" in (ws / "src/merge3.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-55-levenshtein-distance",
            name="Algorithms: Levenshtein Distance with Minimal Edit Script",
            prompt="In src/edit_distance.py, implement levenshtein_distance(s1: str, s2: str) -> int.",
            seed_files={
                "src/edit_distance.py": (
                    "def levenshtein_distance(s1: str, s2: str) -> int:\n"
                    "    # BUG: dummy returns length difference\n"
                    "    return abs(len(s1) - len(s2))\n"
                )
            },
            expected_files=["src/edit_distance.py"],
            verification_checks=[
                lambda ws: "min(" in (ws / "src/edit_distance.py").read_text(encoding="utf-8")
                or "range" in (ws / "src/edit_distance.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-56-bloom-filter-probabilistic",
            name="Data Structures: Probabilistic Bloom Filter with BitArray",
            prompt="In src/bloom.py, implement BloomFilter(expected_elements: int, false_positive_rate=0.01) with add(item) and contains(item) -> bool.",
            seed_files={
                "src/bloom.py": (
                    "class BloomFilter:\n"
                    "    def __init__(self, expected_elements: int, false_positive_rate: float = 0.01):\n"
                    "        self.size = 1000\n"
                    "        self.bits = 0\n"
                    "    def add(self, item: str) -> None:\n"
                    "        pass\n"
                    "    def contains(self, item: str) -> bool:\n"
                    "        return False\n"
                )
            },
            expected_files=["src/bloom.py"],
            verification_checks=[
                lambda ws: "hash" in (ws / "src/bloom.py").read_text(encoding="utf-8").lower()
                or "bits" in (ws / "src/bloom.py").read_text(encoding="utf-8").lower()
            ]
        ),
        EvalTask(
            task_id="swe-57-ast-dependency-resolver",
            name="Compilers: Transitive Import Dependency Ordering with Topological Sort",
            prompt="In src/dep_resolver.py, implement resolve_build_order(modules: dict[str, list[str]]) -> list[str].",
            seed_files={
                "src/dep_resolver.py": (
                    "def resolve_build_order(modules: dict[str, list[str]]) -> list[str]:\n"
                    "    # BUG: returns unsorted keys\n"
                    "    return list(modules.keys())\n"
                )
            },
            expected_files=["src/dep_resolver.py"],
            verification_checks=[
                lambda ws: "visited" in (ws / "src/dep_resolver.py").read_text(encoding="utf-8")
                or "order" in (ws / "src/dep_resolver.py").read_text(encoding="utf-8")
                or "degree" in (ws / "src/dep_resolver.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-58-sliding-window-moving-average",
            name="Streaming: O(1) Real-Time Moving Average & Variance Aggregator",
            prompt="In src/window_stats.py, implement MovingStats(window_size) with add(val), mean() -> float, and variance() -> float.",
            seed_files={
                "src/window_stats.py": (
                    "class MovingStats:\n"
                    "    def __init__(self, window_size: int):\n"
                    "        self.window_size = window_size\n"
                    "        self.values = []\n"
                    "    def add(self, val: float) -> None:\n"
                    "        pass\n"
                    "    def mean(self) -> float:\n"
                    "        return 0.0\n"
                    "    def variance(self) -> float:\n"
                    "        return 0.0\n"
                )
            },
            expected_files=["src/window_stats.py"],
            verification_checks=[
                lambda ws: "sum" in (ws / "src/window_stats.py").read_text(encoding="utf-8")
                or "len" in (ws / "src/window_stats.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-59-cron-expression-parser",
            name="Scheduling: Standard 5-Field Cron Expression Matcher",
            prompt="In src/cron_match.py, implement matches_cron(cron_expr: str, dt) -> bool supporting '*', '*/n', and 'a,b'.",
            seed_files={
                "src/cron_match.py": (
                    "def matches_cron(cron_expr: str, dt) -> bool:\n"
                    "    # BUG: always False\n"
                    "    return False\n"
                )
            },
            expected_files=["src/cron_match.py"],
            verification_checks=[
                lambda ws: "split" in (ws / "src/cron_match.py").read_text(encoding="utf-8")
                or "minute" in (ws / "src/cron_match.py").read_text(encoding="utf-8")
            ]
        ),
        EvalTask(
            task_id="swe-60-dag-cycle-breaker",
            name="Graph Theory: Minimal Feedback Arc Set Graph Cycle Breaker",
            prompt="In src/cycle_breaker.py, implement break_cycles(edges: list[tuple[str, str]]) -> list[tuple[str, str]].",
            seed_files={
                "src/cycle_breaker.py": (
                    "def break_cycles(edges: list[tuple[str, str]]) -> list[tuple[str, str]]:\n"
                    "    # BUG: leaves cycles untouched\n"
                    "    return edges\n"
                )
            },
            expected_files=["src/cycle_breaker.py"],
            verification_checks=[
                lambda ws: "dfs" in (ws / "src/cycle_breaker.py").read_text(encoding="utf-8").lower()
                or "visited" in (ws / "src/cycle_breaker.py").read_text(encoding="utf-8").lower()
                or "cycle" in (ws / "src/cycle_breaker.py").read_text(encoding="utf-8").lower()
            ]
        )
    ]


def get_benchmark_by_id(task_id: str) -> Optional[EvalTask]:
    """Retrieves a specific evaluation task by its identifier."""
    for t in get_default_benchmark_suite():
        if t.task_id == task_id or t.task_id.endswith(task_id):
            return t
    return None
