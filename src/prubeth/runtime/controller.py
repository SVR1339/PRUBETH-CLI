import os
import uuid
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

from prubeth.runtime.state_machine import TaskStateMachine, TaskState
from prubeth.persistence.database import TaskDatabase
from prubeth.persistence.checkpoints import SnapshotManager
from prubeth.security.permissions import SecurityEngine
from prubeth.tools.execution import ToolExecutionEngine
from prubeth.repository.intelligence import RepositoryIntelligence
from prubeth.verification.verifier import IndependentVerifier, VerificationEvidence
from prubeth.models.gateway import UniversalModelGateway, GenerationResponse
from prubeth.persistence.memory import MemoryVault
from prubeth.agents.subagent import SubagentManager
from prubeth.integrations.ide_bridge import IDEBridgeServer
from prubeth.mcp.manager import MCPManager

@dataclass
class RuntimeConfig:
    max_execution_turns: int = 10
    max_recovery_attempts: int = 3
    auto_approve_actions: bool = False
    prefer_local_model: bool = False
    model_name: Optional[str] = None
    speculative_plan_b: bool = True
    auto_checkpoint: bool = True
    auto_rollback_on_failure: bool = True
    plan_b_strategy: str = "auto_pivot"  # auto_pivot | fallback_model | ask_developer

