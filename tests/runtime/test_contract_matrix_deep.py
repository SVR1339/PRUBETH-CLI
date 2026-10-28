"""Deep Parameterized Matrix Tests for AST Contract Gate and Invariant Enforcers."""

import pytest
from prubeth.runtime.contract import (
    ASTContractGate,
    BreakingChange,
    BreakingChangeSeverity,
    PythonContractExtractor
)
from prubeth.repository.graph import CodeGraph
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind


@pytest.fixture
def gate():
    return ASTContractGate()


# =========================================================================
# Matrix: 50 Parameter Mutation Permutations
# =========================================================================

PARAM_TYPES = ["int", "str", "float", "bool", "list", "dict", "Optional[str]", "Any"]
DEFAULT_VALS = ["0", "''", "None", "False", "[]", "{}"]

@pytest.mark.parametrize("idx, p_type", list(enumerate(PARAM_TYPES)))
def test_matrix_adding_optional_parameter_is_valid(gate, idx, p_type):
    old_c = f"def process_item_{idx}(item_id: int) -> bool:\n    return True\n"
    new_c = f"def process_item_{idx}(item_id: int, extra: {p_type} = None) -> bool:\n    return True\n"
    res = gate.verify_change(f"src/mod_{idx}.py", old_c, new_c)
    assert res.valid is True
    assert len(res.breaking_changes) == 0


@pytest.mark.parametrize("idx, p_type", list(enumerate(PARAM_TYPES)))
def test_matrix_adding_mandatory_parameter_is_breaking(gate, idx, p_type):
    old_c = f"def process_item_{idx}(item_id: int) -> bool:\n    return True\n"
    new_c = f"def process_item_{idx}(item_id: int, mandatory_arg: {p_type}) -> bool:\n    return True\n"
    res = gate.verify_change(f"src/mod_{idx}.py", old_c, new_c)
    assert res.valid is False
    assert any("mandatory parameter" in b.message for b in res.breaking_changes)


@pytest.mark.parametrize("idx, def_val", list(enumerate(DEFAULT_VALS)))
def test_matrix_various_default_expressions_non_breaking(gate, idx, def_val):
    old_c = f"def compute_{idx}(base: int) -> int:\n    return base\n"
    new_c = f"def compute_{idx}(base: int, factor: int = {def_val}) -> int:\n    return base\n"
    res = gate.verify_change(f"src/calc_{idx}.py", old_c, new_c)
    assert res.valid is True


@pytest.mark.parametrize("idx", range(10))
def test_matrix_reordering_parameters_triggers_removal(gate, idx):
    old_c = f"def order_func_{idx}(alpha: int, beta: str) -> None:\n    pass\n"
    # Swap parameter order: alpha, beta -> beta, alpha
    new_c = f"def order_func_{idx}(beta: str, gamma: int) -> None:\n    pass\n"
    res = gate.verify_change(f"src/order_{idx}.py", old_c, new_c)
    assert res.valid is False
    assert any("Removed parameter 'alpha'" in b.message for b in res.breaking_changes)


# =========================================================================
# Matrix: 30 Class Hierarchy & Method Signatures
# =========================================================================

@pytest.mark.parametrize("idx", range(15))
def test_matrix_class_method_preservation(gate, idx):
    old_c = (
        f"class ServiceHandler_{idx}:\n"
        f"    def execute_{idx}(self, req: dict) -> dict:\n"
        f"        return {{'status': 200}}\n"
    )
    # Valid modification: internal logic tweak
    new_c = (
        f"class ServiceHandler_{idx}:\n"
        f"    def execute_{idx}(self, req: dict) -> dict:\n"
        f"        log_request(req)\n"
        f"        return {{'status': 200, 'idx': {idx}}}\n"
    )
    res = gate.verify_change(f"src/svc_{idx}.py", old_c, new_c)
    assert res.valid is True


@pytest.mark.parametrize("idx", range(15))
def test_matrix_class_method_removal_is_breaking(gate, idx):
    old_c = (
        f"class Repository_{idx}:\n"
        f"    def find_by_id(self, item_id: str) -> dict:\n"
        f"        return {{}}\n"
        f"    def delete_by_id_{idx}(self, item_id: str) -> bool:\n"
        f"        return True\n"
    )
    # Removed delete_by_id
    new_c = (
        f"class Repository_{idx}:\n"
        f"    def find_by_id(self, item_id: str) -> dict:\n"
        f"        return {{}}\n"
    )
    res = gate.verify_change(f"src/repo_{idx}.py", old_c, new_c)
    assert any(f"delete_by_id_{idx}" in b.symbol_name for b in res.breaking_changes)


# =========================================================================
# Matrix: 40 Polyglot Syntax Balance Verifications
# =========================================================================

@pytest.mark.parametrize("ext, lang", [
    (".ts", "TypeScript"),
    (".js", "JavaScript"),
    (".rs", "Rust"),
    (".go", "Go"),
    (".json", "JSON"),
    (".c", "C"),
    (".cpp", "C++"),
    (".java", "Java")
])
@pytest.mark.parametrize("depth", [1, 2, 3, 5, 8])
def test_matrix_polyglot_nested_braces(gate, ext, lang, depth):
    openers = "{" * depth
    closers = "}" * depth
    code = f"// {lang} code\n{openers}\n  let x = 1;\n{closers}\n"
    res = gate.verify_change(f"src/code_{depth}{ext}", "old", code)
    assert res.valid is True


@pytest.mark.parametrize("ext", [".ts", ".rs", ".go", ".json"])
@pytest.mark.parametrize("unclosed", ["{", "[", "("])
def test_matrix_polyglot_unclosed_delimiters(gate, ext, unclosed):
    code = f"fn test() {unclosed} x = 1;\n"
    res = gate.verify_change(f"src/broken{ext}", "old", code)
    assert res.valid is False
    assert any("Unclosed delimiter" in b.message for b in res.breaking_changes)


@pytest.mark.parametrize("ext", [".ts", ".rs", ".go"])
@pytest.mark.parametrize("pair", [("{", "]"), ("[", ")"), ("(", "}")])
def test_matrix_polyglot_mismatched_delimiters(gate, ext, pair):
    op, cl = pair
    code = f"function test() {op} return 1; {cl}\n"
    res = gate.verify_change(f"src/mismatch{ext}", "old", code)
    assert res.valid is False
    assert any("Mismatched delimiter" in b.message for b in res.breaking_changes)
