"""PRUBETH Precision Agent Stagnation & Infinite Loop Detector.

Detects cyclic or repetitive tool calls, oscillation patterns, no-op mutations,
and text generation stagnation during autonomous ReAct execution loops.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set


@dataclass
class StagnationReport:
    is_stalled: bool
    reason: str = ""
    cycle_length: int = 0
    consecutive_repetitions: int = 0
    suggested_action: str = ""  # "continue", "inject_feedback", "abort"
    oscillation_pattern: List[str] = field(default_factory=list)
    corrective_prompt: Optional[str] = None


class StagnationDetector:
    """Monitors autonomous agent execution turns to detect infinite or unproductive loops."""

    def __init__(self, max_consecutive_same: int = 3, max_cycle_window: int = 8):
        self.max_consecutive_same = max_consecutive_same
        self.max_cycle_window = max_cycle_window
        self._call_history: List[str] = []
        self._text_hashes: List[str] = []

    def record_tool_call(self, tool_name: str, args: Dict[str, Any]) -> StagnationReport:
        """Records an invoked tool call and checks for stagnation loops."""
        call_repr = f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
        call_hash = hashlib.md5(call_repr.encode("utf-8")).hexdigest()[:12]
        self._call_history.append(call_hash)

        # 1. Check for immediate consecutive repetitions of identical tool call (e.g. read_file -> read_file -> read_file)
        if len(self._call_history) >= self.max_consecutive_same:
            last_n = self._call_history[-self.max_consecutive_same:]
            if len(set(last_n)) == 1:
                return StagnationReport(
                    is_stalled=True,
                    reason=f"Tool '{tool_name}' invoked {self.max_consecutive_same} times with identical arguments.",
                    consecutive_repetitions=self.max_consecutive_same,
                    suggested_action="inject_feedback"
                )

        # 2. Check for cyclic loops (e.g. tool A -> tool B -> tool A -> tool B)
        h_len = len(self._call_history)
        for cycle_len in range(2, min(self.max_cycle_window + 1, h_len // 2 + 1)):
            pattern1 = self._call_history[-cycle_len:]
            pattern2 = self._call_history[-2 * cycle_len : -cycle_len]
            if pattern1 == pattern2:
                # If repeated twice consecutively
                return StagnationReport(
                    is_stalled=True,
                    reason=f"Cyclic repetition detected: repeating a pattern of {cycle_len} tool calls.",
                    cycle_length=cycle_len,
                    suggested_action="inject_feedback"
                )

        return StagnationReport(is_stalled=False, suggested_action="continue")

    def record_text_output(self, text: str) -> StagnationReport:
        """Detects if model emits identical text responses repeatedly."""
        clean = " ".join(text.strip().split())
        if not clean:
            return StagnationReport(is_stalled=False, suggested_action="continue")

        thash = hashlib.md5(clean.encode("utf-8")).hexdigest()[:12]
        self._text_hashes.append(thash)

        if len(self._text_hashes) >= 3:
            if self._text_hashes[-1] == self._text_hashes[-2] == self._text_hashes[-3]:
                return StagnationReport(
                    is_stalled=True,
                    reason="Model produced 3 identical text responses in a row without making progress.",
                    consecutive_repetitions=3,
                    suggested_action="abort"
                )

        return StagnationReport(is_stalled=False, suggested_action="continue")

    def reset(self) -> None:
        """Resets the history tracking buffer."""
        self._call_history.clear()
        self._text_hashes.clear()


@dataclass
class ToolExecutionRecord:
    tool_name: str
    args: Dict[str, Any]
    success: bool
    exit_code: int
    output_hash: str
    call_hash: str


class StagnationInterceptor(StagnationDetector):
    """Advanced runtime interceptor that computes semantic tool argument similarity,
    monitors ping-pong file modifications, and synthesizes structured steering prompts.
    """

    def __init__(
        self,
        max_consecutive_same: int = 3,
        max_cycle_window: int = 10,
        max_repeated_failures: int = 3,
        similarity_threshold: float = 0.65
    ):
        super().__init__(max_consecutive_same=max_consecutive_same, max_cycle_window=max_cycle_window)
        self.max_repeated_failures = max_repeated_failures
        self.similarity_threshold = similarity_threshold
        self.records: List[ToolExecutionRecord] = []
        self._edited_file_hashes: Dict[str, List[str]] = {}

    def intercept_execution(
        self,
        tool_name: str,
        args: Dict[str, Any],
        success: bool = True,
        exit_code: int = 0,
        output_snippet: str = ""
    ) -> StagnationReport:
        """Records full execution telemetry and assesses multi-vector stagnation."""
        call_repr = f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
        call_hash = hashlib.sha256(call_repr.encode("utf-8")).hexdigest()[:16]
        out_hash = hashlib.sha256(output_snippet.encode("utf-8")).hexdigest()[:16]

        record = ToolExecutionRecord(
            tool_name=tool_name,
            args=args,
            success=success,
            exit_code=exit_code,
            output_hash=out_hash,
            call_hash=call_hash,
        )
        self.records.append(record)

        target_path = str(args.get("path") or args.get("file_path") or "")
        target_str = str(args.get("target") or "")
        repl_str = str(args.get("replacement") or args.get("content") or args.get("text") or "")

        # 1. No-Op File Modification Check
        if tool_name in ("edit_file", "write_file") and tool_name == "edit_file" and target_str == repl_str and target_str:
            return StagnationReport(
                is_stalled=True,
                reason=f"No-op edit detected on '{target_path}': target and replacement are identical.",
                suggested_action="inject_feedback",
                corrective_prompt=self.synthesize_steering_prompt(
                    f"Your edit on '{target_path}' had target == replacement. Provide actual modifications or proceed to testing."
                )
            )

        # 2. Ping-Pong File Modification Oscillation
        if tool_name in ("write_file", "edit_file") and target_path:
            content_sig = hashlib.md5(repl_str.encode("utf-8")).hexdigest()[:8]
            history = self._edited_file_hashes.setdefault(target_path, [])
            history.append(content_sig)
            if len(history) >= 4 and history[-1] == history[-3] and history[-2] == history[-4]:
                return StagnationReport(
                    is_stalled=True,
                    reason=f"Ping-pong oscillation detected on file '{target_path}': alternating between two conflicting revisions.",
                    cycle_length=2,
                    suggested_action="inject_feedback",
                    oscillation_pattern=[history[-2], history[-1]],
                    corrective_prompt=self.synthesize_steering_prompt(
                        f"File '{target_path}' is oscillating between two versions. Step back, re-verify the contract, and choose a stable implementation."
                    )
                )

        # 3. Repeated failure loop (same tool failing N times)
        if not success:
            fail_streak = 0
            for r in reversed(self.records):
                if not r.success and r.tool_name == tool_name:
                    fail_streak += 1
                else:
                    break
            if fail_streak >= self.max_repeated_failures:
                return StagnationReport(
                    is_stalled=True,
                    reason=f"Tool '{tool_name}' failed {fail_streak} consecutive times.",
                    consecutive_repetitions=fail_streak,
                    suggested_action="inject_feedback",
                    corrective_prompt=self.synthesize_steering_prompt(
                        f"Repeated tool execution failure in '{tool_name}'. Stop repeating this command and re-examine error messages."
                    )
                )

        # 4. Base check (identical call hashing / cycles)
        base_report = self.record_tool_call(tool_name, args)
        if base_report.is_stalled:
            base_report.corrective_prompt = self.synthesize_steering_prompt(
                f"Repeated identical tool invocation: {base_report.reason}"
            )
            return base_report

        # 5. Argument Jaccard Similarity Stagnation
        if len(self.records) >= 3:
            recent_same_tool = [r for r in self.records[-4:] if r.tool_name == tool_name]
            if len(recent_same_tool) >= 3:
                sim1 = self._args_similarity(recent_same_tool[-1].args, recent_same_tool[-2].args)
                sim2 = self._args_similarity(recent_same_tool[-2].args, recent_same_tool[-3].args)
                if sim1 >= self.similarity_threshold and sim2 >= self.similarity_threshold:
                    return StagnationReport(
                        is_stalled=True,
                        reason=f"Tool '{tool_name}' invoked 3 times with near-identical arguments (similarity: {sim1:.2f}).",
                        consecutive_repetitions=3,
                        suggested_action="inject_feedback",
                        corrective_prompt=self.synthesize_steering_prompt(
                            f"You are tweaking near-identical parameters for '{tool_name}'. Stop micro-tweaking and verify test output directly."
                        )
                    )

        return StagnationReport(is_stalled=False, suggested_action="continue")

        return StagnationReport(is_stalled=False, suggested_action="continue")

    def synthesize_steering_prompt(self, context: str) -> str:
        """Generates an assertive steering message to guide the model out of the loop."""
        return (
            f"[PRUBETH STAGNATION INTERCEPTOR]\n"
            f"Alert: {context}\n"
            f"Mandatory Action:\n"
            f"1. Stop repeating the current action.\n"
            f"2. Inspect the latest error message or test failure diagnostics carefully.\n"
            f"3. Switch to a diagnostic tool (e.g. read_file, grep_search, find_callers) or reformulate your approach.\n"
        )

    def _args_similarity(self, a: Dict[str, Any], b: Dict[str, Any]) -> float:
        """Computes Jaccard key-value similarity between two argument dictionaries."""
        def flatten(d: Dict[str, Any]) -> Set[str]:
            items = set()
            for k, v in d.items():
                items.add(f"{k}={str(v)[:100]}")
            return items

        set_a = flatten(a)
        set_b = flatten(b)
        if not set_a and not set_b:
            return 1.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    def reset(self) -> None:
        super().reset()
        self.records.clear()
        self._edited_file_hashes.clear()