def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extracts the first valid JSON object from LLM response text."""
    clean = text.strip()
    try:
        return json.loads(clean)
    except Exception:
        pass

    # Look for ```json ... ``` blocks
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except Exception:
            pass

    # Match balanced braces
    start = text.find("{")
    if start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if not in_string:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except Exception:
                            pass
                        break
    return None

class AutonomousRuntimeController:
    """Subsystem 2: Elite Autonomous Runtime Controller with Plan B & Auto-Rollback."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        config: Optional[RuntimeConfig] = None,
        approval_cb: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
        event_cb: Optional[Callable[[str, Any], None]] = None
    ):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.config = config or RuntimeConfig()
        self.approval_cb = approval_cb
        self.event_cb = event_cb

        # Initialize Core Subsystems
        self.db = TaskDatabase(str(self.workspace_root / ".prubeth" / "prubeth.db"))
        self.security = SecurityEngine(workspace_root=str(self.workspace_root), auto_approve_all=self.config.auto_approve_actions)
        self.repo_intel = RepositoryIntelligence(workspace_root=str(self.workspace_root))
        self.verifier = IndependentVerifier(workspace_root=str(self.workspace_root))
        self.gateway = UniversalModelGateway()
        
        # Subsystems 12, 13 & 15 (Phase 2) + Subsystem 16 (Phase 3)
        self.memory = MemoryVault(self.workspace_root / ".prubeth" / "memory")
        self.memory_vault = self.memory
        self.subagents = SubagentManager(self.workspace_root)
        self.subagent_mgr = self.subagents
        self.ide_bridge = IDEBridgeServer()
        self.mcp = MCPManager(self.workspace_root)

    def _emit(self, event_name: str, payload: Any):
        if self.event_cb:
            self.event_cb(event_name, payload)
        if hasattr(self, "ide_bridge") and self.ide_bridge:
            try:
                self.ide_bridge.emit_event(event_name, payload)
            except Exception:
                pass

    def chat(self, message: str, model_override: Optional[str] = None) -> GenerationResponse:
        """Executes a conversational, natural AI developer interaction with repository context."""
        active_model = model_override or self.config.model_name
        repo_skeleton = self.repo_intel.build_context_skeleton()

        system_prompt = (
            "You are PRUBETH, a friendly, sharp, and natural AI software engineering companion.\n"
            "You are pair-programming with the developer in their workspace.\n"
            "Respond naturally, conversationally, directly, and concisely in clean GitHub-flavored Markdown.\n"
            "Do NOT output robotic internal state transitions, and do NOT split simple replies into Plan A / Plan B boxes.\n"
            "Use the provided workspace structure to give context-aware, insightful, and practical answers.\n"
            "If the developer greets you or asks how you can help, give a warm, sharp greeting, briefly note their current project context, and invite them to specify what feature, bug fix, or code task they want to tackle."
        )

        user_prompt = (
            f"Repository Overview:\n{repo_skeleton}\n\n"
            f"Developer Message: {message}"
        )

        return self.gateway.generate(
            user_prompt,
            system_instruction=system_prompt,
            model_name=active_model,
            model_tier="fast",
            prefer_local=self.config.prefer_local_model
        )

    def _run_tool_turn_loop(
        self,
        fsm: TaskStateMachine,
        goal: str,
        plan_text: str,
        active_model: Optional[str],
        plan_label: str = "Plan A"
    ) -> List[str]:
        """Executes the autonomous tool action turn loop."""
        execution_history = []
        turn = 0
        while turn < self.config.max_execution_turns:
            turn += 1
            exec_prompt = (
                f"Goal: {goal}\nActive Strategy ({plan_label}):\n{plan_text}\n"
                f"Turn: {turn}/{self.config.max_execution_turns}\n"
                f"Execution History:\n" + "\n".join(execution_history[-5:]) + "\n"
                "Propose the next tool action as valid JSON: {\"tool\": \"<name>\", \"args\": {<args>}}.\n"
                "Available tools: read_file, write_file, edit_file, run_command, grep_search, find_files, git_diff.\n"
                "If you are finished modifying files and ready for verification, output: {\"tool\": \"ready_for_verification\", \"args\": {}}"
            )
            
            resp = self.gateway.generate(exec_prompt, model_name=active_model, model_tier="fast", prefer_local=self.config.prefer_local_model)
            action_text = resp.text.strip()

            action = extract_json_object(action_text)
            if not action or "tool" not in action:
                execution_history.append(f"Model note: {action_text[:150]}")
                continue

            try:
                tool_name = action.get("tool")
                args = action.get("args", {})

                if tool_name == "ready_for_verification":
                    self._emit("executing_done", f"Model signaled implementation of {plan_label} complete. Proceeding to verification.")
                    break

                self._emit("tool_invoked", {"tool": tool_name, "args": args, "plan": plan_label, "turn": turn})
                success, result = self.tool_engine.execute_tool(tool_name, args, self.approval_cb)
                self._emit("tool_result", {"tool": tool_name, "success": success, "output": result[:300]})

                execution_history.append(f"Executed {tool_name}({args}) -> {'SUCCESS' if success else 'FAILURE'}: {result[:200]}")

            except Exception as ex:
                execution_history.append(f"Execution error on {action}: {ex}")

        return execution_history

    def run_task(self, goal: str, model_override: Optional[str] = None) -> Dict[str, Any]:
        """Executes the full autonomous engineering lifecycle with Plan B & Checkpoint recovery."""
        task_id = "task_" + str(uuid.uuid4())[:8]
        active_model = model_override or self.config.model_name
        self.snapshot_mgr = SnapshotManager(workspace_root=self.workspace_root, task_id=task_id)

        # 1. State: CREATED
        self.db.create_task(task_id, goal)
        fsm = TaskStateMachine(
            task_id=task_id,
            on_transition=lambda tid, f, t, r: self.db.update_task_state(tid, f.value, t.value, r)
        )
        self.tool_engine = ToolExecutionEngine(self.security, self.db, task_id, mcp_mgr=self.mcp)

        self._emit("state_change", TaskState.CREATED)

        try:
            # 2. State: CONTEXTUALIZING
            fsm.transition_to(TaskState.CONTEXTUALIZING, "Gathering repository architecture and project rules")
            self._emit("state_change", TaskState.CONTEXTUALIZING)
            
            repo_skeleton = self.repo_intel.build_context_skeleton()
            self._emit("context_gathered", repo_skeleton)

            # 3. State: PLANNING (Speculative Plan A & Plan B)
            fsm.transition_to(TaskState.PLANNING, "Generating structured technical implementation plan")
            self._emit("state_change", TaskState.PLANNING)

            plan_instructions = (
                "Produce an ordered, verifiable technical execution plan.\n"
                "If speculative_plan_b is enabled, provide two distinct plans:\n"
                "=== PLAN A (Primary Architecture) ===\n"
                "<Ordered steps, exact files to create/modify, acceptance criteria>\n\n"
                "=== PLAN B (Contingency Fallback Architecture) ===\n"
                "<Alternative architectural approach or simplified fallback if Plan A encounters blockers>"
                if self.config.speculative_plan_b
                else "Produce an ordered, verifiable technical execution plan with exact files to modify and acceptance criteria."
            )

            memory_context = self.memory.get_memory_context()
            memory_section = f"\n\nContinuous Project Memory & Learned Anti-Patterns:\n{memory_context}" if memory_context else ""

            planning_prompt = (
                f"You are the PRUBETH Principal Software Architect.\n"
                f"Repository Skeleton:\n{repo_skeleton}\n\n"
                f"Developer Goal: {goal}\n\n"
                f"{plan_instructions}"
                f"{memory_section}"
            )
            plan_resp = self.gateway.generate(planning_prompt, model_name=active_model, model_tier="reasoning", prefer_local=self.config.prefer_local_model)
            full_plan_text = plan_resp.text

            # Parse Plan A and Plan B robustly (supporting raw or markdown bold delimiters)
            plan_a = full_plan_text
            plan_b = ""
            if re.search(r"===\s*PLAN\s+B", full_plan_text, flags=re.IGNORECASE):
                parts = re.split(r"(?:•\s*)?\*{0,2}\s*===\s*PLAN\s+B.*?===\s*\*{0,2}:?", full_plan_text, maxsplit=1, flags=re.IGNORECASE)
                plan_a = re.sub(r"(?:•\s*)?\*{0,2}\s*===\s*PLAN\s+A.*?===\s*\*{0,2}:?", "", parts[0], flags=re.IGNORECASE).strip()
                if len(parts) > 1:
                    plan_b = parts[1].strip()

            self._emit("plan_generated", {
                "content": plan_a,
                "plan_b": plan_b,
                "has_plan_b": bool(plan_b),
                "model": plan_resp.model,
                "provider": plan_resp.provider,
                "latency_s": plan_resp.latency_s
            })

            # 4. State: READY
            if not self.config.auto_approve_actions and self.approval_cb:
                fsm.transition_to(TaskState.WAITING_FOR_APPROVAL, "Plan awaiting human sign-off")
                self._emit("state_change", TaskState.WAITING_FOR_APPROVAL)
                approved = self.approval_cb("plan_approval", {"plan": plan_a, "plan_b": plan_b})
                if not approved:
                    fsm.transition_to(TaskState.CANCELLED, "Developer rejected implementation plan")
                    return {"task_id": task_id, "success": False, "state": "CANCELLED", "message": "Plan rejected"}

            # Take clean initial snapshot before modifying workspace
            if self.config.auto_checkpoint:
                self.snapshot_mgr.create_snapshot("clean_initial_state")
                self._emit("snapshot_created", {"label": "clean_initial_state"})

            fsm.transition_to(TaskState.READY, "Plan approved; ready for execution")
            self._emit("state_change", TaskState.READY)

            # 5. State: EXECUTING (Plan A Tool Execution Loop)
            fsm.transition_to(TaskState.EXECUTING, "Executing Plan A code modifications and tools")
            self._emit("state_change", TaskState.EXECUTING)

            self._run_tool_turn_loop(fsm, goal, plan_a, active_model, plan_label="Plan A")

            # 6. State: VERIFYING (Deterministic Independent Verification)
            fsm.transition_to(TaskState.VERIFYING, "Running deterministic verification suite")
            self._emit("state_change", TaskState.VERIFYING)

            evidence = self.verifier.run_verification()
            self.db.record_verification(
                task_id=task_id,
                framework=evidence.framework,
                passed=evidence.tests_passed,
                failed=evidence.tests_failed,
                exit_code=evidence.exit_code,
                summary=evidence.summary()
            )
            self._emit("verification_result", evidence)

            # 7. Recovery Loop for Plan A
            recovery_attempts = 0
            while not evidence.success and recovery_attempts < self.config.max_recovery_attempts:
                recovery_attempts += 1
                if fsm.current_state != TaskState.RECOVERING:
                    fsm.transition_to(TaskState.RECOVERING, f"Plan A failure detected. Recovery attempt {recovery_attempts}/{self.config.max_recovery_attempts}")
                    self._emit("state_change", TaskState.RECOVERING)

                # Feed error traceback to model for fix
                fix_prompt = (
                    f"Test Verification FAILED on Plan A!\nFramework: {evidence.framework}\n"
                    f"Exit Code: {evidence.exit_code}\nFailures:\n" + "\n".join(evidence.unresolved_failures) + "\n\n"
                    f"Stderr:\n{evidence.stderr}\n\n"
                    "Diagnose the bug and output tool to patch the code: {\"tool\": \"write_file\"|\"edit_file\", \"args\": {...}}"
                )
                fix_resp = self.gateway.generate(fix_prompt, model_name=active_model, model_tier="fast", prefer_local=self.config.prefer_local_model)
                fix_action = extract_json_object(fix_resp.text)
                if fix_action and "tool" in fix_action:
                    try:
                        t_name = fix_action.get("tool")
                        t_args = fix_action.get("args", {})
                        self._emit("recovery_patch", {"tool": t_name, "args": t_args})
                        self.tool_engine.execute_tool(t_name, t_args, self.approval_cb)
                    except Exception:
                        pass

                fsm.transition_to(TaskState.VERIFYING, "Re-verifying post-recovery patch")
                self._emit("state_change", TaskState.VERIFYING)
                evidence = self.verifier.run_verification()
                self._emit("re_verification_result", evidence)

            # 8. Plan B Auto-Pivot (If Plan A Failed and Plan B is available)
            if not evidence.success and plan_b and self.config.speculative_plan_b and self.config.plan_b_strategy == "auto_pivot":
                self._emit("plan_b_activated", {
                    "reason": "Plan A failed verification after recovery attempts. Reverting workspace to initial snapshot and pivoting to Plan B.",
                    "plan_b": plan_b
                })
                # Revert workspace cleanly
                if self.config.auto_checkpoint:
                    self.snapshot_mgr.rollback_to_snapshot("clean_initial_state")
                    self._emit("workspace_rollback", {"target": "clean_initial_state"})

                fsm.transition_to(TaskState.EXECUTING, "Executing Plan B fallback architecture")
                self._emit("state_change", TaskState.EXECUTING)

                # Execute Plan B
                self._run_tool_turn_loop(fsm, goal, plan_b, active_model, plan_label="Plan B")

                # Verify Plan B
                fsm.transition_to(TaskState.VERIFYING, "Running verification on Plan B implementation")
                self._emit("state_change", TaskState.VERIFYING)
                evidence = self.verifier.run_verification()
                self._emit("verification_result", evidence)

            # 9. Terminal State & Safety Rollback on Total Failure
            if evidence.success:
                fsm.transition_to(TaskState.COMPLETED, "All tests and acceptance criteria verified green")
                self._emit("state_change", TaskState.COMPLETED)
                return {
                    "task_id": task_id,
                    "success": True,
                    "state": TaskState.COMPLETED.value,
                    "evidence": evidence.summary(),
                    "tests_passed": evidence.tests_passed,
                }
            else:
                # Revert broken files if auto_rollback is enabled
                if self.config.auto_rollback_on_failure and self.config.auto_checkpoint:
                    self.snapshot_mgr.rollback_to_snapshot("clean_initial_state")
                    self._emit("workspace_rollback", {"target": "clean_initial_state", "reason": "Total task failure safety rollback"})

                fsm.transition_to(TaskState.FAILED, f"Tests failed after recovery attempts and Plan B")
                self._emit("state_change", TaskState.FAILED)
                return {
                    "task_id": task_id,
                    "success": False,
                    "state": TaskState.FAILED.value,
                    "unresolved_failures": evidence.unresolved_failures,
                }

        except Exception as e:
            if self.config.auto_rollback_on_failure and self.config.auto_checkpoint and hasattr(self, "snapshot_mgr"):
                try:
                    self.snapshot_mgr.rollback_to_snapshot("clean_initial_state")
                except Exception:
                    pass
            fsm.transition_to(TaskState.FAILED, f"Fatal runtime exception: {str(e)}")
            self._emit("state_change", TaskState.FAILED)
            return {"task_id": task_id, "success": False, "state": "FAILED", "error": str(e)}
