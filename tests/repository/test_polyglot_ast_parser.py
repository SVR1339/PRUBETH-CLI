"""Tests for Polyglot AST Symbol Parser across Python, TypeScript, Go, Rust, and polyglot files."""

import pytest
from pathlib import Path
from prubeth.repository.ast_parser import (
    PolyglotASTParser,
    CodeSymbol,
    SymbolKind,
    PythonASTVisitor,
)


@pytest.fixture
def parser(tmp_path):
    return PolyglotASTParser(workspace_root=tmp_path)


# =========================================================================
# Python AST Parsing Tests
# =========================================================================

def test_parse_python_simple_function(parser, tmp_path):
    code = '''
def calculate_metrics(alpha: float, beta: int = 10) -> float:
    """Calculates synthetic benchmark scores."""
    result = alpha * beta
    print(result)
    return result
'''
    p = tmp_path / "metrics.py"
    p.write_text(code, encoding="utf-8")

    symbols = parser.parse_file(p)
    assert len(symbols) == 1
    s = symbols[0]
    assert s.name == "calculate_metrics"
    assert s.kind == SymbolKind.FUNCTION
    assert s.start_line == 2
    assert s.parameters == ["alpha", "beta"]
    assert s.return_type == "float"
    assert "Calculates synthetic benchmark scores." in s.docstring
    assert "print" in s.calls


def test_parse_python_async_function(parser, tmp_path):
    code = '''
async def fetch_remote_payload(url: str, timeout: int = 30):
    await client.get(url)
    return None
'''
    p = tmp_path / "async_net.py"
    p.write_text(code, encoding="utf-8")

    symbols = parser.parse_file(p)
    assert len(symbols) == 1
    s = symbols[0]
    assert s.name == "fetch_remote_payload"
    assert s.kind == SymbolKind.FUNCTION
    assert s.signature.startswith("async def fetch_remote_payload")
    assert "get" in s.calls


def test_parse_python_class_with_methods_and_decorators(parser, tmp_path):
    code = '''
@dataclass
class ModelGateway(BaseGateway):
    """Universal gateway for model routing."""
    provider: str

    @classmethod
    def create(cls, provider: str) -> "ModelGateway":
        return cls(provider)

    def route_request(self, payload: dict) -> bool:
        self.verify(payload)
        return True
'''
    p = tmp_path / "gateway.py"
    p.write_text(code, encoding="utf-8")

    symbols = parser.parse_file(p)
    # Expect 1 class + 2 methods = 3 symbols
    assert len(symbols) == 3

    cls_sym = next(s for s in symbols if s.name == "ModelGateway")
    assert cls_sym.kind == SymbolKind.CLASS
    assert cls_sym.bases == ["BaseGateway"]
    assert "dataclass" in cls_sym.decorators
    assert "Universal gateway" in cls_sym.docstring

    m1 = next(s for s in symbols if s.name == "create")
    assert m1.kind == SymbolKind.METHOD
    assert m1.parent_symbol == "ModelGateway"
    assert "classmethod" in m1.decorators

    m2 = next(s for s in symbols if s.name == "route_request")
    assert m2.kind == SymbolKind.METHOD
    assert m2.parent_symbol == "ModelGateway"
    assert "verify" in m2.calls


def test_parse_python_imports(parser, tmp_path):
    code = '''
import os
import sys as system
from pathlib import Path, PurePath
from prubeth.tools import base

def run():
    pass
'''
    p = tmp_path / "module_imp.py"
    p.write_text(code, encoding="utf-8")

    visitor = PythonASTVisitor("module_imp.py", code)
    import ast
    visitor.visit(ast.parse(code))

    imps = visitor.current_imports
    assert any(i["module"] == "os" for i in imps)
    assert any(i["module"] == "sys" and i["name"] == "system" for i in imps)
    assert any(i["module"] == "pathlib" and i["name"] == "Path" for i in imps)
    assert any(i["module"] == "prubeth.tools" and i["name"] == "base" for i in imps)


def test_parse_python_syntax_error_fallback(parser, tmp_path):
    # Malformed python code with broken syntax
    code = '''
def broken_fn(
    class BrokenClass:
'''
    p = tmp_path / "broken.py"
    p.write_text(code, encoding="utf-8")

    # Should not raise exception; falls back to regex scanner
    symbols = parser.parse_file(p)
    assert isinstance(symbols, list)


# =========================================================================
# JavaScript / TypeScript Parsing Tests
# =========================================================================

