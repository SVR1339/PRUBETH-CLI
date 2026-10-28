"""PRUBETH Polyglot Spec-Driven Development (SDD) Contract Matrix.

Verifies AST contract invariance and breaking change detection across
TypeScript, Go, Rust, Java, C++, and Python codebases.
"""

from __future__ import annotations

import pytest
from prubeth.runtime.contract import (
    ASTContractGate,
    BreakingChangeSeverity,
    ContractVerificationResult,
)
from prubeth.repository.graph import CodeGraph


@pytest.fixture
def empty_gate():
    return ASTContractGate()


# ============================================================================
# 1. TypeScript Contract Invariants
# ============================================================================

def test_typescript_function_removed_detected(empty_gate):
    old_ts = """
export function calculateTax(amount: number): number {
    return amount * 0.2;
}

export function formatCurrency(amount: number): string {
    return `$${amount.toFixed(2)}`;
}
"""
    new_ts = """
export function calculateTax(amount: number): number {
    return amount * 0.2;
}
"""
    res = empty_gate.verify_proposed_change("src/tax.ts", new_ts, old_content=old_ts)
    # No callers in empty graph -> severity WARNING -> valid=True
    assert res.valid is True
    assert any(b.symbol_name == "formatCurrency" for b in res.breaking_changes)


def test_typescript_mandatory_parameter_added(empty_gate):
    old_ts = """
export function sendEmail(to: string, subject: string): boolean {
    return true;
}
"""
    new_ts = """
export function sendEmail(to: string, subject: string, mandatoryAuthToken: string): boolean {
    return true;
}
"""
    res = empty_gate.verify_proposed_change("src/mailer.ts", new_ts, old_content=old_ts)
    assert any("mandatoryAuthToken" in b.message for b in res.breaking_changes)


def test_typescript_optional_parameter_added_is_non_breaking(empty_gate):
    old_ts = """
export function sendEmail(to: string, subject: string): boolean {
    return true;
}
"""
    new_ts = """
export function sendEmail(to: string, subject: string, optionalOptions?: any): boolean {
    return true;
}
"""
    res = empty_gate.verify_proposed_change("src/mailer.ts", new_ts, old_content=old_ts)
    assert not any("optionalOptions" in b.message for b in res.breaking_changes)


def test_typescript_delimiter_imbalance(empty_gate):
    old_ts = "function test() { return true; }"
    new_ts = "function test() { return true;"
    res = empty_gate.verify_proposed_change("src/app.ts", new_ts, old_content=old_ts)
    assert res.valid is False
    assert any("Unclosed delimiter" in b.message for b in res.breaking_changes)


# ============================================================================
# 2. Go Contract Invariants
# ============================================================================

def test_go_struct_removed_detected(empty_gate):
    old_go = """
package auth

type UserSession struct {
    Token string
    ExpiresAt int64
}

type LegacySession struct {
    ID string
}
"""
    new_go = """
package auth

type UserSession struct {
    Token string
    ExpiresAt int64
}
"""
    res = empty_gate.verify_proposed_change("pkg/auth/session.go", new_go, old_content=old_go)
    assert any(b.symbol_name == "LegacySession" for b in res.breaking_changes)


def test_go_function_mandatory_parameter_added(empty_gate):
    old_go = """
package math

func Add(a int, b int) int {
    return a + b
}
"""
    new_go = """
package math

func Add(a int, b int, c int) int {
    return a + b + c
}
"""
    res = empty_gate.verify_proposed_change("pkg/math/calc.go", new_go, old_content=old_go)
    assert any("c int" in b.message or "c" in b.message for b in res.breaking_changes)


def test_go_parenthesis_imbalance(empty_gate):
    old_go = "package main\nfunc main() {}"
    new_go = "package main\nfunc main( {}"
    res = empty_gate.verify_proposed_change("main.go", new_go, old_content=old_go)
    assert res.valid is False


# ============================================================================
# 3. Rust Contract Invariants
# ============================================================================

def test_rust_struct_removed_detected(empty_gate):
    old_rs = """
pub struct Engine {
    pub workers: usize,
}

pub struct Config {
    pub port: u16,
}
"""
    new_rs = """
pub struct Engine {
    pub workers: usize,
}
"""
    res = empty_gate.verify_proposed_change("src/lib.rs", new_rs, old_content=old_rs)
    assert any(b.symbol_name == "Config" for b in res.breaking_changes)


