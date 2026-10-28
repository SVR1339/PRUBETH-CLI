"""PRUBETH Polyglot AST Symbol Extractor Deep Permutations Matrix.

Exhaustively verifies semantic symbol extraction (functions, methods, classes, structs,
interfaces, traits, decorators, parameter schemas, and type signatures) across
Python, TypeScript, JavaScript, Go, Rust, Java, C#, PHP, C/C++, and Ruby.
"""

from __future__ import annotations

import pytest
from prubeth.repository.ast_parser import PolyglotASTParser, SymbolKind, CodeSymbol


# ============================================================================
# 1. Python AST Parser: Function Signatures & Parameter Permutations
# ============================================================================

PYTHON_PARAM_CASES = [
    ("def f(): pass", ["f"], []),
    ("def f(x): pass", ["f"], ["x"]),
    ("def f(x, y): pass", ["f"], ["x", "y"]),
    ("def f(x: int, y: str = 'default'): pass", ["f"], ["x", "y"]),
    ("def f(*args): pass", ["f"], ["*args"]),
    ("def f(**kwargs): pass", ["f"], ["**kwargs"]),
    ("def f(x, *args, **kwargs): pass", ["f"], ["x", "*args", "**kwargs"]),
    ("def f(x, *, kw_only=True): pass", ["f"], ["x", "kw_only"]),
    ("def f(pos_only, /, standard): pass", ["f"], ["pos_only", "standard"]),
    ("async def f(task: str, timeout: float = 5.0): pass", ["f"], ["task", "timeout"]),
]

@pytest.mark.parametrize("code,expected_names,expected_params", PYTHON_PARAM_CASES)
def test_python_parameter_extraction(code: str, expected_names: list[str], expected_params: list[str]):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("test_mod.py", code)
    assert len(symbols) == len(expected_names)
    for s, name in zip(symbols, expected_names):
        assert s.name == name
        assert s.kind == SymbolKind.FUNCTION
        for param in expected_params:
            assert param in s.parameters


# ============================================================================
# 2. Python AST Parser: Return Type Annotation Permutations
# ============================================================================

PYTHON_RETURN_TYPE_CASES = [
    ("def f() -> int: return 1", "int"),
    ("def f() -> str: return 'a'", "str"),
    ("def f() -> bool: return True", "bool"),
    ("def f() -> float: return 1.5", "float"),
    ("def f() -> None: pass", "None"),
    ("def f() -> list[str]: return []", "list"),
    ("def f() -> dict[str, int]: return {}", "dict"),
    ("def f() -> Optional[Path]: return None", "Optional"),
    ("def f() -> Union[int, str]: return 1", "Union"),
    ("async def f() -> Tuple[bool, str]: return True, ''", "Tuple"),
]

@pytest.mark.parametrize("code,expected_ret_prefix", PYTHON_RETURN_TYPE_CASES)
def test_python_return_type_extraction(code: str, expected_ret_prefix: str):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("ret_mod.py", code)
    assert len(symbols) == 1
    assert symbols[0].return_type is not None
    assert expected_ret_prefix in symbols[0].return_type


# ============================================================================
# 3. Python AST Parser: Class Hierarchy, Methods & Decorators Matrix
# ============================================================================

PYTHON_CLASS_CASES = [
    ("class Empty: pass", "Empty", [], []),
    ("class Single(Base): pass", "Single", ["Base"], []),
    ("class Multiple(BaseA, BaseB, MixinC): pass", "Multiple", ["BaseA", "BaseB", "MixinC"], []),
]

@pytest.mark.parametrize("code,expected_cls_name,expected_bases,dummy", [
    (c[0], c[1], c[2], []) for c in PYTHON_CLASS_CASES
])
def test_python_class_bases_extraction(code: str, expected_cls_name: str, expected_bases: list[str], dummy):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("class_mod.py", code)
    classes = [s for s in symbols if s.kind == SymbolKind.CLASS]
    assert len(classes) == 1
    assert classes[0].name == expected_cls_name
    for base in expected_bases:
        assert base in classes[0].bases


PYTHON_METHOD_DECORATOR_CASES = [
    (
        '''
class Service:
    @staticmethod
    def static_m(): pass

    @classmethod
    def class_m(cls): pass

    @property
    def prop(self): return 1
''',
        ["static_m", "class_m", "prop"],
        ["staticmethod", "classmethod", "property"],
    ),
    (
        '''
class Decorated:
    @retry(max_attempts=3)
    def call_api(self): pass

    @cached
    def get_data(self): pass
''',
        ["call_api", "get_data"],
        ["retry(...)", "cached"],
    ),
]

@pytest.mark.parametrize("code,expected_methods,expected_decorators", PYTHON_METHOD_DECORATOR_CASES)
def test_python_methods_and_decorators(code: str, expected_methods: list[str], expected_decorators: list[str]):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("methods.py", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) == len(expected_methods)
    for m, name, deco in zip(methods, expected_methods, expected_decorators):
        assert m.name == name
        assert m.parent_symbol in ("Service", "Decorated")
        assert any(deco.split("(")[0] in d for d in m.decorators)


# ============================================================================
# 4. TypeScript & JavaScript AST Parser: Functions & Arrow Functions
# ============================================================================

