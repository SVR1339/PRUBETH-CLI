"""PRUBETH Autonomous Healing, Stagnation Detection & Contract FSM Matrix.

Exhaustively verifies:
1. StagnationDetector & StagnationInterceptor:
   - Consecutive identical tool call interception across varying thresholds.
   - Cyclic multi-step tool call sequence detection (2-cycle, 3-cycle, 4-cycle).
   - Identical model text response loop detection.
   - No-op edit prevention (target == replacement).
   - Ping-pong file modification oscillation detection across competing revisions.
   - Steering prompt synthesis and history clearing.
2. ASTContractGate & Interface Invariant Checking:
   - Detection of removed functions, methods, and classes.
   - Detection of added required parameters without defaults (breaking caller contracts).
   - Detection of return type modifications and signature drift.
   - Polyglot interface contracts (TypeScript, Go, Rust).
   - Remediation advice synthesis and error classification.
3. TaskStateMachine:
   - Valid lifecycle state transitions from CREATED through COMPLETED.
   - Terminal state immutability (COMPLETED, CANCELLED cannot transition).
   - Rejection of illegal state transitions with StateMachineError.
   - Transition callbacks and comprehensive timestamped history tracking.
"""

from __future__ import annotations

import pytest

from prubeth.runtime.stagnation import (
    StagnationDetector,
    StagnationInterceptor,
    StagnationReport,
)
from prubeth.runtime.contract import (
    ASTContractGate,
    BreakingChangeSeverity,
    ContractVerificationResult,
)
from prubeth.runtime.state_machine import (
    TaskState,
    TaskStateMachine,
    StateMachineError,
)


# ============================================================================
# 1. StagnationDetector: Consecutive Repetitions & Cycles
# ============================================================================

CONSECUTIVE_TOOL_CALL_CASES = [
    ("read_file", {"path": "src/main.py"}, 3, 3, True),
    ("read_file", {"path": "src/main.py"}, 2, 3, False),
    ("run_shell", {"command": "pytest"}, 3, 3, True),
    ("run_shell", {"command": "pytest"}, 4, 3, True),
    ("grep_search", {"pattern": "TODO"}, 3, 3, True),
    ("write_file", {"path": "a.txt", "content": "1"}, 3, 3, True),
    ("edit_file", {"path": "b.txt", "target": "x", "replacement": "y"}, 3, 3, True),
    ("git_status", {}, 3, 3, True),
    ("list_dir", {"path": "."}, 3, 3, True),
    ("read_file", {"path": "config.json"}, 5, 5, True),
    ("read_file", {"path": "config.json"}, 2, 5, False),
    ("run_python", {"code": "print(1)"}, 2, 2, True),
    ("run_python", {"code": "print(1)"}, 1, 2, False),
    ("code_structure", {"path": "src"}, 3, 3, True),
    ("find_dead_code", {"path": "src"}, 3, 3, True),
]

@pytest.mark.parametrize("tool_name,args,call_count,max_same,expected_stalled", CONSECUTIVE_TOOL_CALL_CASES)
def test_stagnation_detector_consecutive_calls(tool_name: str, args: dict, call_count: int, max_same: int, expected_stalled: bool):
    detector = StagnationDetector(max_consecutive_same=max_same)
    last_report = StagnationReport(is_stalled=False)
    for _ in range(call_count):
        last_report = detector.record_tool_call(tool_name, args)
    assert last_report.is_stalled is expected_stalled
    if expected_stalled:
        assert "identical arguments" in last_report.reason or tool_name in last_report.reason


