"""PRUBETH Deep Polyglot Contract & AST Invariant Permutation Matrix.

Exhaustively verifies contract invariance, breaking change detection,
caller graph escalation, and non-breaking evolutionary changes across
all 13 supported programming languages.
"""

from __future__ import annotations

import pytest
from prubeth.runtime.contract import (
    ASTContractGate,
    BreakingChangeSeverity,
    ContractVerificationResult,
)
from prubeth.repository.graph import CodeGraph
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind


LANG_SAMPLES = [
    (".py", "def service_alpha():\n    return 1\n", "def service_beta():\n    return 2\n", "service_beta"),
    (".ts", "export function serviceAlpha(): number { return 1; }\n", "export function serviceBeta(): number { return 2; }\n", "serviceBeta"),
    (".js", "function serviceAlpha() { return 1; }\n", "function serviceBeta() { return 2; }\n", "serviceBeta"),
    (".tsx", "export function ViewAlpha() { return null; }\n", "export function ViewBeta() { return null; }\n", "ViewBeta"),
    (".jsx", "function ViewAlpha() { return null; }\n", "function ViewBeta() { return null; }\n", "ViewBeta"),
    (".go", "func ServiceAlpha() int { return 1 }\n", "func ServiceBeta() int { return 2 }\n", "ServiceBeta"),
    (".rs", "pub fn service_alpha() -> i32 { 1 }\n", "pub fn service_beta() -> i32 { 2 }\n", "service_beta"),
    (".java", "class ServiceAlpha {\n}\n", "class ServiceBeta {\n}\n", "ServiceBeta"),
    (".cs", "class ServiceAlpha {\n}\n", "class ServiceBeta {\n}\n", "ServiceBeta"),
    (".rb", "class ServiceAlpha\nend\n", "class ServiceBeta\nend\n", "ServiceBeta"),
    (".php", "class ServiceAlpha {\n}\n", "class ServiceBeta {\n}\n", "ServiceBeta"),
    (".swift", "class ServiceAlpha {\n}\n", "class ServiceBeta {\n}\n", "ServiceBeta"),
    (".kt", "class ServiceAlpha {\n}\n", "class ServiceBeta {\n}\n", "ServiceBeta"),
]


@pytest.fixture
def empty_gate():
    return ASTContractGate()


# ============================================================================
# 1. New File Creation (Zero Invariants Violated)
# ============================================================================

@pytest.mark.parametrize("ext,code_a,code_b,target_sym", LANG_SAMPLES)
def test_contract_new_file_creation_always_valid(empty_gate, ext, code_a, code_b, target_sym):
    """Creating a new file with no pre-existing content should never flag breaking changes."""
    new_code = f"{code_a}\n{code_b}\n"
    res = empty_gate.verify_proposed_change(f"src/module{ext}", new_code, old_content="")
    assert res.valid is True
    assert len(res.breaking_changes) == 0


# ============================================================================
# 2. Additive Non-Breaking Evolutions
# ============================================================================

@pytest.mark.parametrize("ext,code_a,code_b,target_sym", LANG_SAMPLES)
def test_contract_additive_extension_always_valid(empty_gate, ext, code_a, code_b, target_sym):
    """Adding new symbols while preserving existing symbols must be 100% non-breaking."""
    old_code = code_a
    new_code = f"{code_a}\n{code_b}\n"
    res = empty_gate.verify_proposed_change(f"src/module{ext}", new_code, old_content=old_code)
    assert res.valid is True
    assert len(res.breaking_changes) == 0


# ============================================================================
# 3. Symbol Removal Without Callers (Warning Only, Non-Blocking)
# ============================================================================

@pytest.mark.parametrize("ext,code_a,code_b,target_sym", LANG_SAMPLES)
def test_contract_symbol_removal_no_callers_warns_only(empty_gate, ext, code_a, code_b, target_sym):
    """Removing a symbol with zero callers produces WARNING severity without blocking the agent."""
    old_code = f"{code_a}\n{code_b}\n"
    new_code = code_a
    res = empty_gate.verify_proposed_change(f"src/module{ext}", new_code, old_content=old_code)
    assert res.valid is True
    assert len(res.breaking_changes) >= 1
    assert any(b.symbol_name == target_sym and b.severity == BreakingChangeSeverity.WARNING for b in res.breaking_changes)


# ============================================================================
# 4. Symbol Removal With Active Callers (Blocking ERROR)
# ============================================================================

@pytest.mark.parametrize("ext,code_a,code_b,target_sym", LANG_SAMPLES)
def test_contract_symbol_removal_with_callers_blocks(ext, code_a, code_b, target_sym):
    """Removing a symbol that has registered dependents in CodeGraph must produce ERROR and valid=False."""
    graph = CodeGraph()
    caller = CodeSymbol(
        name="downstream_client",
        kind=SymbolKind.FUNCTION,
        file_path="src/client.ts",
        start_line=1,
        end_line=20,
        signature="function downstreamClient()",
        calls=[target_sym]
    )
    graph.add_symbol(caller)

    gate = ASTContractGate(graph=graph)
    old_code = f"{code_a}\n{code_b}\n"
    new_code = code_a

    res = gate.verify_proposed_change(f"src/module{ext}", new_code, old_content=old_code, force=False)
    assert res.valid is False
    assert any(b.symbol_name == target_sym and b.severity == BreakingChangeSeverity.ERROR for b in res.breaking_changes)


# ============================================================================
# 5. Forced Mutation Bypass (Contract Override)
# ============================================================================

@pytest.mark.parametrize("ext,code_a,code_b,target_sym", LANG_SAMPLES)
def test_contract_symbol_removal_with_callers_force_bypass(ext, code_a, code_b, target_sym):
    """When force=True is specified, mutations are allowed even when breaking callers exist."""
    graph = CodeGraph()
    caller = CodeSymbol(
        name="downstream_client",
        kind=SymbolKind.FUNCTION,
        file_path="src/client.ts",
        start_line=1,
        end_line=20,
        signature="function downstreamClient()",
        calls=[target_sym]
    )
    graph.add_symbol(caller)

    gate = ASTContractGate(graph=graph)
    old_code = f"{code_a}\n{code_b}\n"
    new_code = code_a

    res = gate.verify_proposed_change(f"src/module{ext}", new_code, old_content=old_code, force=True)
    assert res.valid is True
    assert any(b.symbol_name == target_sym for b in res.breaking_changes)
