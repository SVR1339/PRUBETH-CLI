import sys
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

def extract_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Extracts tool call JSON from Markdown blocks or raw text."""
    m = re.search(r"```(?:tool|json)?\s*(\{[\s\S]*?\})\s*```", text)
    if m:
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, dict) and ("tool" in parsed or "action" in parsed):
                return {
                    "tool": parsed.get("tool") or parsed.get("action"),
                    "args": parsed.get("args") or parsed.get("parameters") or {}
                }
        except Exception:
            pass

    start = text.find('{"tool"')
    if start == -1:
        start = text.find('{"action"')
    if start != -1:
        extracted = extract_json_object(text[start:])
        if extracted and ("tool" in extracted or "action" in extracted):
            return {
                "tool": extracted.get("tool") or extracted.get("action"),
                "args": extracted.get("args") or extracted.get("parameters") or {}
            }
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
        # Multi-turn conversational fluid history & compaction state (Claude Code Parity)
        self.fluid_history: List[Dict[str, Any]] = []
        # Frontier Prompt & Context Cache Lifecycle Manager (Gemini cachedContents & Claude Ephemeral)
        from prubeth.models.caching import ContextCacheManager
        self.cache_mgr = ContextCacheManager(workspace_root=self.workspace_root, config_manager=self.gateway.cfg_mgr, gateway=self.gateway)

    def _emit(self, event_name: str, payload: Any):
        if self.event_cb:
            self.event_cb(event_name, payload)
        if hasattr(self, "ide_bridge") and self.ide_bridge:
            try:
                self.ide_bridge.emit_event(event_name, payload)
            except Exception:
                pass

    def close(self):
        """Releases all open resources and databases."""
        if hasattr(self, "tool_engine") and self.tool_engine:
            try:
                self.tool_engine.close()
            except Exception:
                pass
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass
        if hasattr(self, "ide_bridge") and self.ide_bridge:
            try:
                self.ide_bridge.stop()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def chat(self, message: str, model_override: Optional[str] = None, stream_cb: Optional[Any] = None) -> GenerationResponse:
        """Executes a conversational, natural AI developer interaction with repository context and streaming."""
        active_model = model_override or self.config.model_name
        repo_skeleton = self.repo_intel.build_context_skeleton()

        system_prompt = (
            "You are PRUBETH, an elite principal software engineer and autonomous programming agent.\n"
            "Communicate with utmost technical clarity, precision, and conciseness using formal British English orthography (e.g., analyse, optimise, behaviour, synchronise, prioritised).\n"
            "Maintain an authoritative, direct, and rigorous tone. Omit all conversational preamble, pleasantries, apologies, and filler phrases.\n"
            "Respond directly and concisely in clean GitHub-flavoured Markdown.\n"
            "Do NOT output robotic internal state transitions, and do NOT split simple replies into Plan A / Plan B boxes.\n"
            "Use the provided workspace structure to give context-aware, insightful, and practical solutions.\n"
            "Every explanation must be mathematically sound, syntactically verified, and directly actionable."
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
            prefer_local=self.config.prefer_local_model,
            stream_cb=stream_cb
        )

    def run_fluid_turn(
        self,
        user_message: str,
        model_override: Optional[str] = None,
        stream_cb: Optional[Callable[[str], None]] = None,
        tool_cb: Optional[Callable[[str, Dict[str, Any], bool, str], None]] = None,
        max_tool_turns: int = 6
    ) -> Dict[str, Any]:
        """Unified Fluid ReAct Execution Engine (Claude Code-Grade Experience).
        
        Seamlessly streams thought and conversational answers directly to the user.
        Dynamically executes workspace tools (read_file, edit_file, write_file, run_command,
        code_search, resolve_symbol) inline without rigid multi-phase pipeline lock-in.
        """
        active_model = model_override or self.config.model_name
        repo_instructions = self.repo_intel.load_project_instructions()
        memory_ctx = self.memory.get_memory_context()

        # Secure background snapshot for zero-risk rollback
        snap_mgr = SnapshotManager(workspace_root=self.workspace_root)
        baseline_snap = snap_mgr.create_snapshot("fluid_turn_baseline")

        if not hasattr(self, "tool_engine") or not self.tool_engine:
            self.tool_engine = ToolExecutionEngine(self.security, self.db, "fluid_turn", mcp_mgr=self.mcp)

        system_prompt = (
            "You are PRUBETH, an elite principal software engineer and autonomous programming agent.\n"
            "Communicate with utmost technical clarity, precision, and conciseness using formal British English orthography (e.g., analyse, optimise, behaviour, synchronise, prioritised).\n"
            "Maintain an authoritative, direct, and rigorous tone. Omit all conversational preamble, pleasantries, apologies, and filler phrases.\n"
            "You have direct access to workspace tools (read_file, edit_file, write_file, run_command, grep_search, find_files, code_search, resolve_symbol, git_diff, find_symbol_references).\n"
            "Invoke tools proactively whenever necessary to inspect the repository, write code, run tests, or verify syntax.\n"
            "When reasoning or analysing, formulate concise, structured rationale before taking actions.\n"
            "If no tools are required, provide clean, exact solutions in GitHub-flavoured Markdown.\n"
            "Do NOT output robotic internal state transitions (CREATED, PLANNING) or unsolicited Plan A / Plan B boxes during fluid dialogue.\n"
            "Every explanation must be mathematically sound, syntactically verified, and directly actionable."
        )

        # Gemini CLI & Claude Code Tier-1 Environment Context Priming
        branch_name = "main"
        try:
            head_file = self.workspace_root / ".git" / "HEAD"
            if head_file.exists():
                ref = head_file.read_text(encoding="utf-8").strip()
                if ref.startswith("ref: refs/heads/"):
                    branch_name = ref.replace("ref: refs/heads/", "")
        except Exception:
            pass

        history_context = [
            f"Environment Context:\n- Workspace Root: {self.workspace_root}\n- Git Branch: {branch_name}\n- Platform: {sys.platform} (Python {sys.version.split()[0]})\n"
        ]
        if repo_instructions:
            history_context.append(f"Project Rules:\n{repo_instructions}\n")
        if memory_ctx:
            history_context.append(f"Learned Project Memory:\n{memory_ctx}\n")

        messages = []
        if self.fluid_history:
            for past_m in self.fluid_history[-6:]:
                messages.append({"role": past_m.get("role", "user"), "content": past_m.get("content", "")})

        initial_user_content = "\n\n".join(history_context + [f"Developer: {user_message}"])
        messages.append({"role": "user", "content": initial_user_content})
        tools_executed = []
        final_text = ""

        turn = 0
        while turn < max_tool_turns:
            turn += 1

            accumulated_tokens = []
            def chunk_streamer(token: str):
                accumulated_tokens.append(token)
                current_so_far = "".join(accumulated_tokens)
                if stream_cb and "```tool" not in current_so_far and '{"tool"' not in current_so_far:
                    stream_cb(token)

            # Automatic Google Gemini Context Caching (cachedContents REST lifecycle)
            gemini_cache_id = None
            resolved_m = self.gateway.cfg_mgr.resolve_model_and_provider(active_model)
            if resolved_m["provider"] == "google" and resolved_m.get("enable_context_caching", True):
                ws_ctx = "\n\n".join(history_context)
                gemini_cache_id = self.cache_mgr.get_or_create_gemini_session(
                    model=resolved_m["model"],
                    workspace_context=ws_ctx,
                    system_instruction=system_prompt,
                    tools=True
                )

            resp = self.gateway.generate(
                messages,
                system_instruction=system_prompt,
                model_name=active_model,
                model_tier="fast",
                prefer_local=self.config.prefer_local_model,
                stream_cb=chunk_streamer if stream_cb else None,
                tools=True,
                cached_content=gemini_cache_id
            )

            raw_resp = getattr(resp, "text", "") or ""
            raw_tool_calls = getattr(resp, "tool_calls", None)
            tool_calls = raw_tool_calls if isinstance(raw_tool_calls, list) else []

            # Robust fallback for text-based tool calls (mocks, offline local models)
            if not tool_calls and raw_resp:
                extracted = extract_tool_call(raw_resp)
                if extracted:
                    tool_calls = [{"id": f"call_{len(tools_executed)+1}", "name": extracted["tool"], "args": extracted.get("args", {})}]

            if not tool_calls:
                clean_tail = re.sub(r"```(?:tool|json)?[\s\S]*?```", "", raw_resp).strip()
                if clean_tail:
                    final_text = (final_text + "\n\n" + clean_tail).strip()
                elif raw_resp:
                    final_text = (final_text + "\n\n" + raw_resp).strip()
                break

            # Clean leading/trailing commentary text before tool
            display_text = re.sub(r"```(?:tool|json)?[\s\S]*?```", "", raw_resp).strip()
            if display_text and not accumulated_tokens:
                final_text = (final_text + "\n\n" + display_text).strip()

            # Record assistant turn in multi-turn structured message tree
            messages.append({
                "role": "assistant",
                "content": raw_resp,
                "tool_calls": tool_calls
            })

            # Execute tool calls
            for tc in tool_calls:
                t_id = tc.get("id", f"call_{len(tools_executed)+1}")
                t_name = tc.get("name", "")
                t_args = tc.get("args", {})

                if tool_cb:
                    tool_cb("invoking", {"tool": t_name, "args": t_args}, True, "")

                success, output = self.tool_engine.execute_tool(t_name, t_args, approval_cb=self.approval_cb)
                tools_executed.append({"tool": t_name, "args": t_args, "success": success, "output": output[:300]})

                if tool_cb:
                    tool_cb("result", {"tool": t_name, "args": t_args}, success, output)

                messages.append({
                    "role": "tool",
                    "tool_call_id": t_id,
                    "name": t_name,
                    "content": output[:4000]
                })

        # Record fluid turn into persistent multi-turn session history
        self.fluid_history.append({"role": "user", "content": user_message})
        asst_record: Dict[str, Any] = {"role": "assistant", "content": final_text or raw_resp}
        if tools_executed:
            asst_record["tools_summary"] = [f"{t['tool']}: {'OK' if t['success'] else 'ERR'}" for t in tools_executed]
        self.fluid_history.append(asst_record)

        return {
            "text": final_text or raw_resp,
            "tools_executed": tools_executed,
            "success": True,
            "snapshot_id": baseline_snap,
            "prompt_tokens": getattr(resp, "prompt_tokens", 0),
            "candidate_tokens": getattr(resp, "candidate_tokens", 0),
            "cached_tokens": getattr(resp, "cached_tokens", 0),
            "thinking_tokens": getattr(resp, "thinking_tokens", 0),
            "latency_s": getattr(resp, "latency_s", 0.0),
            "model": getattr(resp, "model", active_model or ""),
            "provider": getattr(resp, "provider", "")
        }

    def compact_history(self) -> Dict[str, Any]:
        """Compresses fluid conversation history to maintain pinned prefix KV cache and prevent bloat.
        
        Matches Claude Code /compact standard: prunes raw intermediate tool outputs,
        summarizes historical turns into an executive architectural scratchpad, and keeps
        recent context razor-sharp.
        """
        orig_turns = len(self.fluid_history)
        orig_chars = sum(len(str(m.get("content", ""))) for m in self.fluid_history)

        if not self.fluid_history:
            return {
                "original_turns": 0,
                "compacted_turns": 0,
                "original_chars": 0,
                "compacted_chars": 0,
                "tokens_saved_approx": 0,
                "summary": "No active conversation turns to compact."
            }

        # Synthesize compaction scratchpad from historical turns
        summary_lines = ["[PRUBETH Compacted Architectural Context & Historical Scratchpad]"]
        turn_idx = 1
        for i in range(0, len(self.fluid_history), 2):
            u_msg = self.fluid_history[i] if i < len(self.fluid_history) else {}
            a_msg = self.fluid_history[i+1] if i+1 < len(self.fluid_history) else {}
            u_text = str(u_msg.get("content", ""))[:200].replace("\n", " ")
            a_text = str(a_msg.get("content", ""))[:300].replace("\n", " ")
            tools_str = ""
            if "tools_summary" in a_msg:
                tools_str = f" | Tools: {', '.join(a_msg['tools_summary'])}"
            summary_lines.append(f"- Turn {turn_idx}: Dev: '{u_text}' -> Solution: {a_text}{tools_str}")
            turn_idx += 1

        compacted_content = "\n".join(summary_lines)
        self.fluid_history = [
            {"role": "user", "content": compacted_content},
            {"role": "assistant", "content": "Acknowledged. Historical context compacted and pinned. Ready for next instructions."}
        ]
        new_chars = sum(len(str(m.get("content", ""))) for m in self.fluid_history)
        tokens_saved = max(0, (orig_chars - new_chars) // 4)

        return {
            "original_turns": orig_turns,
            "compacted_turns": len(self.fluid_history),
            "original_chars": orig_chars,
            "compacted_chars": new_chars,
            "tokens_saved_approx": tokens_saved,
            "summary": compacted_content
        }

    def clear_history(self):
        """Resets fluid conversation history while preserving memory invariants and snapshots."""
        self.fluid_history.clear()

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