CYCLIC_TOOL_CALL_PATTERNS = [
    # 2-cycle repeated twice: A, B, A, B
    ([("read_file", {"path": "a.py"}), ("run_shell", {"command": "pytest"})] * 2, 2, True),
    # 2-cycle only once: A, B
    ([("read_file", {"path": "a.py"}), ("run_shell", {"command": "pytest"})], 2, False),
    # 3-cycle repeated twice: A, B, C, A, B, C
    ([("read_file", {"path": "a.py"}), ("edit_file", {"path": "a.py", "target": "x", "replacement": "y"}), ("run_shell", {"command": "pytest"})] * 2, 3, True),
    # 4-cycle repeated twice: A, B, C, D, A, B, C, D
    ([("git_status", {}), ("read_file", {"path": "b.py"}), ("write_file", {"path": "b.py", "content": "c"}), ("run_shell", {"command": "pytest"})] * 2, 4, True),
    # Non-cyclic alternating calls
    ([("read_file", {"path": "a.py"}), ("read_file", {"path": "b.py"}), ("read_file", {"path": "c.py"})], 0, False),
    # 2-cycle repeated three times: A, B, A, B, A, B
    ([("grep_search", {"pattern": "foo"}), ("list_dir", {"path": "src"})] * 3, 2, True),
    # Distinct calls with varying args
    ([("read_file", {"path": f"f_{i}.py"}) for i in range(8)], 0, False),
    # 2-cycle with write and test
    ([("write_file", {"path": "x.py", "content": "1"}), ("run_shell", {"command": "python x.py"})] * 2, 2, True),
    # 3-cycle with check, type, lint
    ([("lint_checker", {"path": "a.py"}), ("type_checker", {"path": "a.py"}), ("patch_verifier", {"path": "a.py", "target": "1", "replacement": "2"})] * 2, 3, True),
    # Single call
    ([("read_file", {"path": "single.py"})], 0, False),
]

@pytest.mark.parametrize("call_sequence,expected_cycle_len,expected_stalled", CYCLIC_TOOL_CALL_PATTERNS)
def test_stagnation_detector_cyclic_patterns(call_sequence: list, expected_cycle_len: int, expected_stalled: bool):
    detector = StagnationDetector(max_cycle_window=8)
    last_report = StagnationReport(is_stalled=False)
    for tool_name, args in call_sequence:
        last_report = detector.record_tool_call(tool_name, args)
    assert last_report.is_stalled is expected_stalled
    if expected_stalled:
        assert last_report.cycle_length == expected_cycle_len


TEXT_OUTPUT_STAGNATION_CASES = [
    (["I will read the file now."] * 3, True),
    (["I will read the file now."] * 2, False),
    (["I will read the file now.", "Next I will run pytest.", "All tests pass."], False),
    (["Fixing bug in auth module."] * 4, True),
    (["", "   ", "\n\n"], False),
    (["Let me check the logs."] * 3, True),
    (["Step 1", "Step 2", "Step 1", "Step 2"], False),
    (["Generating patch..."] * 3, True),
    (["Done."] * 5, True),
    (["Hello world", "hello world", "Hello world"], False),  # Case sensitive hash
]

@pytest.mark.parametrize("text_sequence,expected_stalled", TEXT_OUTPUT_STAGNATION_CASES)
def test_stagnation_detector_text_loop(text_sequence: list[str], expected_stalled: bool):
    detector = StagnationDetector()
    last_report = StagnationReport(is_stalled=False)
    for text in text_sequence:
        last_report = detector.record_text_output(text)
    assert last_report.is_stalled is expected_stalled


def test_stagnation_detector_reset():
    detector = StagnationDetector(max_consecutive_same=3)
    # Trip stall
    for _ in range(3):
        detector.record_tool_call("read_file", {"path": "a.py"})
    assert detector.record_tool_call("read_file", {"path": "a.py"}).is_stalled is True

    # Reset clears history
    detector.reset()
    assert detector._call_history == []
    assert detector._text_hashes == []
    res = detector.record_tool_call("read_file", {"path": "a.py"})
    assert res.is_stalled is False


# ============================================================================
# 2. StagnationInterceptor: No-Op Edits, Ping-Pong Oscillation & Failure Streaks
# ============================================================================

NO_OP_EDIT_CASES = [
    ("edit_file", {"path": "a.py", "target": "def foo(): pass", "replacement": "def foo(): pass"}, True),
    ("edit_file", {"path": "a.py", "target": "x = 1", "replacement": "x = 2"}, False),
    ("edit_file", {"path": "b.py", "target": "import os", "replacement": "import os"}, True),
    ("edit_file", {"path": "b.py", "target": "import os", "replacement": "import os\nimport sys"}, False),
    ("edit_file", {"path": "c.py", "target": "return True", "replacement": "return True"}, True),
    ("write_file", {"path": "d.py", "content": "print(1)"}, False),
    ("read_file", {"path": "e.py"}, False),
    ("edit_file", {"path": "f.py", "target": "class A: pass", "replacement": "class A: pass"}, True),
    ("edit_file", {"path": "g.py", "target": "TIMEOUT = 10", "replacement": "TIMEOUT = 20"}, False),
    ("edit_file", {"path": "h.py", "target": "line_one", "replacement": "line_two"}, False),
]

