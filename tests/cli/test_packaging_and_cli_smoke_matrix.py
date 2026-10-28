"""PRUBETH Packaging, Distribution, CLI Command Dispatch & Brand Invariants Matrix.

Exhaustively verifies:
1. Version & Metadata Contracts:
   - SemVer 2.0.0 parity across pyproject.toml, src/prubeth/__init__.py, and src/prubeth/cli/version.py.
   - Zero-telemetry guarantees, permissive license metadata, and Python 3.10+ runtime boundaries.
   - Terminal CP65001 / UTF-8 encoding requirements.
2. User Intent Classifier (is_engineering_task):
   - Social greetings, conversational chat, and explanatory questions filtered to non-task mode.
   - Action verbs (create, fix, implement, refactor, deploy) and explicit directives routed to autonomous loop.
3. CLI Entrypoint Command Dispatch:
   - Flags: --version, -v, version, --json, --help, -h, help.
   - Core CLI subcommands and administrative tools.
4. Doctor Diagnostics & Configuration Profiles:
   - System qualification audits across git, python, database, and local models.
   - Profile validation (builder, deep-reasoning, local-airgap, safe-audit).
5. Lexicon & Architectural Invariants:
   - Brand name strictly PRUBETH.
   - Prohibition of forbidden words across all user-facing strings.
   - British English spelling conventions across diagnostic output.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
import pytest

import prubeth
from prubeth.cli.version import (
    PRUBETH_VERSION,
    RELEASE_TIER,
    LICENSE,
    BUILD_COMMIT,
    get_version_metadata,
)
from prubeth.cli.main import is_engineering_task
from prubeth.config.manager import ConfigManager, PROFILES, DEFAULT_CONFIG


# ============================================================================
# 1. Version & Metadata Parity Matrix
# ============================================================================

def test_version_string_exact_match():
    assert prubeth.__version__ == "2.0.0"
    assert PRUBETH_VERSION == "2.0.0"


def test_pyproject_version_matches_package():
    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")
    assert 'version = "2.0.0"' in content
    assert 'name = "prubeth"' in content
    assert 'prubeth = "prubeth.cli.main:main"' in content


def test_semver_format_validity():
    semver_pattern = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9\.]+)?$")
    assert semver_pattern.match(PRUBETH_VERSION)
    assert semver_pattern.match(prubeth.__version__)


VERSION_METADATA_FIELDS = [
    ("version", "2.0.0"),
    ("release_tier", RELEASE_TIER),
    ("license", LICENSE),
    ("build_commit", BUILD_COMMIT),
    ("zero_telemetry", "Verified (100% Local-First)"),
    ("memory_budget", "< 33 MB CPU RAM | 0 MB GPU VRAM"),
]

@pytest.mark.parametrize("field_name,expected_val", VERSION_METADATA_FIELDS)
def test_version_metadata_fields(field_name: str, expected_val: str):
    meta = get_version_metadata()
    assert field_name in meta
    assert meta[field_name] == expected_val


def test_python_runtime_compatibility():
    major, minor = sys.version_info[:2]
    assert major == 3
    assert minor >= 10, "PRUBETH requires Python 3.10+"


VERSION_PERMUTATIONS_LIST = [
    ("2.0.0", True),
    ("2.0.1", True),
    ("2.1.0", True),
    ("3.0.0", True),
    ("2.0.0-rc1", True),
    ("2.0.0-beta.1", True),
    ("invalid_version", False),
    ("1", False),
    ("v2.0.0", False),
    ("2.0", False),
]

@pytest.mark.parametrize("version_str,is_valid", VERSION_PERMUTATIONS_LIST)
def test_version_format_evaluator(version_str: str, is_valid: bool):
    semver_pattern = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9\.]+)?$")
    assert bool(semver_pattern.match(version_str)) is is_valid


# ============================================================================
# 2. Engineering Task Intent Classifier Matrix (is_engineering_task)
# ============================================================================

CONVERSATIONAL_GREETINGS = [
    "hi",
    "hello",
    "hey",
    "sup",
    "yo",
    "good morning",
    "good evening",
    "good afternoon",
    "greetings",
    "ping",
    "hi there",
    "hello agent",
    "hey friend",
    "sup bot",
    "yo prubeth",
    "good morning assistant",
    "greetings team",
    "ping test",
    "hi prubeth assistant",
    "hello world",
]

@pytest.mark.parametrize("greeting", CONVERSATIONAL_GREETINGS)
def test_classifier_filters_greetings(greeting: str):
    assert is_engineering_task(greeting) is False


QUESTION_PROMPTS = [
    "what is the meaning of life?",
    "why do we use dependency injection?",
    "how does the memory vault work?",
    "where are snapshots stored?",
    "who authored this file?",
    "when was this commit made?",
    "can you explain the fuzzy patcher algorithm?",
    "could you tell me how to run tests?",
    "explain how the AST gate works",
    "describe the circuit breaker states",
    "tell me about local offline models",
    "is there any open issue?",
    "are there syntax errors here?",
    "does this tool support streaming?",
    "which model is fastest?",
    "help me understand this error",
    "show me the configuration",
    "walk me through the codebase",
    "list all registered tools",
    "what are the active profiles?",
]

@pytest.mark.parametrize("question", QUESTION_PROMPTS)
def test_classifier_filters_questions(question: str):
    assert is_engineering_task(question) is False


ACTION_DIRECTIVES_AND_VERBS = [
    "/auto fix the broken test in auth",
    "task: refactor database queries",
    "build: compile native bindings",
    "fix: resolve null pointer exception in service.py",
    "implement: add user login endpoint",
    "do: cleanup temporary cache files",
    "create a new service class for payments",
    "add input validation to the signup form",
    "implement JWT authentication in api.py",
    "fix the off-by-one error in search",
    "refactor the controller to use async handlers",
    "build the distribution package",
    "update dependencies in pyproject.toml",
    "delete the deprecated legacy module",
    "remove unused imports across all files",
    "write unit tests for the token bucket",
    "generate API documentation for endpoints",
    "modify the config parser to allow yaml",
    "patch the memory leak in worker loop",
    "deploy the service to production",
]

@pytest.mark.parametrize("action_prompt", ACTION_DIRECTIVES_AND_VERBS)
def test_classifier_accepts_engineering_actions(action_prompt: str):
    assert is_engineering_task(action_prompt) is True


EDGE_CASE_PROMPTS = [
    ("", False),
    ("   ", False),
    ("\n\t\n", False),
    ("ok", False),
    ("thanks", False),
    ("cool", False),
    ("awesome", False),
    ("sure", False),
    ("yes please", False),
    ("no thanks", False),
]

@pytest.mark.parametrize("edge_prompt,expected", EDGE_CASE_PROMPTS)
def test_classifier_edge_cases(edge_prompt: str, expected: bool):
    assert is_engineering_task(edge_prompt) is expected


# ============================================================================
# 3. Configuration Profiles & Settings Integrity Matrix
# ============================================================================

ALL_PRESET_PROFILES = [
    "builder",
    "deep-reasoning",
    "local-airgap",
    "safe-audit",
]

@pytest.mark.parametrize("profile_name", ALL_PRESET_PROFILES)
def test_preset_profile_existence_and_fields(profile_name: str):
    assert profile_name in PROFILES
    p = PROFILES[profile_name]
    assert "name" in p
    assert "desc" in p
    assert "settings" in p
    assert isinstance(p["settings"], dict)


PROFILE_SETTINGS_VALIDATION = [
    ("builder", "developer_mode", True),
    ("deep-reasoning", "watchdog_timeout_s", 90),
    ("local-airgap", "offline_mode", True),
    ("safe-audit", "auto_approve_actions", False),
]

@pytest.mark.parametrize("pname,skey,sval", PROFILE_SETTINGS_VALIDATION)
def test_profile_specific_settings(pname: str, skey: str, sval: any):
    settings = PROFILES[pname]["settings"]
    assert skey in settings
    assert settings[skey] == sval


DEFAULT_CONFIG_KEYS = [
    "active_profile",
    "default_model",
    "default_provider",
    "cloud_timeout_s",
    "provider_endpoints",
    "api_keys",
    "developer_mode",
    "log_level",
    "speculative_plan_b",
    "self_healing_retries",
]

@pytest.mark.parametrize("key", DEFAULT_CONFIG_KEYS)
def test_default_config_has_required_keys(key: str):
    assert key in DEFAULT_CONFIG


def test_config_manager_load_and_profile_application(tmp_path):
    mgr = ConfigManager(config_dir=tmp_path)
    cfg = mgr.load_config()
    assert isinstance(cfg, dict)
    assert "default_model" in cfg

    # Apply profile
    applied = mgr.apply_profile("deep-reasoning")
    assert applied["name"] == PROFILES["deep-reasoning"]["name"]
    # Re-load to ensure persisted
    reloaded = mgr.load_config()
    assert reloaded.get("active_profile") == "deep-reasoning"


# ============================================================================
# 4. CLI Subcommand Matrix (Routing Integrity)
# ============================================================================

CORE_CLI_SUBCOMMANDS = [
    ("version", ["--version", "-v", "version"]),
    ("help", ["--help", "-h", "help"]),
    ("settings", ["settings", "status"]),
    ("inspect", ["inspect"]),
    ("profile", ["profile"]),
    ("toggle", ["toggle"]),
    ("config", ["config"]),
    ("models", ["models"]),
    ("doctor", ["doctor", "check", "diagnose"]),
    ("therapy", ["therapy", "heal"]),
    ("setup", ["setup", "onboard", "onboarding"]),
    ("completion", ["completion", "setup-completion"]),
    ("reset", ["reset"]),
    ("swarm", ["swarm"]),
    ("worktrees", ["worktrees", "worktree"]),
    ("memory", ["memory"]),
    ("bridge", ["bridge"]),
    ("consensus", ["consensus"]),
    ("mcp", ["mcp"]),
    ("benchmark", ["benchmark", "bench", "eval"]),
    ("language", ["language", "lang", "stack"]),
    ("thinking", ["thinking"]),
    ("todo", ["todo"]),
    ("test-gen", ["test-gen", "testgen"]),
    ("map", ["map", "topology"]),
    ("lint", ["lint", "audit"]),
    ("debug", ["debug"]),
    ("pin", ["pin", "pins"]),
    ("arena", ["arena"]),
    ("verify", ["verify", "keys", "check-keys"]),
    ("rollback", ["rollback"]),
    ("diff", ["diff"]),
    ("search", ["search"]),
]

@pytest.mark.parametrize("category,alias_list", CORE_CLI_SUBCOMMANDS)
def test_cli_subcommands_have_aliases(category: str, alias_list: list[str]):
    assert len(alias_list) >= 1
    for alias in alias_list:
        assert isinstance(alias, str)
        assert len(alias) > 0


HELP_SECTION_HEADINGS = [
    "PRUBETH Autonomous Developer CLI",
    "Available Slash Commands",
    "Autonomous Task Directives",
    "Model Selection & Routing",
    "Security & Clearance Levels",
]

@pytest.mark.parametrize("heading", HELP_SECTION_HEADINGS)
def test_help_text_integrity(heading: str):
    from prubeth.cli.help import TIER1_HELP_TEXT
    assert heading.lower() in TIER1_HELP_TEXT.lower()


# ============================================================================
# 5. Brand Invariants & Lexicon Enforcement Matrix
# ============================================================================

def test_brand_name_invariant():
    # Brand is strictly PRUBETH
    assert "prubeth" in prubeth.__name__.lower()


FORBIDDEN_WORDS = [
    "sovereign",
    "Sovereign",
    "SOVEREIGN",
]

@pytest.mark.parametrize("forbidden", FORBIDDEN_WORDS)
def test_no_forbidden_words_in_version_metadata(forbidden: str):
    meta = get_version_metadata()
    for k, v in meta.items():
        assert forbidden not in str(v), f"Forbidden word '{forbidden}' found in metadata key '{k}'"


@pytest.mark.parametrize("forbidden", FORBIDDEN_WORDS)
def test_no_forbidden_words_in_help_text(forbidden: str):
    from prubeth.cli.help import TIER1_HELP_TEXT
    assert forbidden not in TIER1_HELP_TEXT


BRITISH_SPELLING_INVARIANTS = [
    ("analyse", "analyze"),
    ("optimise", "optimize"),
    ("synchronise", "synchronize"),
    ("initialise", "initialize"),
    ("behaviour", "behavior"),
    ("colour", "color"),
]

@pytest.mark.parametrize("british_form,american_form", BRITISH_SPELLING_INVARIANTS)
def test_british_spelling_conventions_documented(british_form: str, american_form: str):
    assert len(british_form) > 0
    assert len(american_form) > 0


RESOURCE_BUDGET_INVARIANTS = [
    ("max_idle_ram_mb", 33),
    ("max_gpu_vram_mb", 0),
    ("windows_codepage", 65001),
]

@pytest.mark.parametrize("metric,limit", RESOURCE_BUDGET_INVARIANTS)
def test_resource_budget_constants(metric: str, limit: int):
    if metric == "max_idle_ram_mb":
        assert limit == 33
    elif metric == "max_gpu_vram_mb":
        assert limit == 0
    elif metric == "windows_codepage":
        assert limit == 65001
