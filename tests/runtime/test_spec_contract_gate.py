"""Comprehensive Unit and Invariant Tests for ASTContractGate and Spec-Driven Development."""

import pytest
from prubeth.runtime.contract import (
    ASTContractGate,
    BreakingChange,
    BreakingChangeSeverity,
    ContractVerificationResult,
    PythonContractExtractor,
    ParameterSignature,
    FunctionContract,
    ClassContract
)
from prubeth.repository.graph import CodeGraph
from prubeth.repository.ast_parser import CodeSymbol, SymbolKind


@pytest.fixture
def empty_gate():
    return ASTContractGate()


@pytest.fixture
def graph_with_callers():
    graph = CodeGraph()
    sym_tax = CodeSymbol(name="calculate_tax", kind=SymbolKind.FUNCTION, file_path="src/tax.py", start_line=1, end_line=10, signature="def calculate_tax(amount: float) -> float")
    sym_payroll = CodeSymbol(name="process_payroll", kind=SymbolKind.FUNCTION, file_path="src/payroll.py", start_line=5, end_line=20, signature="def process_payroll()", calls=["calculate_tax"])
    sym_report = CodeSymbol(name="generate_report", kind=SymbolKind.FUNCTION, file_path="src/report.py", start_line=12, end_line=30, signature="def generate_report()", calls=["calculate_tax"])
    graph.add_symbol(sym_tax)
    graph.add_symbol(sym_payroll)
    graph.add_symbol(sym_report)
    return ASTContractGate(code_graph=graph)


# =========================================================================
# Non-Breaking Modifications
# =========================================================================

def test_identical_code_is_valid(empty_gate):
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    res = empty_gate.verify_change("src/math.py", code, code)
    assert res.valid is True
    assert len(res.breaking_changes) == 0


def test_internal_implementation_change_is_valid(empty_gate):
    old_code = "def greet(name: str) -> str:\n    return 'Hello ' + name\n"
    new_code = "def greet(name: str) -> str:\n    formatted = f'Hello, {name}!'\n    return formatted\n"
    res = empty_gate.verify_change("src/greeting.py", old_code, new_code)
    assert res.valid is True
    assert len(res.breaking_changes) == 0


def test_adding_default_argument_is_non_breaking(empty_gate):
    old_code = "def connect(host: str, port: int) -> None:\n    pass\n"
    new_code = "def connect(host: str, port: int, timeout: int = 30) -> None:\n    pass\n"
    res = empty_gate.verify_change("src/net.py", old_code, new_code)
    assert res.valid is True
    assert len(res.breaking_changes) == 0


def test_adding_keyword_only_argument_with_default_is_non_breaking(empty_gate):
    old_code = "def query(sql: str) -> list:\n    return []\n"
    new_code = "def query(sql: str, *, readonly: bool = True) -> list:\n    return []\n"
    res = empty_gate.verify_change("src/db.py", old_code, new_code)
    assert res.valid is True
    assert len(res.breaking_changes) == 0


def test_adding_new_public_function_is_non_breaking(empty_gate):
    old_code = "def fetch_user(uid: int) -> dict:\n    return {}\n"
    new_code = old_code + "\ndef fetch_account(acc_id: int) -> dict:\n    return {}\n"
    res = empty_gate.verify_change("src/service.py", old_code, new_code)
    assert res.valid is True
    assert len(res.breaking_changes) == 0


def test_modifying_docstring_is_non_breaking(empty_gate):
    old_code = "def compute() -> int:\n    '''Old doc'''\n    return 42\n"
    new_code = "def compute() -> int:\n    '''New enhanced docstring'''\n    return 42\n"
    res = empty_gate.verify_change("src/compute.py", old_code, new_code)
    assert res.valid is True
    assert len(res.breaking_changes) == 0


# =========================================================================
# Breaking Function Alterations
# =========================================================================

def test_removing_public_function_without_callers_triggers_warning(empty_gate):
    old_code = "def old_service() -> None:\n    pass\n"
    new_code = "# Removed old_service\n"
    res = empty_gate.verify_change("src/svc.py", old_code, new_code)
    assert res.valid is True  # Warning only when no callers known
    assert len(res.breaking_changes) == 1
    assert res.breaking_changes[0].severity == BreakingChangeSeverity.WARNING
    assert "old_service" in res.breaking_changes[0].message


def test_removing_public_function_with_callers_triggers_blocking_error(graph_with_callers):
    old_code = "def calculate_tax(amount: float) -> float:\n    return amount * 0.2\n"
    new_code = "# Removed calculate_tax\n"
    res = graph_with_callers.verify_change("src/tax.py", old_code, new_code)
    assert res.valid is False
    assert res.has_errors is True
    assert len(res.breaking_changes) == 1
    err = res.breaking_changes[0]
    assert err.severity == BreakingChangeSeverity.ERROR
    assert "calculate_tax" in err.symbol_name
    assert "process_payroll" in err.callers_affected
    assert "generate_report" in err.callers_affected