@pytest.mark.parametrize("tool_name,args,expected_stalled", NO_OP_EDIT_CASES)
def test_stagnation_interceptor_noop_edits(tool_name: str, args: dict, expected_stalled: bool):
    interceptor = StagnationInterceptor()
    report = interceptor.intercept_execution(tool_name, args, success=True)
    assert report.is_stalled is expected_stalled
    if expected_stalled:
        assert "No-op edit detected" in report.reason
        assert report.corrective_prompt is not None


PING_PONG_OSCILLATION_CASES = [
    # File alternating between version A and version B: A, B, A, B -> stalled on 4th
    ("src/service.py", ["version_A", "version_B", "version_A", "version_B"], True),
    # 3 edits without oscillation
    ("src/service.py", ["v1", "v2", "v3"], False),
    # Alternating 3 times
    ("src/config.py", ["A", "B", "A", "B"], True),
    # Progressive modifications: A -> B -> C -> D
    ("src/model.py", ["class V1:", "class V2:", "class V3:", "class V4:"], False),
    # Edit across two different files (no single-file ping-pong)
    ("src/file1.py", ["content_1", "content_2"], False),
    # Repeated same content in edit (tested via ping pong)
    ("src/auth.py", ["token_v1", "token_v2", "token_v1", "token_v2"], True),
    # Oscillation in markdown
    ("README.md", ["# Title 1", "# Title 2", "# Title 1", "# Title 2"], True),
    # Non-oscillating
    ("src/app.py", ["import a", "import b", "import c"], False),
    # Cycle of 3 distinct: A -> B -> C -> A
    ("src/cache.py", ["opt_1", "opt_2", "opt_3", "opt_1"], False),
    # Oscillating boolean flag
    ("src/flags.py", ["FLAG = True", "FLAG = False", "FLAG = True", "FLAG = False"], True),
]

@pytest.mark.parametrize("file_path,contents,expected_stalled", PING_PONG_OSCILLATION_CASES)
def test_stagnation_interceptor_ping_pong_oscillation(file_path: str, contents: list[str], expected_stalled: bool):
    interceptor = StagnationInterceptor()
    last_report = StagnationReport(is_stalled=False)
    for c in contents:
        last_report = interceptor.intercept_execution(
            "write_file",
            {"path": file_path, "content": c},
            success=True
        )
    assert last_report.is_stalled is expected_stalled
    if expected_stalled:
        assert "Ping-pong oscillation detected" in last_report.reason


REPEATED_FAILURE_STREAK_CASES = [
    ([False, False, False], True),
    ([False, False], False),
    ([True, False, False, False], True),
    ([False, True, False, False], False),
    ([False, False, False, False], True),
    ([True, True, True], False),
    ([False, True, True], False),
    ([True, False, False], False),
    ([False, False, True, False, False, False], True),
    ([False], False),
]

@pytest.mark.parametrize("success_stream,expected_stalled", REPEATED_FAILURE_STREAK_CASES)
def test_stagnation_interceptor_failure_streaks(success_stream: list[bool], expected_stalled: bool):
    interceptor = StagnationInterceptor(max_repeated_failures=3)
    last_report = StagnationReport(is_stalled=False)
    for idx, succ in enumerate(success_stream):
        last_report = interceptor.intercept_execution(
            "run_shell",
            {"command": f"pytest test_{idx}.py"},
            success=succ,
            exit_code=0 if succ else 1,
            output_snippet="fail" if not succ else "ok"
        )
    assert last_report.is_stalled is expected_stalled
    if expected_stalled:
        assert "consecutive times" in last_report.reason.lower() or "failed" in last_report.reason.lower()


# ============================================================================
# 3. ASTContractGate: Python Interface Breaking Change Detection
# ============================================================================

REMOVED_FUNCTION_CASES = [
    ("def f1(): pass\ndef f2(): pass\n", "def f2(): pass\n", "f1", True),
    ("def calculate(x): return x\n", "def compute(x): return x\n", "calculate", True),
    ("def keep_me(): pass\n", "def keep_me(): pass\n", "", False),
    ("def a(): pass\ndef b(): pass\ndef c(): pass\n", "def a(): pass\ndef c(): pass\n", "b", True),
    ("async def async_fetch(): pass\n", "# removed\n", "async_fetch", True),
    ("def _private(): pass\n", "# private removed\n", "_private", False),  # Private functions ignored
    ("def helper(): pass\ndef main(): pass\n", "def main(): pass\n", "helper", True),
    ("def f(): pass\n", "def f(): return 1\n", "", False),
    ("class Service:\n    def run(self): pass\n", "class Service:\n    pass\n", "run", True),
    ("def api_endpoint(): pass\n", "def api_endpoint(): pass\ndef new_fn(): pass\n", "", False),
]

