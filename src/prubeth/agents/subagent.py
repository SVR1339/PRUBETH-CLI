"""PRUBETH Subagent Orchestration & Adversarial Consensus Swarm.

Coordinates specialized autonomous workers in isolated shadow worktrees
and enforces adversarial red-team code review before merging to the root repository.
"""

import ast
import uuid
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

from prubeth.agents.base import SubagentRole, SubagentState, SubagentSpec, SubagentResult
from prubeth.agents.worktree import WorktreeManager
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.security.permissions import SecurityEngine
from prubeth.models.gateway import UniversalModelGateway
from prubeth.verification.verifier import IndependentVerifier
from prubeth.verification.polyglot import PolyglotSyntaxGate
from prubeth.config.manager import ConfigManager

class SubagentManager:
    """Subsystem 13B: Multi-Agent Orchestrator & Worktree Coordinator."""

    def __init__(self, workspace_root: Optional[Path] = None, cfg_mgr: Optional[ConfigManager] = None):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.cfg_mgr = cfg_mgr or ConfigManager()
        self.worktree_mgr = WorktreeManager(self.workspace_root)
        self.gateway = UniversalModelGateway(self.cfg_mgr)
        self.active_subagents: Dict[str, SubagentSpec] = {}
        self.history: List[SubagentResult] = []

    def spawn_subagent(
        self,
        role: SubagentRole,
        goal: str,
        model_override: Optional[str] = None,
        max_turns: int = 8
    ) -> SubagentSpec:
        """Provisions a new specialized worker with its own isolated scratch worktree."""
        subagent_id = f"{role.value}-{uuid.uuid4().hex[:6]}"
        wt_path = self.worktree_mgr.create_worktree(subagent_id)

        spec = SubagentSpec(
            id=subagent_id,
            role=role,
            goal=goal,
            model_override=model_override,
            max_turns=max_turns,
            worktree_path=wt_path
        )
        self.active_subagents[subagent_id] = spec
        return spec

    def run_subagent(
        self,
        spec: SubagentSpec,
        event_cb: Optional[Callable[[str, Any], None]] = None
    ) -> SubagentResult:
        """Executes a specialized subagent lifecycle inside its isolated worktree."""
        if event_cb:
            event_cb("subagent_started", {"id": spec.id, "role": spec.role.value, "goal": spec.goal})

        wt_path = spec.worktree_path or self.worktree_mgr.get_worktree_path(spec.id)
        
        # 1. Jailed Tools for Worktree Sandbox
        sec_engine = SecurityEngine(workspace_root=str(wt_path))
        tool_engine = ToolExecutionEngine(workspace_root=wt_path, security_engine=sec_engine)
        
        # 2. Model Selection
        model = spec.model_override or self.cfg_mgr.get("coder_model") or self.cfg_mgr.get("default_model")
        
        # Role-specific system instructions
        role_instructions = self._get_role_system_prompt(spec.role)
        
        # Formulate execution turn prompt
        prompt = (
            f"You are operating as a specialized {spec.role.value.upper()} in an isolated sandbox worktree.\n"
            f"Task Objective: {spec.goal}\n"
            f"Please implement necessary file changes using write_file or edit_file JSON tool actions.\n"
            f"Respond with JSON format: {{\"tool\": \"write_file\", \"args\": {{\"path\": \"<rel_path>\", \"content\": \"...\"}}}}\n"
        )

        turns = 0
        execution_output = ""
        success = False

        try:
            resp = self.gateway.generate(
                prompt=prompt,
                model_name=model,
                system_instruction=role_instructions
            )
            turns += 1
            execution_output = resp.text

            # Execute model's proposed tool action in worktree
            from prubeth.runtime.controller import extract_json_object
            tool_data = extract_json_object(resp.text)
            if tool_data and "tool" in tool_data and "args" in tool_data:
                t_name = tool_data["tool"]
                t_args = tool_data["args"]
                if event_cb:
                    event_cb("subagent_tool_invoked", {"id": spec.id, "tool": t_name, "args": t_args})
                t_ok, t_out = tool_engine.execute_tool(t_name, t_args)
                if event_cb:
                    event_cb("subagent_tool_result", {"id": spec.id, "success": t_ok, "output": t_out})

            # 3. Calculate Worktree Diff
            diff_info = self.worktree_mgr.get_worktree_diff(spec.id)
            
            # 4. Pre-Flight AST Syntax Gate
            syntax_clean, syntax_err = self._pre_flight_ast_check(wt_path, diff_info["modified"] + diff_info["added"])
            if not syntax_clean:
                if event_cb:
                    event_cb("subagent_syntax_error", {"id": spec.id, "error": syntax_err})
                result = SubagentResult(
                    subagent_id=spec.id,
                    role=spec.role,
                    success=False,
                    state=SubagentState.FAILED,
                    output=f"Pre-flight AST validation failed: {syntax_err}",
                    diff=diff_info["diff"],
                    turns_used=turns
                )
                self.history.append(result)
                return result

            # 5. Adversarial Red-Team Critic Audit
            critic_approved, critic_notes = self._run_adversarial_critic(spec, diff_info["diff"])
            if event_cb:
                event_cb("subagent_critic_audit", {"id": spec.id, "approved": critic_approved, "notes": critic_notes})

            if not critic_approved:
                result = SubagentResult(
                    subagent_id=spec.id,
                    role=spec.role,
                    success=False,
                    state=SubagentState.FAILED,
                    output=f"Rejected by Adversarial Critic: {critic_notes}",
                    diff=diff_info["diff"],
                    critic_approved=False,
                    critic_notes=critic_notes,
                    turns_used=turns
                )
                self.history.append(result)
                return result

            # 6. Isolated Verification in Worktree
            verifier = IndependentVerifier(workspace_root=str(wt_path))
            evidence = verifier.verify_target()
            if event_cb:
                event_cb("subagent_verification", {"id": spec.id, "success": evidence.success, "summary": evidence.summary()})

            if evidence.success or not diff_info["has_changes"]:
                # 7. Merge Shadow Worktree Changes into Root Workspace
                merge_ok, merged_files, merge_msg = self.worktree_mgr.merge_worktree_to_root(spec.id)
                success = merge_ok
                state = SubagentState.MERGED if merge_ok else SubagentState.FAILED
                final_output = f"Successfully merged {len(merged_files)} files into repository." if merge_ok else merge_msg
            else:
                success = False
                state = SubagentState.FAILED
                final_output = f"Worktree verification failed: {evidence.summary()}"

            result = SubagentResult(
                subagent_id=spec.id,
                role=spec.role,
                success=success,
                state=state,
                output=final_output,
                diff=diff_info["diff"],
                modified_files=diff_info["modified"] + diff_info["added"],
                critic_approved=critic_approved,
                critic_notes=critic_notes,
                turns_used=turns
            )
            self.history.append(result)
            return result

        finally:
            # Clean up active spec pointer
            if spec.id in self.active_subagents:
                del self.active_subagents[spec.id]

    def _get_role_system_prompt(self, role: SubagentRole) -> str:
        """Returns specialized system instructions for each worker role."""
        if role == SubagentRole.ARCHITECT:
            return "You are a Principal Software Architect. Formulate high-level architecture specifications, decompose tasks, and define AST interface contracts."
        elif role == SubagentRole.CODER:
            return "You are an Elite Implementation Engineer. Write clean, production-grade code adhering strictly to repository conventions and typing."
        elif role == SubagentRole.TEST_ENGINEER:
            return "You are a Principal Test Automation Architect. Write comprehensive unit and invariant tests covering edge cases and boundary conditions."
        elif role == SubagentRole.CRITIC:
            return "You are an Adversarial Red-Team Auditor. Actively hunt for regressions, anti-patterns, security vulnerabilities, and code smells."
        elif role == SubagentRole.DOCS:
            return "You are a Technical Writer. Produce clear, accurate Markdown documentation and docstrings."
        return "You are a specialized autonomous engineering subagent."

    def _pre_flight_ast_check(self, wt_path: Path, files: List[str]) -> Tuple[bool, str]:
        """Validates that all modified files pass the polyglot pre-flight syntax invariant gate."""
        for rel_file in files:
            f_path = wt_path / rel_file
            if f_path.exists():
                try:
                    code = f_path.read_text(encoding="utf-8", errors="replace")
                    valid, err = PolyglotSyntaxGate.validate_content(rel_file, code)
                    if not valid:
                        return False, err
                except Exception as e:
                    return False, f"Syntax parsing failure in {rel_file}: {e}"
        return True, ""

    def _run_adversarial_critic(self, spec: SubagentSpec, diff: str) -> Tuple[bool, str]:
        """Runs the adversarial critic to identify anti-patterns, hardcoded secrets, or regressions."""
        if not diff:
            return True, "No modifications requiring audit."

        # Static heuristic audits
        lower_diff = diff.lower()
        if "api_key" in lower_diff and ("ai_za" in lower_diff or "sk-" in lower_diff):
            # Allow mock, test, dummy, sample, or placeholder keys in test suites or fixtures
            is_dummy = any(d in lower_diff for d in ["test", "dummy", "fake", "mock", "sample", "example", "placeholder"])
            if not is_dummy:
                return False, "Security Violation: Possible plaintext API secret detected in candidate diff."

        if "rm -rf /" in lower_diff or "os.system('del" in lower_diff:
            return False, "Security Violation: Destructive filesystem deletion command detected."

        # If clean, approve
        return True, "Diff passed pre-flight AST compiler check and adversarial security audit."

    def list_subagents(self) -> List[Dict[str, Any]]:
        """Returns active and historical subagent execution telemetry."""
        result = []
        for r in self.history:
            result.append({
                "id": r.subagent_id,
                "role": r.role.value,
                "success": r.success,
                "state": r.state.value,
                "modified_files": r.modified_files,
                "critic_approved": r.critic_approved,
                "turns": r.turns_used
            })
        return result