def test_rust_brace_imbalance(empty_gate):
    old_rs = "pub struct S { x: i32 }"
    new_rs = "pub struct S { x: i32 "
    res = empty_gate.verify_proposed_change("src/types.rs", new_rs, old_content=old_rs)
    assert res.valid is False


# ============================================================================
# 4. Java Contract Invariants
# ============================================================================

def test_java_class_removed_detected(empty_gate):
    old_java = """
public class PaymentGateway {
    public void process() {}
}

class InternalHelper {
}
"""
    new_java = """
public class PaymentGateway {
    public void process() {}
}
"""
    res = empty_gate.verify_proposed_change("PaymentGateway.java", new_java, old_content=old_java)
    assert any(b.symbol_name == "InternalHelper" for b in res.breaking_changes)


# ============================================================================
# 5. Graph Callers Impact Escalation to ERROR
# ============================================================================

def test_polyglot_breaking_change_escalates_to_error_when_callers_exist():
    graph = CodeGraph()
    # Register caller in graph
    from prubeth.repository.ast_parser import CodeSymbol, SymbolKind
    caller_symbol = CodeSymbol(
        name="dispatchHandler",
        kind=SymbolKind.FUNCTION,
        file_path="src/router.ts",
        start_line=10,
        end_line=20,
        signature="function dispatchHandler()",
        calls=["fetchUserData"]
    )
    graph.add_symbol(caller_symbol)

    gate = ASTContractGate(graph=graph)

    old_ts = """
export function fetchUserData(userId: string): Promise<any> {
    return Promise.resolve({});
}
"""
    new_ts = """
// fetchUserData removed completely!
"""
    res = gate.verify_proposed_change("src/api.ts", new_ts, old_content=old_ts)
    assert res.valid is False
    assert res.has_errors is True
    assert "dispatchHandler" in res.affected_callers
    assert any(b.severity == BreakingChangeSeverity.ERROR for b in res.breaking_changes)


def test_polyglot_breaking_change_force_override_allows_mutations():
    graph = CodeGraph()
    from prubeth.repository.ast_parser import CodeSymbol, SymbolKind
    caller_symbol = CodeSymbol(
        name="worker",
        kind=SymbolKind.FUNCTION,
        file_path="src/worker.go",
        start_line=1,
        end_line=10,
        signature="func worker()",
        calls=["OldEngine"]
    )
    graph.add_symbol(caller_symbol)

    gate = ASTContractGate(graph=graph)
    old_go = "package main\ntype OldEngine struct {}\n"
    new_go = "package main\n"

    # With force=True, mutation is allowed despite callers
    res = gate.verify_proposed_change("src/engine.go", new_go, old_content=old_go, force=True)
    assert res.valid is True
    assert len(res.breaking_changes) > 0


# ============================================================================
# 6. Parameterized Polyglot Matrix Scale
# ============================================================================

@pytest.mark.parametrize("lang_ext,sym_decl_1,sym_decl_2,sym_name", [
    (".ts", "export function funcAlpha() {}", "export function funcBeta() {}", "funcBeta"),
    (".js", "function workerOne() {}", "function workerTwo() {}", "workerTwo"),
    (".go", "func HandleA() {}", "func HandleB() {}", "HandleB"),
    (".rs", "pub fn start_alpha() {}", "pub fn start_beta() {}", "start_beta"),
    (".java", "class ServiceA {}", "class ServiceB {}", "ServiceB"),
    (".cs", "class ModuleA {}", "class ModuleB {}", "ModuleB"),
    (".rb", "class HandlerA\nend", "class HandlerB\nend", "HandlerB"),
    (".php", "class ControllerA {}", "class ControllerB {}", "ControllerB"),
    (".swift", "class ManagerA {}", "class ManagerB {}", "ManagerB"),
    (".kt", "class ServiceA {}", "class ServiceB {}", "ServiceB"),
])
def test_polyglot_symbol_removal_matrix_scale(empty_gate, lang_ext, sym_decl_1, sym_decl_2, sym_name):
    old_content = f"{sym_decl_1}\n{sym_decl_2}\n"
    new_content = f"{sym_decl_1}\n"

    res = empty_gate.verify_proposed_change(f"test_service{lang_ext}", new_content, old_content=old_content)
    assert any(b.symbol_name == sym_name for b in res.breaking_changes)