@pytest.mark.parametrize("old_code,new_code,removed_symbol,expected_breaking", REMOVED_FUNCTION_CASES)
def test_contract_gate_removed_function(old_code: str, new_code: str, removed_symbol: str, expected_breaking: bool):
    gate = ASTContractGate()
    res = gate.verify_change("service.py", old_code, new_code)
    if expected_breaking:
        assert res.has_errors or res.has_warnings
        syms = [b.symbol_name for b in res.breaking_changes]
        assert any(removed_symbol in s for s in syms)
    else:
        assert not res.has_errors


ADDED_REQUIRED_PARAM_CASES = [
    ("def add(a, b): return a + b\n", "def add(a, b, c): return a + b + c\n", True),
    ("def add(a, b): return a + b\n", "def add(a, b, c=0): return a + b + c\n", False),
    ("def greet(name): return name\n", "def greet(name, formal=False): return name\n", False),
    ("def process(data): pass\n", "def process(data, validator): pass\n", True),
    ("def query(q): pass\n", "def query(q, timeout=30): pass\n", False),
    ("def run(): pass\n", "def run(mode): pass\n", True),
    ("def exec_cmd(cmd): pass\n", "def exec_cmd(cmd, env=None, cwd=None): pass\n", False),
    ("def send(msg): pass\n", "def send(msg, recipient): pass\n", True),
    ("def ping(): return 'pong'\n", "def ping(count=1): return 'pong' * count\n", False),
    ("def compute(x, y): pass\n", "def compute(x, y, z, w=1): pass\n", True),
]

@pytest.mark.parametrize("old_code,new_code,expected_breaking", ADDED_REQUIRED_PARAM_CASES)
def test_contract_gate_added_required_param(old_code: str, new_code: str, expected_breaking: bool):
    gate = ASTContractGate()
    res = gate.verify_change("service.py", old_code, new_code)
    if expected_breaking:
        assert res.has_errors or res.has_warnings
        messages = [b.message for b in res.breaking_changes]
        assert any("parameter" in m.lower() or "signature" in m.lower() for m in messages)
    else:
        assert not res.has_errors


REMOVED_CLASS_CASES = [
    ("class Authenticator:\n    pass\n", "# Authenticator removed\n", True),
    ("class Config:\n    pass\nclass App:\n    pass\n", "class App:\n    pass\n", True),
    ("class App:\n    pass\n", "class App:\n    version = 2\n", False),
    ("class _InternalHelper:\n    pass\n", "# internal removed\n", False),  # Private ignored
    ("class DBConnection:\n    pass\n", "class DBConnection:\n    pass\nclass NewClass:\n    pass\n", False),
    ("class Repository:\n    def find(self): pass\n", "# repo deleted\n", True),
    ("class Model:\n    x: int = 1\n", "class Model:\n    x: int = 2\n", False),
    ("class Cache:\n    pass\n", "#\n", True),
    ("class Token:\n    pass\n", "class Token:\n    pass\n", False),
    ("class Logger:\n    pass\nclass Formatter:\n    pass\n", "class Logger:\n    pass\n", True),
]

@pytest.mark.parametrize("old_code,new_code,expected_breaking", REMOVED_CLASS_CASES)
def test_contract_gate_removed_class(old_code: str, new_code: str, expected_breaking: bool):
    gate = ASTContractGate()
    res = gate.verify_change("service.py", old_code, new_code)
    if expected_breaking:
        assert res.has_errors or res.has_warnings
    else:
        assert not res.has_errors


