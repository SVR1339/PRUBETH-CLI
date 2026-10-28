"""Deep Matrix Tests for SecurityLinterTool detecting credentials, tokens, and injections."""

import pytest
from pathlib import Path
from prubeth.tools.domain.security_linter import SecurityLinterTool


@pytest.fixture
def linter():
    return SecurityLinterTool()


# =========================================================================
# Matrix: 10 Leaked Secret Varieties
# =========================================================================

SECRET_SAMPLES = [
    ("api_key = 'abcdef1234567890abcdef1234567890'", "SECRET", "HIGH"),
    ("AUTH_TOKEN = 'secret_bearer_token_1234567890'", "SECRET", "HIGH"),
    ("GEMINI_KEY = 'AIzaSyD-1234567890abcdefghijklmnopqrstuv'", "SECRET", "CRITICAL"),
    ("OPENAI_SECRET = 'sk-abcdef1234567890abcdef1234567890abcdef12'", "SECRET", "CRITICAL"),
    ("GH_TOKEN = 'ghp_1234567890abcdefghijklmnopqrstuvwxyz12'", "SECRET", "CRITICAL"),
    ("AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'", "SECRET", "CRITICAL"),
]

@pytest.mark.parametrize("line, expected_type, expected_sev", SECRET_SAMPLES)
def test_matrix_security_linter_detects_secrets(tmp_path: Path, linter, line, expected_type, expected_sev):
    f = tmp_path / "creds.py"
    f.write_text(f"# Configuration\n{line}\n", encoding="utf-8")

    res = linter.execute({"path": str(f)})
    assert res.success is False
    assert res.metadata["count"] >= 1
    finding = res.metadata["findings"][0]
    assert finding["type"] == expected_type
    assert finding["severity"] == expected_sev


# =========================================================================
# Matrix: 10 Vulnerable Code Patterns
# =========================================================================

VULNERABLE_PATTERNS = [
    ("val = eval(user_input)", "Dangerous eval() usage", "HIGH"),
    ("exec(dynamic_code)", "Dangerous exec() usage", "HIGH"),
    ("subprocess.run(cmd, shell=True)", "Subprocess shell=True injection risk", "MEDIUM"),
    ("h = hashlib.md5(pwd.encode())", "Weak cryptographic hash (MD5/SHA1)", "LOW"),
    ("query = 'SELECT * FROM users WHERE name = %s' % user", "Potential SQL string formatting injection", "HIGH"),
    ("sql = f'DELETE FROM items WHERE id = {item_id}'", "Potential SQL f-string injection", "HIGH"),
]

@pytest.mark.parametrize("line, expected_desc, expected_sev", VULNERABLE_PATTERNS)
def test_matrix_security_linter_detects_vulnerabilities(tmp_path: Path, linter, line, expected_desc, expected_sev):
    f = tmp_path / "vuln.py"
    f.write_text(f"# App logic\n{line}\n", encoding="utf-8")

    res = linter.execute({"path": str(f)})
    # Severity check
    assert res.metadata["count"] >= 1
    finding = res.metadata["findings"][0]
    assert finding["type"] == "VULNERABILITY"
    assert finding["severity"] == expected_sev
    assert expected_desc in finding["description"]


# =========================================================================
# Matrix: 10 Benign Code Patterns (Zero False Positives)
# =========================================================================

BENIGN_PATTERNS = [
    "api_key = os.getenv('GEMINI_API_KEY')",
    "token = config.get('auth_token')",
    "h = hashlib.sha256(data.encode())",
    "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
    "proc = subprocess.run(['git', 'status'], capture_output=True)",
    "evaluated_flag = True",
    "execute_query = db.query",
]

@pytest.mark.parametrize("line", BENIGN_PATTERNS)
def test_matrix_security_linter_zero_false_positives(tmp_path: Path, linter, line):
    f = tmp_path / "clean.py"
    f.write_text(f"# Production code\n{line}\n", encoding="utf-8")

    res = linter.execute({"path": str(f)})
    assert res.success is True
    assert res.metadata["count"] == 0
