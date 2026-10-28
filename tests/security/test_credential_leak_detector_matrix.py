"""PRUBETH Credential Leak Detection & Secret Scrubbing Matrix Tests.

Exhaustively verifies SecurityEngine secret redaction and PolyglotQualityLinter
secret pattern scanning:
- Provider API keys (OpenAI, Anthropic, Google Gemini, GitHub, AWS)
- Generic bearer tokens, passwords, and authorization headers
- Preservation invariants for non-secret UUIDs, git SHAs, function parameters, and URLs
- Polyglot static secret detection across multiple language files
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prubeth.security.permissions import SecurityEngine
from prubeth.security.linter import PolyglotQualityLinter, SECRET_PATTERNS


# ============================================================================
# 1. Redaction Matrix: Provider Keys
# ============================================================================

PROVIDER_SECRETS = [
    ("sk-1234567890abcdef1234567890123456", "[REDACTED_OPENAI_KEY]"),
    ("sk-proj-1234567890abcdef1234567890123456", "[REDACTED_OPENAI_KEY]"),
    ("sk-ant-api03-abcdef1234567890abcdef1234567890", "[REDACTED_ANTHROPIC_KEY]"),
    ("AIzaSyB1234567890abcdefghijklmnopqrstuv", "[REDACTED_GEMINI_KEY]"),
    ("AIzaSyD9876543210zyxwvutsrqponmlkjihgfe", "[REDACTED_GEMINI_KEY]"),
    ("ghp_1234567890abcdefghijklmnopqrstuvwxyz", "[REDACTED_GITHUB_TOKEN]"),
    ("ghp_ABCDEF1234567890abcdef1234567890abcd", "[REDACTED_GITHUB_TOKEN]"),
]

@pytest.mark.parametrize("raw_secret,expected_placeholder", PROVIDER_SECRETS)
def test_redact_provider_secrets_in_isolation(raw_secret: str, expected_placeholder: str):
    sec = SecurityEngine()
    redacted = sec.redact_secrets(raw_secret)
    assert raw_secret not in redacted
    assert expected_placeholder in redacted


@pytest.mark.parametrize("raw_secret,expected_placeholder", PROVIDER_SECRETS)
def test_redact_provider_secrets_embedded_in_logs(raw_secret: str, expected_placeholder: str):
    sec = SecurityEngine()
    log_line = f"2026-10-28 09:30:00 [ERROR] Connection failed using authorization header key {raw_secret} from IP 127.0.0.1"
    redacted = sec.redact_secrets(log_line)
    assert raw_secret not in redacted
    assert expected_placeholder in redacted
    assert "2026-10-28 09:30:00 [ERROR]" in redacted
    assert "from IP 127.0.0.1" in redacted


# ============================================================================
# 2. Redaction Matrix: Generic Key/Password Patterns
# ============================================================================

GENERIC_SECRETS = [
    ('api_key: "abcdef1234567890abcdef123456"', '***REDACTED***'),
    ('apiKey = "abcdef1234567890abcdef123456"', '***REDACTED***'),
    ('secret: "my_ultra_secret_app_token_999"', '***REDACTED***'),
    ('token = "secret_auth_token_value_xyz123"', '***REDACTED***'),
    ('password: "DatabaseSuperPassword2026!"', '***REDACTED***'),
    ('auth = "super_secret_auth_string_12345"', '***REDACTED***'),
    ('bearer: "header_bearer_token_string_456"', '***REDACTED***'),
]

@pytest.mark.parametrize("secret_text,expected_marker", GENERIC_SECRETS)
def test_redact_generic_secrets(secret_text: str, expected_marker: str):
    sec = SecurityEngine()
    redacted = sec.redact_secrets(secret_text)
    assert expected_marker in redacted
    # Raw value extracted
    raw_val = secret_text.split('"')[1]
    assert raw_val not in redacted


# ============================================================================
# 3. Preservation Invariants: Non-Secrets Must Never Be Redacted
# ============================================================================

SAFE_NON_SECRETS = [
    "bb91c880-6116-4761-9938-8870c1183574",
    "ca18d27d-9f55-4a43-bfda-ab003fdc5436",
    "00000000-0000-0000-0000-000000000000",
    "commit 7a3f89b2c4d5e6f1029384756a1b2c3d4e5f6071",
    "def calculate_cost(tokens: int, prompt_tokens: int) -> float:",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro",
    "http://localhost:11434/v1/chat/completions",
    "User query: Please analyse this Python function for memory leaks.",
    "pytest -q tests/tools/test_file_core_tools.py",
]

@pytest.mark.parametrize("safe_text", SAFE_NON_SECRETS)
def test_preservation_of_safe_non_secret_strings(safe_text: str):
    sec = SecurityEngine()
    redacted = sec.redact_secrets(safe_text)
    assert redacted == safe_text


def test_redact_secrets_empty_and_none_handling():
    sec = SecurityEngine()
    assert sec.redact_secrets("") == ""
    assert sec.redact_secrets(None) == ""


# ============================================================================
# 4. Polyglot Quality Linter Secret Detection Matrix
# ============================================================================

def test_linter_detects_aws_key(tmp_path: Path):
    src = tmp_path / "aws_deploy.py"
    src.write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")

    linter = PolyglotQualityLinter(workspace_root=tmp_path)
    issues = linter.audit_workspace(include_tests=True)

    aws_issue = next((i for i in issues if "AWS Access Key" in i["rule"]), None)
    assert aws_issue is not None
    assert aws_issue["severity"] == "CRITICAL"


def test_linter_detects_rsa_private_key(tmp_path: Path):
    key_file = tmp_path / "server.key"
    key_file.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y+...\n"
        "-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8"
    )

    linter = PolyglotQualityLinter(workspace_root=tmp_path)
    issues = linter.audit_workspace(include_tests=True)

    key_issue = next((i for i in issues if "Private Cryptographic Key" in i["rule"]), None)
    assert key_issue is not None
    assert key_issue["severity"] == "CRITICAL"


def test_linter_detects_hardcoded_openai_key(tmp_path: Path):
    cfg_file = tmp_path / "ai_client.ts"
    cfg_file.write_text('const apiKey = "sk-1234567890abcdef12345678901234";\n', encoding="utf-8")

    linter = PolyglotQualityLinter(workspace_root=tmp_path)
    issues = linter.audit_workspace(include_tests=True)

    openai_issue = next((i for i in issues if "OpenAI" in i["rule"]), None)
    assert openai_issue is not None
    assert openai_issue["severity"] == "CRITICAL"


def test_linter_detects_unsafe_eval(tmp_path: Path):
    bad_code = tmp_path / "unsafe.py"
    bad_code.write_text('res = eval("2 + 2")\n', encoding="utf-8")

    linter = PolyglotQualityLinter(workspace_root=tmp_path)
    issues = linter.audit_workspace(include_tests=True)

    eval_issue = next((i for i in issues if "eval" in i["rule"].lower()), None)
    assert eval_issue is not None
    assert eval_issue["severity"] == "HIGH"


def test_linter_detects_unsafe_shell_subprocess(tmp_path: Path):
    bad_proc = tmp_path / "shell.py"
    bad_proc.write_text('import subprocess\nsubprocess.run(user_cmd, shell=True)\n', encoding="utf-8")

    linter = PolyglotQualityLinter(workspace_root=tmp_path)
    issues = linter.audit_workspace(include_tests=True)

    sub_issue = next((i for i in issues if "Subprocess Shell" in i["rule"]), None)
    assert sub_issue is not None
    assert sub_issue["severity"] == "HIGH"