POLYGLOT_CONTRACT_CASES = [
    ("service.ts", "export function calculateTotal(price: number): number { return price; }\n", "export function otherFunction(): void {}\n", True),
    ("service.ts", "export function sum(a: number): number { return a; }\n", "export function sum(a: number): number { return a + 1; }\n", False),
    ("handler.go", "package main\nfunc Serve(port int) error { return nil }\n", "package main\nfunc Health() string { return \"ok\" }\n", True),
    ("handler.go", "package main\nfunc Ping() string { return \"pong\" }\n", "package main\nfunc Ping() string { return \"pong!\" }\n", False),
    ("lib.rs", "pub fn process_data(input: &str) -> bool { true }\n", "pub fn new_handler() -> bool { true }\n", True),
    ("lib.rs", "pub fn process_data(input: &str) -> bool { true }\n", "pub fn process_data(input: &str) -> bool { false }\n", False),
    ("config.json", '{"port": 8080}', '{"port": 9090}', False),
    ("README.md", "# Title\n", "# New Title\n", False),
    ("service.ts", "export class UserRepo { getById(id: string) {} }\n", "export class OtherRepo { }\n", True),
    ("service.ts", "export interface Config { timeout: number; }\n", "export interface Config { timeout: number; host: string; }\n", False),
]

@pytest.mark.parametrize("filename,old_code,new_code,expected_breaking", POLYGLOT_CONTRACT_CASES)
def test_contract_gate_polyglot_contracts(filename: str, old_code: str, new_code: str, expected_breaking: bool):
    gate = ASTContractGate()
    res = gate.verify_change(filename, old_code, new_code)
    if expected_breaking:
        assert res.has_errors or res.has_warnings
    else:
        assert not res.has_errors


# ============================================================================
# 4. TaskStateMachine: Transitions, Terminal States & Error Matrix
# ============================================================================

VALID_STATE_TRANSITIONS = [
    (TaskState.CREATED, TaskState.CONTEXTUALIZING),
    (TaskState.CREATED, TaskState.CANCELLED),
    (TaskState.CONTEXTUALIZING, TaskState.PLANNING),
    (TaskState.CONTEXTUALIZING, TaskState.FAILED),
    (TaskState.CONTEXTUALIZING, TaskState.CANCELLED),
    (TaskState.PLANNING, TaskState.WAITING_FOR_APPROVAL),
    (TaskState.PLANNING, TaskState.READY),
    (TaskState.PLANNING, TaskState.FAILED),
    (TaskState.PLANNING, TaskState.CANCELLED),
    (TaskState.WAITING_FOR_APPROVAL, TaskState.READY),
    (TaskState.WAITING_FOR_APPROVAL, TaskState.PLANNING),
    (TaskState.WAITING_FOR_APPROVAL, TaskState.CANCELLED),
    (TaskState.READY, TaskState.EXECUTING),
    (TaskState.READY, TaskState.PAUSED),
    (TaskState.READY, TaskState.CANCELLED),
    (TaskState.EXECUTING, TaskState.VERIFYING),
    (TaskState.EXECUTING, TaskState.RECOVERING),
    (TaskState.EXECUTING, TaskState.PAUSED),
    (TaskState.EXECUTING, TaskState.FAILED),
    (TaskState.EXECUTING, TaskState.CANCELLED),
    (TaskState.VERIFYING, TaskState.COMPLETED),
    (TaskState.VERIFYING, TaskState.RECOVERING),
    (TaskState.VERIFYING, TaskState.EXECUTING),
    (TaskState.VERIFYING, TaskState.FAILED),
    (TaskState.RECOVERING, TaskState.PLANNING),
    (TaskState.RECOVERING, TaskState.EXECUTING),
    (TaskState.RECOVERING, TaskState.VERIFYING),
    (TaskState.RECOVERING, TaskState.RECOVERING),
    (TaskState.RECOVERING, TaskState.FAILED),
    (TaskState.RECOVERING, TaskState.CANCELLED),
    (TaskState.PAUSED, TaskState.READY),
    (TaskState.PAUSED, TaskState.EXECUTING),
    (TaskState.PAUSED, TaskState.CANCELLED),
    (TaskState.FAILED, TaskState.RECOVERING),
    (TaskState.FAILED, TaskState.CANCELLED),
]

@pytest.mark.parametrize("from_state,to_state", VALID_STATE_TRANSITIONS)
def test_state_machine_valid_transitions(from_state: TaskState, to_state: TaskState):
    fsm = TaskStateMachine(task_id="task-001", initial_state=from_state)
    new_s = fsm.transition_to(to_state, reason=f"Testing transition {from_state.value} -> {to_state.value}")
    assert new_s == to_state
    assert fsm.current_state == to_state
    assert len(fsm.history) == 2
    assert fsm.history[-1]["from_state"] == from_state.value
    assert fsm.history[-1]["to_state"] == to_state.value