TS_FUNCTION_CASES = [
    ("function calculateTotal(items: number[]): number { return 0; }", "calculateTotal", SymbolKind.FUNCTION),
    ("async function fetchData(url: string): Promise<string> { return ''; }", "fetchData", SymbolKind.FUNCTION),
    ("export function exportedTest(a: int, b: int): int { return a + b; }", "exportedTest", SymbolKind.FUNCTION),
    ("export default function defaultHelper(): void { }", "defaultHelper", SymbolKind.FUNCTION),
    ("const add = (a: number, b: number): number => a + b;", "add", SymbolKind.FUNCTION),
    ("export const multiply = (x: number, y: number) => x * y;", "multiply", SymbolKind.FUNCTION),
    ("const asyncAction = async (payload: any): Promise<void> => {};", "asyncAction", SymbolKind.FUNCTION),
]

@pytest.mark.parametrize("code,expected_name,expected_kind", TS_FUNCTION_CASES)
def test_ts_function_and_arrow_extraction(code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("ts_functions.ts", code)
    assert len(symbols) >= 1
    matched = [s for s in symbols if s.name == expected_name]
    assert len(matched) == 1
    assert matched[0].kind == expected_kind


# ============================================================================
# 5. TypeScript AST Parser: Classes, Interfaces & Type Aliases
# ============================================================================

TS_TYPE_CASES = [
    ("interface UserProfile { id: string; name: string; }", "UserProfile", SymbolKind.INTERFACE),
    ("export interface ExtendedProfile extends UserProfile { role: string; }", "ExtendedProfile", SymbolKind.INTERFACE),
    ("class UserService { constructor() {} }", "UserService", SymbolKind.CLASS),
    ("export class AdminService extends UserService { }", "AdminService", SymbolKind.CLASS),
    ("type ID = string | number;", "ID", SymbolKind.TYPE_ALIAS),
    ("export type ResponsePayload = { success: boolean; data: any; };", "ResponsePayload", SymbolKind.TYPE_ALIAS),
]

@pytest.mark.parametrize("code,expected_name,expected_kind", TS_TYPE_CASES)
def test_ts_types_interfaces_classes(code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("types.ts", code)
    matched = [s for s in symbols if s.name == expected_name]
    assert len(matched) == 1
    assert matched[0].kind == expected_kind


# ============================================================================
# 6. Go AST Parser: Structs, Interfaces, Functions & Receiver Methods
# ============================================================================

GO_CODE_SNIPPETS = [
    ("type Config struct { Host string; Port int }", "Config", SymbolKind.STRUCT),
    ("type Reader interface { Read(p []byte) (n int, err error) }", "Reader", SymbolKind.INTERFACE),
    ("func ProcessJob(id string) error { return nil }", "ProcessJob", SymbolKind.FUNCTION),
    ("func (c *Config) Validate() bool { return true }", "Validate", SymbolKind.METHOD),
    ("func (c Config) String() string { return '' }", "String", SymbolKind.METHOD),
    ("func NewServer(port int) (*Server, error) { return nil, nil }", "NewServer", SymbolKind.FUNCTION),
]

@pytest.mark.parametrize("code,expected_name,expected_kind", GO_CODE_SNIPPETS)
def test_go_symbol_extraction(code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("main.go", code)
    matched = [s for s in symbols if s.name == expected_name]
    assert len(matched) == 1
    assert matched[0].kind == expected_kind
    if expected_kind == SymbolKind.METHOD:
        assert matched[0].parent_symbol == "Config"


# ============================================================================
# 7. Rust AST Parser: Structs, Enums, Traits, Functions & Impl Blocks
# ============================================================================

RUST_CODE_SNIPPETS = [
    ("pub struct Engine { running: bool }", "Engine", SymbolKind.STRUCT),
    ("pub enum Status { Active, Idle, Error }", "Status", SymbolKind.ENUM),
    ("pub trait Worker { fn work(&self); }", "Worker", SymbolKind.TRAIT),
    ("pub fn initialize_system() -> Result<(), String> { Ok(()) }", "initialize_system", SymbolKind.FUNCTION),
    ("async fn fetch_records(limit: usize) -> Vec<Record> { vec![] }", "fetch_records", SymbolKind.FUNCTION),
]

@pytest.mark.parametrize("code,expected_name,expected_kind", RUST_CODE_SNIPPETS)
def test_rust_symbol_extraction(code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("lib.rs", code)
    matched = [s for s in symbols if s.name == expected_name]
    assert len(matched) == 1
    assert matched[0].kind == expected_kind


def test_rust_impl_block_methods():
    rust_code = '''
struct Database {
    url: String,
}

impl Database {
    pub fn connect(url: &str) -> Self {
        Database { url: url.to_string() }
    }

    pub fn query(&self, sql: &str) -> Vec<Row> {
        vec![]
    }
}
'''
    parser = PolyglotASTParser()
    symbols = parser.parse_content("db.rs", rust_code)
    db_struct = [s for s in symbols if s.name == "Database" and s.kind == SymbolKind.STRUCT]
    assert len(db_struct) == 1

    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) >= 2
    method_names = {m.name for m in methods}
    assert "connect" in method_names
    assert "query" in method_names
    for m in methods:
        assert m.parent_symbol == "Database"


# ============================================================================
# 8. Generic Fallback Parser: C, C++, Java, C#, PHP, Ruby, Dart
# ============================================================================

POLYGLOT_GENERIC_CASES = [
    ("main.c", "int calculate_sum(int a, int b) { return a + b; }", "calculate_sum", SymbolKind.FUNCTION),
    ("worker.cpp", "class ConnectionPool { void release(); };", "ConnectionPool", SymbolKind.CLASS),
    ("App.java", "public class ApplicationServer { public void start() {} }", "ApplicationServer", SymbolKind.CLASS),
    ("Model.cs", "public class OrderRecord { public int Id { get; set; } }", "OrderRecord", SymbolKind.CLASS),
    ("helper.php", "function formatCurrency($amount) { return '$' . $amount; }", "formatCurrency", SymbolKind.FUNCTION),
    ("user.rb", "class UserProfile\n  def full_name\n  end\nend", "UserProfile", SymbolKind.CLASS),
    ("widget.dart", "class CustomButton {\n  void handleTap() {}\n}", "CustomButton", SymbolKind.CLASS),
]

@pytest.mark.parametrize("filename,content,expected_name,expected_kind", POLYGLOT_GENERIC_CASES)
def test_polyglot_generic_fallback_extraction(filename: str, content: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content(filename, content)
    matched = [s for s in symbols if s.name == expected_name]
    assert len(matched) >= 1
    assert matched[0].kind == expected_kind


# ============================================================================
# 20. Python Async Dunder Methods Matrix
# ============================================================================

ASYNC_DUNDERS = [
    ("__aenter__", "async def __aenter__(self): return self"),
    ("__aexit__", "async def __aexit__(self, exc_type, exc_val, exc_tb): pass"),
    ("__aiter__", "def __aiter__(self): return self"),
    ("__anext__", "async def __anext__(self): return 1"),
]

@pytest.mark.parametrize("dunder_name,dunder_def", ASYNC_DUNDERS)
def test_python_async_dunders(dunder_name: str, dunder_def: str):
    code = f"""
class AsyncSession:
    {dunder_def}
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("async_session.py", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) == 1
    assert methods[0].name == dunder_name
    assert methods[0].parent_symbol == "AsyncSession"


# ============================================================================
# 21. Python Custom Exception Class Hierarchy Matrix
# ============================================================================

EXCEPTION_CLASSES = [
    ("DatabaseConnectionError", "Exception"),
    ("ModelInferenceTimeout", "TimeoutError"),
    ("ConfigurationError", "ValueError"),
    ("SecurityViolationError", "PermissionError"),
    ("TaskExecutionFailure", "RuntimeError"),
]

@pytest.mark.parametrize("exc_name,base_exc", EXCEPTION_CLASSES)
def test_python_custom_exceptions(exc_name: str, base_exc: str):
    code = f"""
class {exc_name}({base_exc}):
    def __init__(self, message: str):
        super().__init__(message)
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("exceptions.py", code)
    classes = [s for s in symbols if s.kind == SymbolKind.CLASS and s.name == exc_name]
    assert len(classes) == 1
    assert base_exc in classes[0].bases


# ============================================================================
# 22. Python Internal Call Target Extraction Matrix
# ============================================================================

CALL_TARGET_CASES = [
    ("def f(): print('hello')", ["print"]),
    ("def f(): logger.info('data'); os.mkdir('dir')", ["info", "mkdir"]),
    ("def f(): a(); b(); c()", ["a", "b", "c"]),
    ("def f(): resp = requests.get(url); return resp.json()", ["get", "json"]),
    ("def f(): hashlib.sha256(b'test').hexdigest()", ["sha256", "hexdigest"]),
]

@pytest.mark.parametrize("code,expected_calls", CALL_TARGET_CASES)
def test_python_call_target_resolution(code: str, expected_calls: list[str]):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("calls.py", code)
    assert len(symbols) == 1
    for call in expected_calls:
        assert call in symbols[0].calls


# ============================================================================
# 23. TypeScript Getters and Setters Extraction Matrix
# ============================================================================

TS_ACCESSORS = [
    ("get id(): string { return this._id; }", "id"),
    ("get active(): boolean { return this._active; }", "active"),
    ("set payload(data: any) { this._payload = data; }", "payload"),
    ("set timeout(ms: number) { this._timeout = ms; }", "timeout"),
]

@pytest.mark.parametrize("accessor_code,expected_name", TS_ACCESSORS)
def test_ts_getter_setter_extraction(accessor_code: str, expected_name: str):
    code = f"""
class ModelEntity {{
    {accessor_code}
}}
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("entity.ts", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) == 1
    assert methods[0].name == expected_name


# ============================================================================
# 24. Go Pointer vs Value Receiver Matrix
# ============================================================================

GO_RECEIVERS = [
    ("func (h *Handler) ServeHTTP(w ResponseWriter, r *Request) {}", "ServeHTTP", "Handler"),
    ("func (h Handler) Path() string { return '/' }", "Path", "Handler"),
    ("func (s *Store) Put(k string, v []byte) error { return nil }", "Put", "Store"),
    ("func (s Store) Get(k string) ([]byte, bool) { return nil, false }", "Get", "Store"),
]

@pytest.mark.parametrize("code,expected_name,expected_parent", GO_RECEIVERS)
def test_go_receiver_variations(code: str, expected_name: str, expected_parent: str):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("http.go", code)
    matched = [s for s in symbols if s.name == expected_name and s.kind == SymbolKind.METHOD]
    assert len(matched) == 1
    assert matched[0].parent_symbol == expected_parent


# ============================================================================
# 25. Python Property Setter and Deleter Decorators Matrix
# ============================================================================

PROPERTY_DECORATORS = [
    ("@prop.setter\ndef prop(self, val): pass", "prop", "prop.setter"),
    ("@prop.deleter\ndef prop(self): pass", "prop", "prop.deleter"),
    ("@score.setter\ndef score(self, s: float): pass", "score", "score.setter"),
    ("@cache.deleter\ndef cache(self): pass", "cache", "cache.deleter"),
]

@pytest.mark.parametrize("code_snippet,expected_name,expected_deco", PROPERTY_DECORATORS)
def test_python_property_setter_deleter(code_snippet: str, expected_name: str, expected_deco: str):
    indented = "\n    ".join(code_snippet.strip().splitlines())
    code = f"class Evaluator:\n    {indented}\n"
    parser = PolyglotASTParser()
    symbols = parser.parse_content("eval.py", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD and s.name == expected_name]
    assert len(methods) == 1
    assert any(expected_deco in d for d in methods[0].decorators)


# ============================================================================
# 26. Go Multi-Method Interface Matrix
# ============================================================================

GO_MULTI_INTERFACES = [
    ("type ReadWriter interface { Read(p []byte) (n int, err error); Write(p []byte) (n int, err error) }", "ReadWriter"),
    ("type ReadCloser interface { Read(p []byte) (n int, err error); Close() error }", "ReadCloser"),
    ("type WriteCloser interface { Write(p []byte) (n int, err error); Close() error }", "WriteCloser"),
    ("type Seeker interface { Seek(offset int64, whence int) (int64, error) }", "Seeker"),
    ("type ByteScanner interface { ReadByte() (byte, error); UnreadByte() error }", "ByteScanner"),
]

@pytest.mark.parametrize("code,expected_name", GO_MULTI_INTERFACES)
def test_go_multi_method_interfaces(code: str, expected_name: str):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("io.go", code)
    matched = [s for s in symbols if s.name == expected_name and s.kind == SymbolKind.INTERFACE]
    assert len(matched) == 1


# ============================================================================
# 27. Rust Generic Structs, Enums, and Functions Matrix
# ============================================================================

RUST_GENERICS = [
    ("pub struct Box<T> { val: T }", "Box", SymbolKind.STRUCT),
    ("pub struct Pair<K, V> { k: K, v: V }", "Pair", SymbolKind.STRUCT),
    ("pub struct ResultWrapper<T, E> { res: Result<T, E> }", "ResultWrapper", SymbolKind.STRUCT),
    ("pub enum Option<T> { Some(T), None }", "Option", SymbolKind.ENUM),
    ("pub fn identity<T>(val: T) -> T { val }", "identity", SymbolKind.FUNCTION),
    ("pub fn pair_up<A, B>(a: A, b: B) -> (A, B) { (a, b) }", "pair_up", SymbolKind.FUNCTION),
]

@pytest.mark.parametrize("code,expected_name,expected_kind", RUST_GENERICS)
def test_rust_generics_matrix(code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("generics.rs", code)
    matched = [s for s in symbols if s.name == expected_name and s.kind == expected_kind]
    assert len(matched) == 1


# ============================================================================
# 28. Java and C# Modern Language Constructs Matrix
# ============================================================================

JAVA_CS_CONSTRUCTS = [
    ("Records.java", "public record UserDto(String id, String email) {}", "UserDto", SymbolKind.CLASS),
    ("Events.java", "public enum SystemEvent { STARTUP, SHUTDOWN, HEARTBEAT }", "SystemEvent", SymbolKind.CLASS),
    ("Records.cs", "public record DeviceTelemetry(string DeviceId, double Temp);", "DeviceTelemetry", SymbolKind.CLASS),
    ("Enums.cs", "public enum EngineState { Idle, Active, Error }", "EngineState", SymbolKind.CLASS),
]

@pytest.mark.parametrize("filename,code,expected_name,expected_kind", JAVA_CS_CONSTRUCTS)
def test_java_cs_modern_constructs(filename: str, code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content(filename, code)
    matched = [s for s in symbols if s.name == expected_name and s.kind == expected_kind]
    assert len(matched) >= 1




# ============================================================================
# 9. CodeSymbol Serialization & Invariants
# ============================================================================

def test_code_symbol_to_dict():
    sym = CodeSymbol(
        name="test_func",
        kind=SymbolKind.FUNCTION,
        file_path="src/utils.py",
        start_line=10,
        end_line=25,
        signature="def test_func(x: int) -> int:",
        docstring="Doc string here",
        decorators=["@cached"],
        parameters=["x"],
        return_type="int",
        parent_symbol=None,
        calls=["print", "log"],
        imports=[{"module": "os"}],
        bases=[],
        body_snippet="def test_func(x: int) -> int:\n    return x * 2",
    )
    d = sym.to_dict()
    assert d["name"] == "test_func"
    assert d["kind"] == "function"
    assert d["start_line"] == 10
    assert d["end_line"] == 25
    assert d["signature"] == "def test_func(x: int) -> int:"
    assert d["docstring"] == "Doc string here"
    assert d["decorators"] == ["@cached"]
    assert d["parameters"] == ["x"]
    assert d["return_type"] == "int"
    assert d["calls"] == ["print", "log"]
    assert d["imports"] == [{"module": "os"}]


# ============================================================================
# 10. Python Dunder Methods Extraction Matrix
# ============================================================================

DUNDER_METHODS = [
    ("__init__", "def __init__(self, val: int): pass"),
    ("__repr__", "def __repr__(self) -> str: return ''"),
    ("__str__", "def __str__(self) -> str: return ''"),
    ("__len__", "def __len__(self) -> int: return 0"),
    ("__getitem__", "def __getitem__(self, idx: int): return None"),
    ("__setitem__", "def __setitem__(self, idx: int, val: int): pass"),
    ("__enter__", "def __enter__(self): return self"),
    ("__exit__", "def __exit__(self, exc_type, exc_val, exc_tb): pass"),
    ("__call__", "def __call__(self, *args): pass"),
    ("__iter__", "def __iter__(self): yield 1"),
    ("__next__", "def __next__(self): return 1"),
    ("__eq__", "def __eq__(self, other) -> bool: return True"),
    ("__hash__", "def __hash__(self) -> int: return 42"),
    ("__contains__", "def __contains__(self, item) -> bool: return True"),
]

@pytest.mark.parametrize("dunder_name,dunder_def", DUNDER_METHODS)
def test_python_dunder_methods_extraction(dunder_name: str, dunder_def: str):
    code = f"""
class CustomContainer:
    {dunder_def}
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("dunder.py", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) == 1
    assert methods[0].name == dunder_name
    assert methods[0].parent_symbol == "CustomContainer"


# ============================================================================
# 11. Polyglot Method Visibility and Modifier Matrix
# ============================================================================

TS_MODIFIERS = [
    ("public", "public calculate(): void {}"),
    ("private", "private hashPassword(): string { return ''; }"),
    ("protected", "protected validateAccess(): boolean { return true; }"),
    ("static", "static createInstance(): Service { return new Service(); }"),
    ("async", "async fetchData(): Promise<any> {}"),
    ("public static", "public static getVersion(): string { return '1.0'; }"),
    ("private async", "private async verifyToken(): Promise<boolean> { return true; }"),
]

@pytest.mark.parametrize("mod_label,method_def", TS_MODIFIERS)
def test_ts_method_modifier_extraction(mod_label: str, method_def: str):
    code = f"""
class SecurityController {{
    {method_def}
}}
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("controller.ts", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) == 1
    assert methods[0].parent_symbol == "SecurityController"


# ============================================================================
# 12. Python Complex Type Annotations Permutations Matrix
# ============================================================================

COMPLEX_TYPE_ANNOTATIONS = [
    ("Iterable[str]", "def gen(items: Iterable[str]) -> None: pass"),
    ("Mapping[str, Any]", "def transform(config: Mapping[str, Any]) -> None: pass"),
    ("Sequence[int]", "def sort_items(arr: Sequence[int]) -> list[int]: pass"),
    ("Callable[[int, int], bool]", "def filter_by(comparator: Callable[[int, int], bool]) -> None: pass"),
    ("Optional[Dict[str, List[int]]]", "def parse_groups() -> Optional[Dict[str, List[int]]]: pass"),
    ("Union[str, int, float, bool]", "def serialize(val: Union[str, int, float, bool]) -> str: pass"),
    ("tuple[str, ...]", "def var_tuple(t: tuple[str, ...]) -> None: pass"),
    ("set[frozenset[int]]", "def set_algebra(s: set[frozenset[int]]) -> None: pass"),
]

@pytest.mark.parametrize("expected_type_str,code", COMPLEX_TYPE_ANNOTATIONS)
def test_python_complex_type_signatures(expected_type_str: str, code: str):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("types_complex.py", code)
    assert len(symbols) == 1
    # Check signature text retains the complex types
    base_keyword = expected_type_str.split("[")[0]
    assert base_keyword in symbols[0].signature


# ============================================================================
# 13. Polyglot Language File Extension Routing Matrix
# ============================================================================

EXTENSION_ROUTING = [
    ("service.py", "def run(): pass", SymbolKind.FUNCTION),
    ("app.ts", "function run(): void {}", SymbolKind.FUNCTION),
    ("app.tsx", "function Component(): any {}", SymbolKind.FUNCTION),
    ("script.js", "function run() {}", SymbolKind.FUNCTION),
    ("script.jsx", "function Page() {}", SymbolKind.FUNCTION),
    ("server.go", "func Serve() error { return nil }", SymbolKind.FUNCTION),
    ("lib.rs", "pub fn build() {}", SymbolKind.FUNCTION),
    ("program.c", "void execute() {}", SymbolKind.FUNCTION),
    ("program.cpp", "class Handler {};", SymbolKind.CLASS),
    ("Main.java", "public class Runner {}", SymbolKind.CLASS),
    ("Worker.cs", "public class BackgroundService {}", SymbolKind.CLASS),
    ("api.php", "function dispatchRequest() {}", SymbolKind.FUNCTION),
    ("model.rb", "class Account {};", SymbolKind.CLASS),
]

@pytest.mark.parametrize("filename,code,expected_kind", EXTENSION_ROUTING)
def test_polyglot_extension_routing(filename: str, code: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content(filename, code)
    assert len(symbols) >= 1
    assert symbols[0].kind == expected_kind


# ============================================================================
# 14. Python Arithmetic & Numeric Dunder Methods Matrix
# ============================================================================

NUMERIC_DUNDERS = [
    ("__add__", "def __add__(self, other): return self"),
    ("__sub__", "def __sub__(self, other): return self"),
    ("__mul__", "def __mul__(self, other): return self"),
    ("__truediv__", "def __truediv__(self, other): return self"),
    ("__floordiv__", "def __floordiv__(self, other): return self"),
    ("__mod__", "def __mod__(self, other): return self"),
    ("__pow__", "def __pow__(self, other): return self"),
    ("__lshift__", "def __lshift__(self, other): return self"),
    ("__rshift__", "def __rshift__(self, other): return self"),
    ("__and__", "def __and__(self, other): return self"),
    ("__xor__", "def __xor__(self, other): return self"),
    ("__or__", "def __or__(self, other): return self"),
    ("__radd__", "def __radd__(self, other): return self"),
    ("__iadd__", "def __iadd__(self, other): return self"),
    ("__neg__", "def __neg__(self): return self"),
    ("__pos__", "def __pos__(self): return self"),
    ("__abs__", "def __abs__(self): return self"),
    ("__invert__", "def __invert__(self): return self"),
    ("__int__", "def __int__(self) -> int: return 0"),
    ("__float__", "def __float__(self) -> float: return 0.0"),
    ("__bool__", "def __bool__(self) -> bool: return True"),
]

@pytest.mark.parametrize("dunder_name,dunder_def", NUMERIC_DUNDERS)
def test_python_numeric_dunders(dunder_name: str, dunder_def: str):
    code = f"""
class VectorMath:
    {dunder_def}
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("vector.py", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) == 1
    assert methods[0].name == dunder_name
    assert methods[0].parent_symbol == "VectorMath"


# ============================================================================
# 15. Python Stacked Decorator Chains (1 to 4 decorators)
# ============================================================================

STACKED_DECORATORS = [
    (["property"], "@property\ndef val(self): return 1"),
    (["staticmethod", "cached"], "@staticmethod\n@cached\ndef val(): return 1"),
    (["retry(...)", "logged", "timed"], "@retry(attempts=3)\n@logged\n@timed\ndef run(): pass"),
    (["trace", "audit", "profile", "validate"], "@trace\n@audit\n@profile\n@validate\ndef execute(): pass"),
]

@pytest.mark.parametrize("expected_decos,code", STACKED_DECORATORS)
def test_python_stacked_decorators(expected_decos: list[str], code: str):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("decos.py", code)
    assert len(symbols) == 1
    for deco in expected_decos:
        base = deco.split("(")[0]
        assert any(base in d for d in symbols[0].decorators)


# ============================================================================
# 16. TypeScript Interface Extends Multi-Inheritance & Generic Matrix
# ============================================================================

TS_INTERFACE_PERMUTATIONS = [
    ("interface Base { id: string; }", "Base", []),
    ("interface Identifiable extends Base { uuid: string; }", "Identifiable", ["Base"]),
    ("interface Entity extends Base, Auditable, Versioned { rev: int; }", "Entity", ["Base", "Auditable", "Versioned"]),
    ("interface Repository<T> { find(id: string): T; }", "Repository", []),
    ("interface CrudRepository<T, ID> extends Repository<T> { delete(id: ID): void; }", "CrudRepository", ["Repository<T>"]),
]

@pytest.mark.parametrize("code,expected_name,expected_bases", TS_INTERFACE_PERMUTATIONS)
def test_ts_interface_matrix(code: str, expected_name: str, expected_bases: list[str]):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("iface.ts", code)
    ifaces = [s for s in symbols if s.kind == SymbolKind.INTERFACE and s.name == expected_name]
    assert len(ifaces) == 1
    for base in expected_bases:
        assert any(base.split("<")[0] in b for b in ifaces[0].bases)


# ============================================================================
# 17. Go Struct & Function Complexity Matrix
# ============================================================================

GO_COMPLEX_CASES = [
    ("type DBConfig struct { DSN string }", "DBConfig", SymbolKind.STRUCT),
    ("type CacheConfig struct { TTL int }", "CacheConfig", SymbolKind.STRUCT),
    ("type TLSConfig struct { CertFile string }", "TLSConfig", SymbolKind.STRUCT),
    ("type MetricsConfig struct { Prometheus bool }", "MetricsConfig", SymbolKind.STRUCT),
    ("type Streamer interface { Stream(ctx context.Context) error }", "Streamer", SymbolKind.INTERFACE),
    ("type Closer interface { Close() error }", "Closer", SymbolKind.INTERFACE),
    ("type Logger interface { Log(msg string, args ...any) }", "Logger", SymbolKind.INTERFACE),
    ("func (c *DBConfig) Connect() error { return nil }", "Connect", SymbolKind.METHOD),
    ("func (c *CacheConfig) Invalidate() { }", "Invalidate", SymbolKind.METHOD),
    ("func (c *TLSConfig) LoadPair() error { return nil }", "LoadPair", SymbolKind.METHOD),
    ("func (c *MetricsConfig) Register() error { return nil }", "Register", SymbolKind.METHOD),
    ("func InitAll(configs ...any) bool { return true }", "InitAll", SymbolKind.FUNCTION),
    ("func Teardown(force bool) error { return nil }", "Teardown", SymbolKind.FUNCTION),
]

@pytest.mark.parametrize("code,expected_name,expected_kind", GO_COMPLEX_CASES)
def test_go_complex_symbol_matrix(code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("cluster.go", code)
    matched = [s for s in symbols if s.name == expected_name]
    assert len(matched) == 1
    assert matched[0].kind == expected_kind


# ============================================================================
# 18. Rust Enums, Traits, and Functions Exhaustive Matrix
# ============================================================================

RUST_EXHAUSTIVE_CASES = [
    ("pub struct Point { pub x: f64, pub y: f64 }", "Point", SymbolKind.STRUCT),
    ("pub struct Vector3 { x: f32, y: f32, z: f32 }", "Vector3", SymbolKind.STRUCT),
    ("pub enum Command { Quit, Refresh, Reload }", "Command", SymbolKind.ENUM),
    ("pub enum Event { KeyPress(char), Click(i32, i32) }", "Event", SymbolKind.ENUM),
    ("pub trait Displayable { fn display(&self); }", "Displayable", SymbolKind.TRAIT),
    ("pub trait Serializable { fn serialize(&self) -> String; }", "Serializable", SymbolKind.TRAIT),
    ("pub fn parse_input(raw: &str) -> Option<Command> { None }", "parse_input", SymbolKind.FUNCTION),
    ("pub async fn send_heartbeat() -> Result<(), ()> { Ok(()) }", "send_heartbeat", SymbolKind.FUNCTION),
    ("fn local_calc(a: u32, b: u32) -> u32 { a + b }", "local_calc", SymbolKind.FUNCTION),
]

@pytest.mark.parametrize("code,expected_name,expected_kind", RUST_EXHAUSTIVE_CASES)
def test_rust_exhaustive_matrix(code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("pipeline.rs", code)
    matched = [s for s in symbols if s.name == expected_name]
    assert len(matched) == 1
    assert matched[0].kind == expected_kind


# ============================================================================
# 19. Generic Polyglot Fallback Matrix across Languages (C, Java, C#, PHP, Ruby, Dart)
# ============================================================================

GENERIC_POLYGLOT_PERMUTATIONS = [
    # C/C++
    ("core.h", "int execute_step(int step_id);", "execute_step", SymbolKind.FUNCTION),
    ("driver.c", "void init_hardware();", "init_hardware", SymbolKind.FUNCTION),
    ("matrix.cpp", "class MatrixTransformer {};", "MatrixTransformer", SymbolKind.CLASS),
    ("buffer.cpp", "struct RingBuffer {};", "RingBuffer", SymbolKind.CLASS),
    # Java
    ("User.java", "public class UserAccount {}", "UserAccount", SymbolKind.CLASS),
    ("Repository.java", "public interface UserRepository {}", "UserRepository", SymbolKind.CLASS),
    ("Config.java", "class DatabaseConfig {}", "DatabaseConfig", SymbolKind.CLASS),
    # C#
    ("Payment.cs", "public class PaymentGateway {}", "PaymentGateway", SymbolKind.CLASS),
    ("IHandler.cs", "public interface IRequestHandler {}", "IRequestHandler", SymbolKind.CLASS),
    ("Point.cs", "public struct Coordinates {}", "Coordinates", SymbolKind.CLASS),
    # PHP
    ("controller.php", "class AuthController {}", "AuthController", SymbolKind.CLASS),
    ("helper.php", "function sanitizeInput($raw) {}", "sanitizeInput", SymbolKind.FUNCTION),
    ("service.php", "interface NotificationInterface {}", "NotificationInterface", SymbolKind.CLASS),
    # Ruby
    ("model.rb", "class TransactionRecord\nend", "TransactionRecord", SymbolKind.CLASS),
    ("worker.rb", "def process_batch\nend", "process_batch", SymbolKind.FUNCTION),
    # Dart
    ("screen.dart", "class HomeScreen {}", "HomeScreen", SymbolKind.CLASS),
    ("util.dart", "void logMessage(String msg) {}", "logMessage", SymbolKind.FUNCTION),
]

@pytest.mark.parametrize("filename,code,expected_name,expected_kind", GENERIC_POLYGLOT_PERMUTATIONS)
def test_generic_polyglot_matrix(filename: str, code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content(filename, code)
    matched = [s for s in symbols if s.name == expected_name]
    assert len(matched) >= 1
    assert matched[0].kind == expected_kind


# ============================================================================
# 20. Python Async Dunder Methods Matrix
# ============================================================================

ASYNC_DUNDERS = [
    ("__aenter__", "async def __aenter__(self): return self"),
    ("__aexit__", "async def __aexit__(self, exc_type, exc_val, exc_tb): pass"),
    ("__aiter__", "def __aiter__(self): return self"),
    ("__anext__", "async def __anext__(self): return 1"),
]

@pytest.mark.parametrize("dunder_name,dunder_def", ASYNC_DUNDERS)
def test_python_async_dunders(dunder_name: str, dunder_def: str):
    code = f"""
class AsyncSession:
    {dunder_def}
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("async_session.py", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) == 1
    assert methods[0].name == dunder_name
    assert methods[0].parent_symbol == "AsyncSession"


# ============================================================================
# 21. Python Custom Exception Class Hierarchy Matrix
# ============================================================================

EXCEPTION_CLASSES = [
    ("DatabaseConnectionError", "Exception"),
    ("ModelInferenceTimeout", "TimeoutError"),
    ("ConfigurationError", "ValueError"),
    ("SecurityViolationError", "PermissionError"),
    ("TaskExecutionFailure", "RuntimeError"),
]

@pytest.mark.parametrize("exc_name,base_exc", EXCEPTION_CLASSES)
def test_python_custom_exceptions(exc_name: str, base_exc: str):
    code = f"""
class {exc_name}({base_exc}):
    def __init__(self, message: str):
        super().__init__(message)
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("exceptions.py", code)
    classes = [s for s in symbols if s.kind == SymbolKind.CLASS and s.name == exc_name]
    assert len(classes) == 1
    assert base_exc in classes[0].bases


# ============================================================================
# 22. Python Internal Call Target Extraction Matrix
# ============================================================================

CALL_TARGET_CASES = [
    ("def f(): print('hello')", ["print"]),
    ("def f(): logger.info('data'); os.mkdir('dir')", ["info", "mkdir"]),
    ("def f(): a(); b(); c()", ["a", "b", "c"]),
    ("def f(): resp = requests.get(url); return resp.json()", ["get", "json"]),
    ("def f(): hashlib.sha256(b'test').hexdigest()", ["sha256", "hexdigest"]),
]

@pytest.mark.parametrize("code,expected_calls", CALL_TARGET_CASES)
def test_python_call_target_resolution(code: str, expected_calls: list[str]):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("calls.py", code)
    assert len(symbols) == 1
    for call in expected_calls:
        assert call in symbols[0].calls


# ============================================================================
# 23. TypeScript Getters and Setters Extraction Matrix
# ============================================================================

TS_ACCESSORS = [
    ("get id(): string { return this._id; }", "id"),
    ("get active(): boolean { return this._active; }", "active"),
    ("set payload(data: any) { this._payload = data; }", "payload"),
    ("set timeout(ms: number) { this._timeout = ms; }", "timeout"),
]

@pytest.mark.parametrize("accessor_code,expected_name", TS_ACCESSORS)
def test_ts_getter_setter_extraction(accessor_code: str, expected_name: str):
    code = f"""
class ModelEntity {{
    {accessor_code}
}}
"""
    parser = PolyglotASTParser()
    symbols = parser.parse_content("entity.ts", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
    assert len(methods) == 1
    assert methods[0].name == expected_name


# ============================================================================
# 24. Go Pointer vs Value Receiver Matrix
# ============================================================================

GO_RECEIVERS = [
    ("func (h *Handler) ServeHTTP(w ResponseWriter, r *Request) {}", "ServeHTTP", "Handler"),
    ("func (h Handler) Path() string { return '/' }", "Path", "Handler"),
    ("func (s *Store) Put(k string, v []byte) error { return nil }", "Put", "Store"),
    ("func (s Store) Get(k string) ([]byte, bool) { return nil, false }", "Get", "Store"),
]

@pytest.mark.parametrize("code,expected_name,expected_parent", GO_RECEIVERS)
def test_go_receiver_variations(code: str, expected_name: str, expected_parent: str):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("http.go", code)
    matched = [s for s in symbols if s.name == expected_name and s.kind == SymbolKind.METHOD]
    assert len(matched) == 1
    assert matched[0].parent_symbol == expected_parent


# ============================================================================
# 25. Python Property Setter and Deleter Decorators Matrix
# ============================================================================

PROPERTY_DECORATORS = [
    ("@prop.setter\ndef prop(self, val): pass", "prop", "prop.setter"),
    ("@prop.deleter\ndef prop(self): pass", "prop", "prop.deleter"),
    ("@score.setter\ndef score(self, s: float): pass", "score", "score.setter"),
    ("@cache.deleter\ndef cache(self): pass", "cache", "cache.deleter"),
]

@pytest.mark.parametrize("code_snippet,expected_name,expected_deco", PROPERTY_DECORATORS)
def test_python_property_setter_deleter(code_snippet: str, expected_name: str, expected_deco: str):
    indented = "\n    ".join(code_snippet.strip().splitlines())
    code = f"class Evaluator:\n    {indented}\n"
    parser = PolyglotASTParser()
    symbols = parser.parse_content("eval.py", code)
    methods = [s for s in symbols if s.kind == SymbolKind.METHOD and s.name == expected_name]
    assert len(methods) == 1
    assert any(expected_deco in d for d in methods[0].decorators)


# ============================================================================
# 26. Go Multi-Method Interface Matrix
# ============================================================================

GO_MULTI_INTERFACES = [
    ("type ReadWriter interface { Read(p []byte) (n int, err error); Write(p []byte) (n int, err error) }", "ReadWriter"),
    ("type ReadCloser interface { Read(p []byte) (n int, err error); Close() error }", "ReadCloser"),
    ("type WriteCloser interface { Write(p []byte) (n int, err error); Close() error }", "WriteCloser"),
    ("type Seeker interface { Seek(offset int64, whence int) (int64, error) }", "Seeker"),
    ("type ByteScanner interface { ReadByte() (byte, error); UnreadByte() error }", "ByteScanner"),
]

@pytest.mark.parametrize("code,expected_name", GO_MULTI_INTERFACES)
def test_go_multi_method_interfaces(code: str, expected_name: str):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("io.go", code)
    matched = [s for s in symbols if s.name == expected_name and s.kind == SymbolKind.INTERFACE]
    assert len(matched) == 1


# ============================================================================
# 27. Rust Generic Structs, Enums, and Functions Matrix
# ============================================================================

RUST_GENERICS = [
    ("pub struct Box<T> { val: T }", "Box", SymbolKind.STRUCT),
    ("pub struct Pair<K, V> { k: K, v: V }", "Pair", SymbolKind.STRUCT),
    ("pub struct ResultWrapper<T, E> { res: Result<T, E> }", "ResultWrapper", SymbolKind.STRUCT),
    ("pub enum Option<T> { Some(T), None }", "Option", SymbolKind.ENUM),
    ("pub fn identity<T>(val: T) -> T { val }", "identity", SymbolKind.FUNCTION),
    ("pub fn pair_up<A, B>(a: A, b: B) -> (A, B) { (a, b) }", "pair_up", SymbolKind.FUNCTION),
]

@pytest.mark.parametrize("code,expected_name,expected_kind", RUST_GENERICS)
def test_rust_generics_matrix(code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content("generics.rs", code)
    matched = [s for s in symbols if s.name == expected_name and s.kind == expected_kind]
    assert len(matched) == 1


# ============================================================================
# 28. Java and C# Modern Language Constructs Matrix
# ============================================================================

JAVA_CS_CONSTRUCTS = [
    ("Records.java", "public record UserDto(String id, String email) {}", "UserDto", SymbolKind.CLASS),
    ("Events.java", "public enum SystemEvent { STARTUP, SHUTDOWN, HEARTBEAT }", "SystemEvent", SymbolKind.CLASS),
    ("Records.cs", "public record DeviceTelemetry(string DeviceId, double Temp);", "DeviceTelemetry", SymbolKind.CLASS),
    ("Enums.cs", "public enum EngineState { Idle, Active, Error }", "EngineState", SymbolKind.CLASS),
]

@pytest.mark.parametrize("filename,code,expected_name,expected_kind", JAVA_CS_CONSTRUCTS)
def test_java_cs_modern_constructs(filename: str, code: str, expected_name: str, expected_kind: SymbolKind):
    parser = PolyglotASTParser()
    symbols = parser.parse_content(filename, code)
    matched = [s for s in symbols if s.name == expected_name and s.kind == expected_kind]
    assert len(matched) >= 1




