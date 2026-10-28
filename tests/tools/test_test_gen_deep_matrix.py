"""Deep Matrix Tests for TestGenTool generating unit test skeletons."""

import pytest
from pathlib import Path
from prubeth.tools.domain.test_gen import TestGenTool


@pytest.fixture
def gen():
    return TestGenTool()


# =========================================================================
# Matrix: 20 Function Signatures
# =========================================================================

FUNCTION_SIGNATURES = [
    ("add", "x: int, y: int", "int"),
    ("find_user", "username: str", "dict"),
    ("process_batch", "items: list, timeout: float = 5.0", "bool"),
    ("connect", "host: str, port: int = 8080", "None"),
    ("is_valid", "token: str", "bool"),
    ("calculate_area", "width: float, height: float", "float"),
    ("parse_header", "raw: str", "tuple"),
    ("export_csv", "path: str, rows: list", "int"),
    ("health_check", "", "dict"),
    ("retry_operation", "func: Any, max_retries: int = 3", "Any"),
]

@pytest.mark.parametrize("fn_name, params, ret_type", FUNCTION_SIGNATURES)
def test_matrix_test_gen_functions(tmp_path: Path, gen, fn_name, params, ret_type):
    f = tmp_path / f"svc_{fn_name}.py"
    f.write_text(f"def {fn_name}({params}) -> {ret_type}:\n    '''Docstring for {fn_name}.'''\n    return None\n", encoding="utf-8")

    res = gen.execute({"file_path": str(f), "symbol_name": fn_name})
    assert res.success is True
    assert f"def test_{fn_name}_baseline():" in res.output
    assert f"def test_{fn_name}_edge_cases():" in res.output
    assert f"def test_{fn_name}_raises_on_invalid_input():" in res.output


# =========================================================================
# Matrix: 15 Class Signatures
# =========================================================================

CLASS_NAMES = [
    "UserManager",
    "DatabasePool",
    "HttpRouter",
    "CacheEngine",
    "SecurityAuditor",
    "TaskScheduler",
    "MetricsCollector",
    "ConfigLoader",
    "EventDispatcher",
    "PaymentGateway",
]

@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_matrix_test_gen_classes(tmp_path: Path, gen, cls_name):
    f = tmp_path / f"mgr_{cls_name.lower()}.py"
    f.write_text(f"class {cls_name}:\n    def __init__(self):\n        pass\n    def run(self):\n        return True\n", encoding="utf-8")

    res = gen.execute({"file_path": str(f), "symbol_name": cls_name})
    assert res.success is True
    assert "@pytest.fixture" in res.output
    assert f"def {cls_name.lower()}_instance():" in res.output
    assert f"test_{cls_name.lower()}_initialisation" in res.output