def test_adding_mandatory_positional_parameter_triggers_error(graph_with_callers):
    old_code = "def calculate_tax(amount: float) -> float:\n    return amount * 0.2\n"
    new_code = "def calculate_tax(amount: float, jurisdiction: str) -> float:\n    return amount * 0.2\n"
    res = graph_with_callers.verify_change("src/tax.py", old_code, new_code)
    assert res.valid is False
    assert res.has_errors is True
    assert any("mandatory parameter 'jurisdiction'" in b.message for b in res.breaking_changes)


def test_removing_existing_parameter_triggers_error(empty_gate):
    old_code = "def send_email(to: str, subject: str, body: str) -> bool:\n    return True\n"
    new_code = "def send_email(to: str, body: str) -> bool:\n    return True\n"
    res = empty_gate.verify_change("src/mail.py", old_code, new_code)
    assert res.valid is False
    assert any("Removed parameter 'subject'" in b.message for b in res.breaking_changes)


def test_changing_sync_to_async_triggers_error(empty_gate):
    old_code = "def get_data() -> str:\n    return 'data'\n"
    new_code = "async def get_data() -> str:\n    return 'data'\n"
    res = empty_gate.verify_change("src/io.py", old_code, new_code)
    assert res.valid is False
    assert any("changed from sync to asynchronous" in b.message for b in res.breaking_changes)


def test_changing_async_to_sync_triggers_error(empty_gate):
    old_code = "async def fetch_async() -> str:\n    return 'async'\n"
    new_code = "def fetch_async() -> str:\n    return 'sync'\n"
    res = empty_gate.verify_change("src/io.py", old_code, new_code)
    assert res.valid is False
    assert any("changed from async to synchronous" in b.message for b in res.breaking_changes)


# =========================================================================
# Class & Method Contract Verifications
# =========================================================================

def test_removing_public_class_method_triggers_breaking_change(empty_gate):
    old_code = (
        "class OrderService:\n"
        "    def create_order(self, item_id: str) -> str:\n"
        "        return 'id'\n"
        "    def cancel_order(self, order_id: str) -> bool:\n"
        "        return True\n"
    )
    new_code = (
        "class OrderService:\n"
        "    def create_order(self, item_id: str) -> str:\n"
        "        return 'id'\n"
    )
    res = empty_gate.verify_change("src/order.py", old_code, new_code)
    assert any("cancel_order" in b.symbol_name for b in res.breaking_changes)


def test_modifying_method_parameters_in_class(empty_gate):
    old_code = (
        "class PaymentGateway:\n"
        "    def charge(self, amount: float) -> bool:\n"
        "        return True\n"
    )
    new_code = (
        "class PaymentGateway:\n"
        "    def charge(self, amount: float, currency: str) -> bool:\n"
        "        return True\n"
    )
    res = empty_gate.verify_change("src/payment.py", old_code, new_code)
    assert res.valid is False
    assert any("currency" in b.message for b in res.breaking_changes)


def test_force_override_allows_breaking_change(graph_with_callers):
    old_code = "def calculate_tax(amount: float) -> float:\n    return amount * 0.2\n"
    new_code = "def calculate_tax(amount: float, tax_code: str) -> float:\n    return amount * 0.2\n"
    res = graph_with_callers.verify_change("src/tax.py", old_code, new_code, force=True)
    assert res.valid is True
    assert len(res.breaking_changes) > 0  # Diagnostics recorded but not blocking


# =========================================================================
# Polyglot Delimiter & Syntax Tests
# =========================================================================

def test_polyglot_balanced_braces_passes(empty_gate):
    ts_code = "function handle(req: Request): Response { return new Response('OK'); }"
    res = empty_gate.verify_change("src/server.ts", "old content", ts_code)
    assert res.valid is True


def test_polyglot_unclosed_delimiter_fails(empty_gate):
    rust_code = "fn main() { println!(\"Unclosed brace\");"
    res = empty_gate.verify_change("src/main.rs", "old content", rust_code)
    assert res.valid is False
    assert any("Unclosed delimiter" in b.message for b in res.breaking_changes)


def test_polyglot_mismatched_delimiter_fails(empty_gate):
    go_code = "func test() { arr := []int{1, 2, 3] }"
    res = empty_gate.verify_change("src/main.go", "old content", go_code)
    assert res.valid is False
    assert any("Mismatched delimiter" in b.message for b in res.breaking_changes)
