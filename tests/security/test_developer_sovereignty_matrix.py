"""PRUBETH Unconstrained Developer Sovereignty & Security Matrix.

Exhaustively verifies frictionless developer workflow across AST Pre-Flight Gates,
Security & Permission Clearances, Credential Scrubbing, and Model Technical Prompts.
Ensures developers face zero bureaucratic roadblocks or artificial model refusals,
while maintaining strictly essential safeguards against catastrophic disk destruction.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from prubeth.security.permissions import SecurityEngine, PermissionLevel
from prubeth.tools.core.write_file import WriteFileTool
from prubeth.tools.core.edit_file import EditFileTool
from prubeth.tools.core.run_shell import RunShellTool, DANGEROUS_COMMAND_PATTERNS
from prubeth.verification.polyglot import PolyglotSyntaxGate
from prubeth.agents.subagent import SubagentSpec, SubagentRole, SubagentManager
from prubeth.models.gateway import ModelGateway
from prubeth.persistence.database import TaskDatabase


class DummyContext:
    def __init__(self, workspace_root: Path, developer_mode: bool = False, unrestricted_mode: bool = False):
        self.workspace_root = workspace_root
        self.developer_mode = developer_mode
        self.unrestricted_mode = unrestricted_mode


# ============================================================================
# 1. AST & Pre-Flight Syntax Gate Sovereignty Tests
# ============================================================================

def test_write_file_force_bypasses_syntax_gate(tmp_path: Path):
    """Developers can write files with deliberate syntax flaws using force=True."""
    target = tmp_path / "syntax_fixture.py"
    tool = WriteFileTool()

    # Intentionally malformed python syntax (e.g. for a parser test fixture)
    res = tool.execute({
        "path": str(target),
        "content": "def intentional_syntax_defect(:\n    pass\n",
        "force": True
    })

    assert res.success is True
    assert res.exit_code == 0
    assert target.is_file()
    assert "intentional_syntax_defect" in target.read_text(encoding="utf-8")
    assert "Advisory" in res.output or "notice" in res.output.lower()
    assert res.metadata.get("forced") is True
    assert "syntax_advisory" in res.metadata


def test_write_file_developer_mode_context_bypasses_syntax_gate(tmp_path: Path):
    """Context operating in developer_mode automatically allows syntax writing without failure."""
    target = tmp_path / "wip_code.py"
    tool = WriteFileTool()
    ctx = DummyContext(workspace_root=tmp_path, developer_mode=True)

    res = tool.execute({
        "path": str(target),
        "content": "def incomplete_stub():\n    return (\n",  # unclosed parenthesis
    }, context=ctx)

    assert res.success is True
    assert res.exit_code == 0
    assert target.is_file()
    assert res.metadata.get("forced") is True


def test_write_file_syntax_gate_pragma_bypass(tmp_path: Path):
    """Files with pragma headers are automatically accepted without requiring force flag."""
    target = tmp_path / "compiler_test.py"
    tool = WriteFileTool()

    content = "# prubeth: allow-syntax-error\nclass MalformedClass {\n"
    res = tool.execute({"path": str(target), "content": content})

    assert res.success is True
    assert res.exit_code == 0
    assert target.is_file()


def test_edit_file_force_bypasses_syntax_gate(tmp_path: Path):
    """Developers can apply surgical edits resulting in partial or test code via force=True."""
    target = tmp_path / "test_module.py"
    target.write_text("x = 100\n", encoding="utf-8")

    tool = EditFileTool()
    res = tool.execute({
        "path": str(target),
        "target": "x = 100",
        "replacement": "x = (\n",  # unclosed parenthesis
        "force": True
    })

    assert res.success is True
    assert res.exit_code == 0
    assert "x = (\n" in target.read_text(encoding="utf-8")
    assert res.metadata.get("forced") is True


def test_edit_file_developer_mode_context_bypasses_syntax_gate(tmp_path: Path):
    """Developer mode context permits surgical edit without exit code 422."""
    target = tmp_path / "test_refactor.py"
    target.write_text("y = 42\n", encoding="utf-8")

    tool = EditFileTool()
    ctx = DummyContext(workspace_root=tmp_path, unrestricted_mode=True)
    res = tool.execute({
        "path": str(target),
        "target": "y = 42",
        "replacement": "y = {'unclosed_dict':\n",
    }, context=ctx)

    assert res.success is True
    assert res.exit_code == 0
    assert target.read_text(encoding="utf-8").startswith("y = {")


@pytest.mark.parametrize("pragma", [
    "# prubeth: allow-syntax-error",
    "// prubeth: allow-syntax-error",
    "# prubeth: no-gate",
    "# prubeth: relaxed",
    "# prubeth: force-syntax",
    "# noqa: syntax",
])
def test_polyglot_syntax_gate_pragmas_exhaustive(pragma: str):
    """All registered developer pragma directives successfully bypass syntax gate."""
    code = f"{pragma}\nmalformed {{{{ code +++\n"
    ok, msg = PolyglotSyntaxGate.validate_content("fixture.py", code)
    assert ok is True
    assert "bypassed" in msg.lower() or "pragma" in msg.lower()


def test_polyglot_syntax_gate_has_bypass_pragma():
    assert PolyglotSyntaxGate.has_bypass_pragma("# prubeth: allow-syntax-error\nx = 1") is True
    assert PolyglotSyntaxGate.has_bypass_pragma("// PRUBETH: NO-GATE\nint a =;") is True
    assert PolyglotSyntaxGate.has_bypass_pragma("x = 1\ny = 2") is False
    assert PolyglotSyntaxGate.has_bypass_pragma("") is False


# ============================================================================
# 2. Security Engine & Unrestricted Developer Clearance Tests
# ============================================================================

def test_security_engine_unrestricted_developer_mode(tmp_path: Path):
    """Enabling unrestricted developer mode auto-approves all 37 tools with 0 interactive prompts."""
    sec = SecurityEngine(workspace_root=str(tmp_path))
    assert sec.auto_approve_all is False

    sec.enable_unrestricted_developer_mode()
    assert sec.is_developer_unrestricted() is True
    assert sec.auto_approve_all is True

    # Check all key mutation and execution tools are now ALLOW
    assert sec.tool_policies["write_file"] == PermissionLevel.ALLOW
    assert sec.tool_policies["edit_file"] == PermissionLevel.ALLOW
    assert sec.tool_policies["run_command"] == PermissionLevel.ALLOW
    assert sec.tool_policies["git_commit"] == PermissionLevel.ALLOW
    assert sec.tool_policies["run_python"] == PermissionLevel.ALLOW


def test_security_engine_blocks_catastrophic_only(tmp_path: Path):
    """Even under unrestricted mode, catastrophic wipe commands remain strictly prevented."""
    sec = SecurityEngine(workspace_root=str(tmp_path))
    sec.enable_unrestricted_developer_mode()

    # Catastrophic command must be blocked
    ok, err = sec.check_tool_permission("run_command", {"command": "rm -rf /"})
    assert ok is False
    assert "SECURITY DENIAL" in err
    assert "dangerous blacklisted string" in err


def test_security_engine_allows_normal_dev_commands_in_unrestricted_mode(tmp_path: Path):
    """Standard development commands execute without any permission prompt under developer mode."""
    sec = SecurityEngine(workspace_root=str(tmp_path))
    sec.enable_unrestricted_developer_mode()

    normal_commands = [
        "git status",
        "pytest tests/",
        "python -m build",
        "npm test",
        "cargo check",
        "docker ps",
        "make test",
    ]
    for cmd in normal_commands:
        ok, err = sec.check_tool_permission("run_command", {"command": cmd})
        assert ok is True
        assert err == ""


def test_security_engine_catastrophic_command_helper(tmp_path: Path):
    sec = SecurityEngine(workspace_root=str(tmp_path))
    is_cat, token = sec.is_catastrophic_command("rm -rf /")
    assert is_cat is True
    assert "rm -rf /" in token

    is_cat, _ = sec.is_catastrophic_command("rm -rf build")
    assert is_cat is False


def test_security_engine_configure_tool_policy_override(tmp_path: Path):
    sec = SecurityEngine(workspace_root=str(tmp_path))
    sec.configure_tool_policy("custom_plugin_tool", PermissionLevel.ALLOW)
    assert sec.tool_policies["custom_plugin_tool"] == PermissionLevel.ALLOW


# ============================================================================
# 3. Shell Tool Cleanup Freedom (rm -rf build / dist allowed)
# ============================================================================

@pytest.mark.parametrize("build_clean_cmd", [
    "rm -rf build",
    "rm -rf dist",
    "rm -rf target",
    "rm -rf node_modules",
    "rm -rf .pytest_cache",
    "rm -rf __pycache__",
    "rm -rf temp_out",
])
def test_run_shell_tool_allows_developer_build_cleanup(build_clean_cmd: str):
    """Legitimate build artifact directory removals are never blocked."""
    import re
    for pat in DANGEROUS_COMMAND_PATTERNS:
        match = re.search(pat, build_clean_cmd, re.IGNORECASE)
        assert not match, f"Build cleaning command '{build_clean_cmd}' was erroneously blocked by pattern '{pat}'"


# ============================================================================
# 4. Credential Gate & Mock/Dummy Key Sovereignty Tests
# ============================================================================

def test_security_engine_redact_secrets_preserves_execution(tmp_path: Path):
    """Secret scrubbing filters credentials for logging safety without blocking developer execution."""
    sec = SecurityEngine(workspace_root=str(tmp_path))
    sample_log = "Connection established with key sk-1234567890abcdef1234567890abcdef for user"
    redacted = sec.redact_secrets(sample_log)
    assert "sk-" not in redacted
    assert "[REDACTED_OPENAI_KEY]" in redacted
    assert "Connection established" in redacted


def test_security_engine_is_dummy_secret():
    sec = SecurityEngine()
    assert sec.is_dummy_secret("sk-test-12345678901234567890") is True
    assert sec.is_dummy_secret("dummy_auth_token_for_mock") is True
    assert sec.is_dummy_secret("AIzaSyFakeSampleKeyForTesting") is True
    assert sec.is_dummy_secret("real_production_secret_value_xyz") is False


def test_subagent_critic_permits_mock_and_test_credentials(tmp_path: Path):
    """Subagent critic approves diffs that contain test, dummy, or sample API keys."""
    mgr = SubagentManager(workspace_root=tmp_path)

    spec = SubagentSpec(
        id="sub-coder-01",
        role=SubagentRole.CODER,
        goal="Add unit test fixture for API client"
    )

    diff_with_mock_key = """