def test_parse_typescript_interfaces_and_classes(parser, tmp_path):
    ts_code = '''
import { EventEmitter } from 'events';

export interface IRuntimeConfig extends IBaseConfig {
    timeout: number;
    retries?: number;
}

export type StatusType = 'idle' | 'running' | 'terminated';

export class TaskRunner extends BaseRunner implements IRunnable {
    private isRunning: boolean = false;

    constructor(private config: IRuntimeConfig) {
        super();
    }

    public async executeTask(taskId: string): Promise<boolean> {
        this.emit('start', taskId);
        return true;
    }
}
'''
    p = tmp_path / "runner.ts"
    p.write_text(ts_code, encoding="utf-8")

    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]

    assert "IRuntimeConfig" in names
    iface = next(s for s in symbols if s.name == "IRuntimeConfig")
    assert iface.kind == SymbolKind.INTERFACE
    assert "IBaseConfig" in iface.bases

    assert "StatusType" in names
    alias = next(s for s in symbols if s.name == "StatusType")
    assert alias.kind == SymbolKind.TYPE_ALIAS

    assert "TaskRunner" in names
    cls_sym = next(s for s in symbols if s.name == "TaskRunner")
    assert cls_sym.kind == SymbolKind.CLASS
    assert "BaseRunner" in cls_sym.bases

    assert "executeTask" in names
    method_sym = next(s for s in symbols if s.name == "executeTask")
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_symbol == "TaskRunner"


def test_parse_javascript_functions_and_arrows(parser, tmp_path):
    js_code = '''
function computeHash(data, salt) {
    const raw = hash(data + salt);
    return raw;
}

const sendNotification = async (userId, msg) => {
    dispatch(userId, msg);
    return true;
};
'''
    p = tmp_path / "util.js"
    p.write_text(js_code, encoding="utf-8")

    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]
    assert "computeHash" in names
    assert "sendNotification" in names

    fn1 = next(s for s in symbols if s.name == "computeHash")
    assert fn1.kind == SymbolKind.FUNCTION
    assert fn1.parameters == ["data", "salt"]

    fn2 = next(s for s in symbols if s.name == "sendNotification")
    assert fn2.kind == SymbolKind.FUNCTION
    assert fn2.parameters == ["userId", "msg"]


# =========================================================================
# Go Parsing Tests
# =========================================================================

def test_parse_go_structs_interfaces_and_methods(parser, tmp_path):
    go_code = '''
package orchestrator

type EngineConfig struct {
    MaxWorkers int
    TimeoutSec int
}

type Worker interface {
    Process(taskID string) error
    Stop()
}

func (e *EngineConfig) Initialize() error {
    setupLogging()
    return nil
}

func SpawnCluster(workers int) (*EngineConfig, error) {
    cfg := &EngineConfig{MaxWorkers: workers}
    return cfg, nil
}
'''
    p = tmp_path / "engine.go"
    p.write_text(go_code, encoding="utf-8")

    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]

    assert "EngineConfig" in names
    struct_sym = next(s for s in symbols if s.name == "EngineConfig")
    assert struct_sym.kind == SymbolKind.STRUCT

    assert "Worker" in names
    iface_sym = next(s for s in symbols if s.name == "Worker")
    assert iface_sym.kind == SymbolKind.INTERFACE

    assert "Initialize" in names
    method_sym = next(s for s in symbols if s.name == "Initialize")
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_symbol == "EngineConfig"

    assert "SpawnCluster" in names
    fn_sym = next(s for s in symbols if s.name == "SpawnCluster")
    assert fn_sym.kind == SymbolKind.FUNCTION
    assert fn_sym.parameters == ["workers int"]


# =========================================================================
# Rust Parsing Tests
# =========================================================================

def test_parse_rust_structs_traits_and_impls(parser, tmp_path):
    rs_code = '''
pub struct ConnectionPool {
    size: usize,
}

pub enum ConnectionState {
    Active,
    Idle,
    Closed,
}

pub trait Communicator {
    fn send_payload(&self, data: &[u8]) -> Result<usize, String>;
}

impl ConnectionPool {
    pub fn new(size: usize) -> Self {
        allocate_pool(size);
        ConnectionPool { size }
    }

    pub async fn acquire(&self) -> bool {
        check_available();
        true
    }
}

pub fn global_diagnostics() {
    report_status();
}
'''
    p = tmp_path / "pool.rs"
    p.write_text(rs_code, encoding="utf-8")

    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]

    assert "ConnectionPool" in names
    s_sym = next(s for s in symbols if s.name == "ConnectionPool")
    assert s_sym.kind == SymbolKind.STRUCT

    assert "ConnectionState" in names
    e_sym = next(s for s in symbols if s.name == "ConnectionState")
    assert e_sym.kind == SymbolKind.ENUM

    assert "Communicator" in names
    t_sym = next(s for s in symbols if s.name == "Communicator")
    assert t_sym.kind == SymbolKind.TRAIT

    assert "new" in names
    m1 = next(s for s in symbols if s.name == "new")
    assert m1.kind == SymbolKind.METHOD
    assert m1.parent_symbol == "ConnectionPool"

    assert "acquire" in names
    m2 = next(s for s in symbols if s.name == "acquire")
    assert m2.kind == SymbolKind.METHOD
    assert m2.parent_symbol == "ConnectionPool"

    assert "global_diagnostics" in names
    fn_sym = next(s for s in symbols if s.name == "global_diagnostics")
    assert fn_sym.kind == SymbolKind.FUNCTION


