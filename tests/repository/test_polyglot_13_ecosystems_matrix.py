"""Comprehensive tests across all 13 supported programming language ecosystems."""

import pytest
from pathlib import Path
from prubeth.repository.ast_parser import PolyglotASTParser, SymbolKind


@pytest.fixture
def parser(tmp_path):
    return PolyglotASTParser(workspace_root=tmp_path)


# =========================================================================
# 13 Language Ecosystem Syntax Matrix
# =========================================================================

ECOSYSTEM_FIXTURES = [
    # 1. Python
    (
        "python",
        "service.py",
        '''
class PythonService:
    def execute(self, payload: dict) -> bool:
        return True
''',
        "PythonService",
        SymbolKind.CLASS,
    ),
    # 2. TypeScript
    (
        "typescript",
        "service.ts",
        '''
export class TypeScriptService {
    public execute(payload: any): boolean {
        return true;
    }
}
''',
        "TypeScriptService",
        SymbolKind.CLASS,
    ),
    # 3. JavaScript
    (
        "javascript",
        "service.js",
        '''
function executeJavaScript(payload) {
    return true;
}
''',
        "executeJavaScript",
        SymbolKind.FUNCTION,
    ),
    # 4. Go
    (
        "go",
        "service.go",
        '''
package service
type GoService struct {
    Port int
}
func (s *GoService) Start() error {
    return nil
}
''',
        "GoService",
        SymbolKind.STRUCT,
    ),
    # 5. Rust
    (
        "rust",
        "service.rs",
        '''
pub struct RustService {
    pub workers: usize,
}
impl RustService {
    pub fn start(&self) -> bool {
        true
    }
}
''',
        "RustService",
        SymbolKind.STRUCT,
    ),
    # 6. Java
    (
        "java",
        "Service.java",
        '''
public class JavaService {
    public void executeTask() {
    }
}
''',
        "JavaService",
        SymbolKind.CLASS,
    ),
    # 7. C
    (
        "c",
        "service.c",
        '''
struct CContext {
    int id;
};

void init_service(int id) {
}
''',
        "CContext",
        SymbolKind.CLASS,
    ),
    # 8. C++
    (
        "cpp",
        "service.cpp",
        '''
class CppEngine {
public:
    void run();
};

void run_engine() {
}
''',
        "CppEngine",
        SymbolKind.CLASS,
    ),
    # 9. C#
    (
        "csharp",
        "Service.cs",
        '''
public class CSharpHandler {
    public void Handle() {
    }
}
''',
        "CSharpHandler",
        SymbolKind.CLASS,
    ),
    # 10. Ruby
    (
        "ruby",
        "service.rb",
        '''
class RubyService
  def process_request
    true
  end
end
''',
        "RubyService",
        SymbolKind.CLASS,
    ),
    # 11. PHP
    (
        "php",
        "service.php",
        '''
<?php
class PhpController {
    public function handle() {
        return true;
    }
}
''',
        "PhpController",
        SymbolKind.CLASS,
    ),
    # 12. Swift
    (
        "swift",
        "Service.swift",
        '''
class SwiftManager {
    func execute() -> Bool {
        return true
    }
}
''',
        "SwiftManager",
        SymbolKind.CLASS,
    ),
    # 13. Kotlin
    (
        "kotlin",
        "Service.kt",
        '''
class KotlinWorker {
    fun executeJob(): Boolean {
        return true
    }
}
''',
        "KotlinWorker",
        SymbolKind.CLASS,
    ),
]

@pytest.mark.parametrize("lang,filename,code,expected_symbol,expected_kind", ECOSYSTEM_FIXTURES)
def test_13_ecosystem_baseline_parsing(parser, tmp_path, lang, filename, code, expected_symbol, expected_kind):
    p = tmp_path / filename
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    names = [s.name for s in symbols]
    assert expected_symbol in names
    sym = next(s for s in symbols if s.name == expected_symbol)
    assert sym.kind == expected_kind


# =========================================================================
# Parametrized Polyglot File Permutations (13 languages x 15 variants)
# =========================================================================

def _make_code(lang: str, ext: str, i: int) -> str:
    if ext == "py":
        return f"class Class_py_{i}:\n    pass\n"
    elif ext == "go":
        return f"package main\ntype Class_go_{i} struct {{\n}}\n"
    elif ext == "rs":
        return f"pub struct Class_rs_{i} {{\n}}\n"
    else:
        return f"class Class_{lang}_{i} {{\n}}\n"


def _make_kind(ext: str) -> SymbolKind:
    if ext in {"go", "rs"}:
        return SymbolKind.STRUCT
    return SymbolKind.CLASS


POLYGLOT_PERMUTATIONS = [
    (
        f"service_{lang}_{i}.{ext}",
        _make_code(lang, ext, i),
        f"Class_{lang}_{i}",
        _make_kind(ext)
    )
    for lang, ext in [
        ("py", "py"), ("ts", "ts"), ("js", "js"), ("go", "go"),
        ("rs", "rs"), ("java", "java"), ("cpp", "cpp"), ("cs", "cs"),
        ("rb", "rb"), ("php", "php"), ("swift", "swift"), ("kt", "kt")
    ]
    for i in range(15)
]

@pytest.mark.parametrize("filename,code,expected_symbol,expected_kind", POLYGLOT_PERMUTATIONS)
def test_polyglot_language_matrix_scale(parser, tmp_path, filename, code, expected_symbol, expected_kind):
    p = tmp_path / filename
    p.write_text(code, encoding="utf-8")
    symbols = parser.parse_file(p)
    assert any(s.name == expected_symbol for s in symbols)