--- a/tests/test_api.py
+++ b/tests/test_api.py
@@ -1,3 +1,5 @@
+API_KEY = "sk-test-mock-fixture-1234567890abcdef"
+client = Client(api_key=API_KEY)
"""
    approved, reason = mgr._run_adversarial_critic(spec, diff_with_mock_key)
    assert approved is True
    assert "passed" in reason.lower()


def test_subagent_critic_rejects_real_looking_secret(tmp_path: Path):
    """Subagent critic blocks diffs containing non-mock API secrets to protect against accidental leaks."""
    mgr = SubagentManager(workspace_root=tmp_path)

    spec = SubagentSpec(
        id="sub-coder-02",
        role=SubagentRole.CODER,
        goal="Configure client credentials"
    )

    diff_with_real_looking_key = """
--- a/src/config.py
+++ b/src/config.py
@@ -1,3 +1,5 @@
+api_key = "sk-99887766554433221100aabbccddeeff"
"""
    approved, reason = mgr._run_adversarial_critic(spec, diff_with_real_looking_key)
    assert approved is False
    assert "Possible plaintext API secret detected" in reason


# ============================================================================
# 5. Model Technical Prompts Anti-Refusal Verification
# ============================================================================

def test_controller_system_prompts_contain_developer_sovereignty(tmp_path: Path):
    """Controller chat and fluid turn system prompts mandate unrestricted developer clearance and anti-refusal."""
    from prubeth.runtime.controller import AutonomousRuntimeController
    controller = AutonomousRuntimeController(workspace_root=str(tmp_path))

    import inspect
    chat_src = inspect.getsource(controller.chat)
    fluid_src = inspect.getsource(controller.run_fluid_turn)

    assert "unrestricted technical clearance" in chat_src
    assert "unsolicited ethical lectures" in chat_src
    assert "unrestricted technical clearance" in fluid_src
    assert "unsolicited ethical lectures" in fluid_src