# =========================================================================
# Generic Fallback and Edge Cases
# =========================================================================

def test_parse_generic_fallback_c_cpp(parser, tmp_path):
    cpp_code = '''
class MemoryArena {
    void* buffer;
};

void allocate_pages(int count) {
    malloc(count * 4096);
}
'''
    p = tmp_path / "arena.cpp"
    p.write_text(cpp_code, encoding="utf-8")

    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]
    assert "MemoryArena" in names
    assert "allocate_pages" in names


def test_parse_empty_and_nonexistent_files(parser, tmp_path):
    p_empty = tmp_path / "empty.py"
    p_empty.write_text("", encoding="utf-8")
    assert parser.parse_file(p_empty) == []

    p_nonexistent = tmp_path / "does_not_exist.py"
    assert parser.parse_file(p_nonexistent) == []


def test_code_symbol_to_dict_roundtrip():
    sym = CodeSymbol(
        name="test_symbol",
        kind=SymbolKind.FUNCTION,
        file_path="src/app.py",
        start_line=10,
        end_line=25,
        signature="def test_symbol(x: int) -> int",
        docstring="Test docstring",
        decorators=["lru_cache"],
        parameters=["x"],
        return_type="int",
        parent_symbol=None,
        calls=["print", "len"],
        imports=[{"module": "sys"}],
        bases=[],
        body_snippet="def test_symbol(x: int) -> int:\n    return x * 2",
    )
    d = sym.to_dict()
    assert d["name"] == "test_symbol"
    assert d["kind"] == "function"
    assert d["start_line"] == 10
    assert d["calls"] == ["print", "len"]
    assert d["decorators"] == ["lru_cache"]


# =========================================================================
# Matrix Parametrized Syntax Permutation Tests
# =========================================================================

PYTHON_PARAM_MATRIX = [
    (f"def func_{i}(a{i}: int) -> int:\n    return a{i} * 2\n", f"func_{i}", [f"a{i}"])
    for i in range(25)
]

@pytest.mark.parametrize("code,fn_name,params", PYTHON_PARAM_MATRIX)
def test_python_parameter_matrix(parser, tmp_path, code, fn_name, params):
    p = tmp_path / f"{fn_name}.py"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert len(symbols) == 1
    assert symbols[0].name == fn_name
    assert symbols[0].parameters == params


TS_INTERFACE_MATRIX = [
    (f"export interface IService_{i} {{\n    execute_{i}(): void;\n}}\n", f"IService_{i}")
    for i in range(20)
]

@pytest.mark.parametrize("code,iface_name", TS_INTERFACE_MATRIX)
def test_ts_interface_matrix(parser, tmp_path, code, iface_name):
    p = tmp_path / f"{iface_name}.ts"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert any(s.name == iface_name and s.kind == SymbolKind.INTERFACE for s in symbols)


GO_FUNC_MATRIX = [
    (f"package main\nfunc HandleRequest_{i}(id_{i} string) bool {{\n    return true\n}}\n", f"HandleRequest_{i}")
    for i in range(20)
]

@pytest.mark.parametrize("code,func_name", GO_FUNC_MATRIX)
def test_go_func_matrix(parser, tmp_path, code, func_name):
    p = tmp_path / f"{func_name}.go"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert any(s.name == func_name and s.kind == SymbolKind.FUNCTION for s in symbols)


RUST_STRUCT_MATRIX = [
    (f"pub struct Container_{i} {{\n    id: u64,\n}}\n", f"Container_{i}")
    for i in range(20)
]

@pytest.mark.parametrize("code,struct_name", RUST_STRUCT_MATRIX)
def test_rust_struct_matrix(parser, tmp_path, code, struct_name):
    p = tmp_path / f"{struct_name}.rs"
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert any(s.name == struct_name and s.kind == SymbolKind.STRUCT for s in symbols)
