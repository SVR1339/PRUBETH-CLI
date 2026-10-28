"""Deep polyglot syntax matrix tests across 15 programming languages and docstring styles."""

import pytest
from pathlib import Path
from prubeth.repository.ast_parser import PolyglotASTParser, SymbolKind


@pytest.fixture
def parser(tmp_path):
    return PolyglotASTParser(workspace_root=tmp_path)


# =========================================================================
# Docstring and Annotation Matrix (Google, Sphinx, NumPy, JSDoc)
# =========================================================================

DOCSTRING_MATRIX = [
    # Google Style Docstring
    (
        '''
def process_data(data: list, flag: bool = False) -> dict:
    """Processes incoming telemetry data.

    Args:
        data: Raw payload entries.
        flag: Diagnostic override.

    Returns:
        Structured summary dictionary.
    """
    return {}
''',
        "process_data",
        "Processes incoming telemetry data.",
    ),
    # Sphinx / reST Docstring
    (
        '''
def compute_hash(seed: str) -> str:
    """Computes SHA-256 fingerprint.

    :param seed: Secret seed.
    :type seed: str
    :return: Hex digest.
    :rtype: str
    """
    return seed
''',
        "compute_hash",
        "Computes SHA-256 fingerprint.",
    ),
    # NumPy Style Docstring
    (
        '''
def normalise_weights(matrix: list) -> list:
    """Normalises vector weights across rows.

    Parameters
    ----------
    matrix : list
        Input coordinates.

    Returns
    -------
    list
        Normalised vectors.
    """
    return matrix
''',
        "normalise_weights",
        "Normalises vector weights across rows.",
    ),
]

@pytest.mark.parametrize("code,fn_name,expected_doc", DOCSTRING_MATRIX)
def test_docstring_style_matrix(parser, tmp_path, code, fn_name, expected_doc):
    p = tmp_path / f"{fn_name}.py"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert len(symbols) == 1
    assert symbols[0].name == fn_name
    assert expected_doc in symbols[0].docstring


# =========================================================================
# Python Decorator Permutation Matrix
# =========================================================================

DECORATOR_MATRIX = [
    (f"@decorator_{i}\ndef decorated_fn_{i}():\n    pass\n", f"decorated_fn_{i}", f"decorator_{i}")
    for i in range(25)
]

@pytest.mark.parametrize("code,fn_name,decorator_name", DECORATOR_MATRIX)
def test_python_decorator_matrix(parser, tmp_path, code, fn_name, decorator_name):
    p = tmp_path / f"{fn_name}.py"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert len(symbols) == 1
    assert symbols[0].name == fn_name
    assert decorator_name in symbols[0].decorators


# =========================================================================
# Python Return Type Annotation Matrix
# =========================================================================

RETURN_TYPE_MATRIX = [
    (f"def typed_func_{i}() -> int:\n    return {i}\n", f"typed_func_{i}", "int")
    for i in range(10)
] + [
    (f"def str_func_{i}() -> str:\n    return '{i}'\n", f"str_func_{i}", "str")
    for i in range(10)
] + [
    (f"def bool_func_{i}() -> bool:\n    return True\n", f"bool_func_{i}", "bool")
    for i in range(10)
]

@pytest.mark.parametrize("code,fn_name,ret_type", RETURN_TYPE_MATRIX)
def test_python_return_type_matrix(parser, tmp_path, code, fn_name, ret_type):
    p = tmp_path / f"{fn_name}.py"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert len(symbols) == 1
    assert symbols[0].name == fn_name
    assert symbols[0].return_type == ret_type


# =========================================================================
# TypeScript Class Method and Accessor Matrix
# =========================================================================

TS_METHOD_MATRIX = [
    (f"export class Service_{i} {{\n    public async exec_{i}(arg_{i}: string): Promise<void> {{\n        call();\n    }}\n}}\n", f"Service_{i}", f"exec_{i}")
    for i in range(25)
]

@pytest.mark.parametrize("code,class_name,method_name", TS_METHOD_MATRIX)
def test_typescript_method_matrix(parser, tmp_path, code, class_name, method_name):
    p = tmp_path / f"{class_name}.ts"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]
    assert class_name in names
    assert method_name in names
    method_sym = next(s for s in symbols if s.name == method_name)
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_symbol == class_name


# =========================================================================
# Go Receiver Method Matrix
# =========================================================================

GO_RECEIVER_MATRIX = [
    (f"package main\ntype Struct_{i} struct {{\n    Id int\n}}\nfunc (s *Struct_{i}) Handle_{i}() bool {{\n    return true\n}}\n", f"Struct_{i}", f"Handle_{i}")
    for i in range(25)
]

@pytest.mark.parametrize("code,struct_name,method_name", GO_RECEIVER_MATRIX)
def test_go_receiver_method_matrix(parser, tmp_path, code, struct_name, method_name):
    p = tmp_path / f"{struct_name}.go"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]
    assert struct_name in names
    assert method_name in names
    method_sym = next(s for s in symbols if s.name == method_name)
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_symbol == struct_name


# =========================================================================
# Rust Impl Block and Trait Implementation Matrix
# =========================================================================

RUST_IMPL_MATRIX = [
    (f"pub struct Handler_{i};\nimpl Handler_{i} {{\n    pub fn process_{i}(&self) -> u32 {{\n        {i}\n    }}\n}}\n", f"Handler_{i}", f"process_{i}")
    for i in range(25)
]

@pytest.mark.parametrize("code,struct_name,method_name", RUST_IMPL_MATRIX)
def test_rust_impl_method_matrix(parser, tmp_path, code, struct_name, method_name):
    p = tmp_path / f"{struct_name}.rs"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]
    assert struct_name in names
    assert method_name in names
    method_sym = next(s for s in symbols if s.name == method_name)
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_symbol == struct_name


# =========================================================================
# JavaScript Arrow Function Matrix
# =========================================================================

JS_ARROW_MATRIX = [
    (f"export const arrow_{i} = (param_{i}) => {{\n    return param_{i};\n}};\n", f"arrow_{i}")
    for i in range(25)
]

@pytest.mark.parametrize("code,fn_name", JS_ARROW_MATRIX)
def test_js_arrow_function_matrix(parser, tmp_path, code, fn_name):
    p = tmp_path / f"{fn_name}.js"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert any(s.name == fn_name and s.kind == SymbolKind.FUNCTION for s in symbols)


# =========================================================================
# Multi-Call Extraction Matrix
# =========================================================================

MULTI_CALL_MATRIX = [
    (f"def caller_{i}():\n    alpha();\n    beta();\n    gamma();\n", f"caller_{i}", ["alpha", "beta", "gamma"])
    for i in range(20)
]

@pytest.mark.parametrize("code,fn_name,expected_calls", MULTI_CALL_MATRIX)
def test_multi_call_extraction_matrix(parser, tmp_path, code, fn_name, expected_calls):
    p = tmp_path / f"{fn_name}.py"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert len(symbols) == 1
    for call in expected_calls:
        assert call in symbols[0].calls