INVALID_STATE_TRANSITIONS = [
    # Terminal state transitions
    (TaskState.COMPLETED, TaskState.EXECUTING),
    (TaskState.COMPLETED, TaskState.PLANNING),
    (TaskState.COMPLETED, TaskState.CREATED),
    (TaskState.CANCELLED, TaskState.EXECUTING),
    (TaskState.CANCELLED, TaskState.READY),
    # Illegal skip transitions
    (TaskState.CREATED, TaskState.EXECUTING),
    (TaskState.CREATED, TaskState.COMPLETED),
    (TaskState.CREATED, TaskState.VERIFYING),
    (TaskState.CONTEXTUALIZING, TaskState.COMPLETED),
    (TaskState.CONTEXTUALIZING, TaskState.EXECUTING),
    (TaskState.PLANNING, TaskState.COMPLETED),
    (TaskState.WAITING_FOR_APPROVAL, TaskState.COMPLETED),
    (TaskState.WAITING_FOR_APPROVAL, TaskState.EXECUTING),
    (TaskState.READY, TaskState.COMPLETED),
    (TaskState.READY, TaskState.VERIFYING),
    (TaskState.EXECUTING, TaskState.COMPLETED),
    (TaskState.VERIFYING, TaskState.PLANNING),
    (TaskState.VERIFYING, TaskState.CANCELLED),
    (TaskState.FAILED, TaskState.COMPLETED),
    (TaskState.FAILED, TaskState.EXECUTING),
    (TaskState.PAUSED, TaskState.COMPLETED),
    (TaskState.PAUSED, TaskState.VERIFYING),
    (TaskState.COMPLETED, TaskState.CANCELLED),
    (TaskState.CANCELLED, TaskState.FAILED),
    (TaskState.FAILED, TaskState.PLANNING),
]

@pytest.mark.parametrize("from_state,to_state", INVALID_STATE_TRANSITIONS)
def test_state_machine_invalid_transitions_raise(from_state: TaskState, to_state: TaskState):
    fsm = TaskStateMachine(task_id="task-err", initial_state=from_state)
    with pytest.raises(StateMachineError) as exc_info:
        fsm.transition_to(to_state)
    assert "Illegal State Transition" in str(exc_info.value)
    assert fsm.current_state == from_state  # State unchanged


TERMINAL_STATE_CASES = [
    (TaskState.COMPLETED, True),
    (TaskState.CANCELLED, True),
    (TaskState.CREATED, False),
    (TaskState.CONTEXTUALIZING, False),
    (TaskState.PLANNING, False),
    (TaskState.WAITING_FOR_APPROVAL, False),
    (TaskState.READY, False),
    (TaskState.EXECUTING, False),
    (TaskState.VERIFYING, False),
    (TaskState.RECOVERING, False),
    (TaskState.PAUSED, False),
    (TaskState.FAILED, False),
]

@pytest.mark.parametrize("state,expected_terminal", TERMINAL_STATE_CASES)
def test_state_machine_terminal_state_detection(state: TaskState, expected_terminal: bool):
    fsm = TaskStateMachine(task_id="task-term", initial_state=state)
    assert fsm.is_terminal() is expected_terminal


def test_state_machine_callback_and_history():
    events = []

    def on_trans(task_id: str, old_s: TaskState, new_s: TaskState, reason: str):
        events.append((task_id, old_s, new_s, reason))

    fsm = TaskStateMachine(task_id="task-full-lifecycle", initial_state=TaskState.CREATED, on_transition=on_trans)
    fsm.transition_to(TaskState.CONTEXTUALIZING, "Analyzing project AST")
    fsm.transition_to(TaskState.PLANNING, "Formulating plan")
    fsm.transition_to(TaskState.READY, "Plan approved")
    fsm.transition_to(TaskState.EXECUTING, "Applying code mutations")
    fsm.transition_to(TaskState.VERIFYING, "Running test suite")
    fsm.transition_to(TaskState.COMPLETED, "All 100 tests pass")

    assert fsm.is_terminal() is True
    assert len(events) == 6
    assert events[0] == ("task-full-lifecycle", TaskState.CREATED, TaskState.CONTEXTUALIZING, "Analyzing project AST")
    assert events[-1] == ("task-full-lifecycle", TaskState.VERIFYING, TaskState.COMPLETED, "All 100 tests pass")
    assert len(fsm.history) == 7  # 1 init + 6 transitions
