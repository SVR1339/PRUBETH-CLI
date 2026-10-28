"""PRUBETH Prompt Classification (is_engineering_task) Exhaustive Matrix Tests.

Exhaustively verifies is_engineering_task heuristic classifier:
- Conversational greetings, salutations, inquiries -> False
- Conceptual, theoretical, and architectural questions -> False
- Explicit task prefixes (/auto, task:, build:, fix:, implement:, do:) -> True
- Action verbs (create, implement, refactor, add, patch, delete) -> True
- Boundary edge cases: empty strings, whitespace, punctuation, single characters
"""

from __future__ import annotations

import pytest
from prubeth.cli.main import is_engineering_task


# ============================================================================
# 1. Conversational Queries & Inquiries (Must Return False)
# ============================================================================

CONVERSATIONAL_PROMPTS = [
    "hello",
    "hi",
    "hey",
    "sup",
    "yo",
    "good morning",
    "good afternoon",
    "good evening",
    "greetings",
    "ping",
    "hi there, how are you today?",
    "hello PRUBETH!",
    "hey assistant",
    "what is an abstract syntax tree?",
    "what's the difference between concurrency and parallelism?",
    "why do we use SQLite WAL mode?",
    "how does a Bloom filter achieve O(1) membership checking?",
    "where are configuration files stored in Linux?",
    "who authored the Python programming language?",
    "when was Python 3.12 released?",
    "can you explain how memory compaction works?",
    "could you describe the difference between Git merge and rebase?",
    "explain the Raft consensus algorithm.",
    "describe the role of a circuit breaker in microservices.",
    "tell me a quick summary of this repository.",
    "is there any support for Rust in PRUBETH?",
    "are there any open issues in the backlog?",
    "does this tool support offline GGUF inference?",
    "which model provider is recommended for coding tasks?",
    "help",
    "show me the available commands",
    "walk me through the project layout",
    "list the supported languages",
]

@pytest.mark.parametrize("prompt", CONVERSATIONAL_PROMPTS)
def test_conversational_prompts_classified_as_chat(prompt: str):
    assert is_engineering_task(prompt) is False, f"Expected False for conversational prompt: {prompt}"


# ============================================================================
# 2. Explicit Task Directives & Action Verbs (Must Return True)
# ============================================================================

ENGINEERING_PROMPTS = [
    "/auto build the frontend dashboard component",
    "task: implement JWT authentication guard",
    "build: compile all Rust binaries in release mode",
    "fix: resolve ZeroDivisionError in math_utils.py",
    "implement: add retry logic with exponential backoff",
    "do: delete the stale test cache directory",
    "create a new FastAPI endpoint for user registration",
    "add input validation to the payment handler",
    "implement consistent hashing in src/hash_ring.py",
    "fix the broken unit test in tests/test_parser.py",
    "refactor the database query layer to use connection pooling",
    "build the production distribution wheel package",
    "update the version string in pyproject.toml to 2.0.0",
    "delete all temporary cache files in .pytest_cache",
    "remove deprecated methods from the UserService class",
    "write unit tests for the token bucket rate limiter",
    "generate a benchmark suite for the JSON repair engine",
    "modify the config schema to add thinking_budget setting",
    "patch the security vulnerability in the subprocess execution call",
    "install the required dependencies from requirements.txt",
    "test the authentication middleware under high load",
    "run pytest across all runtime test suites",
    "deploy the release artifact to the test repository",
    "migrate from threading to asyncio in the network worker",
    "setup the pre-commit hook configuration file",
    "configure the fallback model provider in config.json",
    "make a new directory called src/persistence/wal",
    "draft a schema migration script for user profiles",
    "commit these changes with message 'feat: add telemetry'",
    "push the current release branch to origin",
]

@pytest.mark.parametrize("prompt", ENGINEERING_PROMPTS)
def test_engineering_prompts_classified_as_tasks(prompt: str):
    assert is_engineering_task(prompt) is True, f"Expected True for engineering task prompt: {prompt}"


# ============================================================================
# 3. Boundary & Edge Case Permutations
# ============================================================================

BOUNDARY_CASES = [
    ("", False),
    ("   ", False),
    ("\n\t\n", False),
    ("???", False),
    ("...", False),
    ("a", False),
    ("!", False),
    ("123", False),
]

@pytest.mark.parametrize("prompt,expected", BOUNDARY_CASES)
def test_boundary_prompts(prompt: str, expected: bool):
    assert is_engineering_task(prompt) is expected
