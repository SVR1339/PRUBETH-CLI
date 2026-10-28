"""PRUBETH Polyglot AST Symbol Parser & Syntax Extractor.

Extracts deep semantic AST symbols across Python, TypeScript, JavaScript, Go,
Rust, and other language ecosystems without external binary dependencies.
Enforces deterministic precision, zero font blur, and micro-footprint invariants.
"""

import ast
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple, Union


class SymbolKind(str, Enum):
    """Categorisation of parsed code symbols."""
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    TRAIT = "trait"
    TYPE_ALIAS = "type_alias"
    VARIABLE = "variable"
    IMPORT = "import"


@dataclass
class CodeSymbol:
    """Rich semantic representation of an AST code symbol."""
    name: str
    kind: SymbolKind
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    parent_symbol: Optional[str] = None
    calls: List[str] = field(default_factory=list)
    imports: List[Dict[str, Any]] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)
    body_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts symbol to JSON-serialisable dictionary."""
        return {
            "name": self.name,
            "kind": self.kind.value if isinstance(self.kind, SymbolKind) else str(self.kind),
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
            "docstring": self.docstring,
            "decorators": self.decorators,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "parent_symbol": self.parent_symbol,
            "calls": self.calls,
            "imports": self.imports,
            "bases": self.bases,
            "body_snippet": self.body_snippet,
        }


class PythonASTVisitor(ast.NodeVisitor):
    """Deep AST visitor for Python source files."""

    def __init__(self, rel_path: str, source_code: str):
        self.rel_path = rel_path
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.symbols: List[CodeSymbol] = []
        self.current_class: Optional[str] = None
        self.current_calls: List[str] = []
        self.current_imports: List[Dict[str, Any]] = []

    def _get_snippet(self, start_line: int, end_line: int) -> str:
        """Extracts source lines safely."""
        start_idx = max(0, start_line - 1)
        end_idx = min(len(self.source_lines), end_line)
        return "\n".join(self.source_lines[start_idx:end_idx])

    def _format_decorator(self, node: ast.AST) -> str:
        """Formats decorator AST node to string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._format_attribute(node)}"
        elif isinstance(node, ast.Call):
            func_name = self._format_decorator(node.func)
            return f"{func_name}(...)"
        return "decorator"

    def _format_attribute(self, node: ast.Attribute) -> str:
        """Recursively formats attribute access."""
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._format_attribute(node.value)}.{node.attr}"
        return node.attr

    def visit_Import(self, node: ast.Import) -> None:
        """Records explicit module imports."""
        for alias in node.names:
            imp_info = {
                "module": alias.name,
                "name": alias.asname or alias.name,
                "is_from": False,
                "line": node.lineno,
            }
            self.current_imports.append(imp_info)
            self.symbols.append(CodeSymbol(
                name=alias.asname or alias.name,
                kind=SymbolKind.IMPORT,
                file_path=self.rel_path,
                start_line=node.lineno,
                end_line=node.lineno,
                signature=f"import {alias.name}",
                imports=[imp_info],
            ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Records from-module imports."""
        module = node.module or ""
        for alias in node.names:
            imp_info = {
                "module": module,
                "name": alias.name,
                "alias": alias.asname,
                "is_from": True,
                "line": node.lineno,
            }
            self.current_imports.append(imp_info)
            self.symbols.append(CodeSymbol(
                name=alias.name,
                kind=SymbolKind.IMPORT,
                file_path=self.rel_path,
                start_line=node.lineno,
                end_line=node.lineno,
                signature=f"from {module} import {alias.name}",
                imports=[imp_info],
            ))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visits class definitions and extracts bases and methods."""
        prev_class = self.current_class
        self.current_class = node.name

        docstring = ast.get_docstring(node)
        decorators = [self._format_decorator(d) for d in node.decorator_list]

        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(self._format_attribute(b))

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        sig = f"class {node.name}" + (f"({', '.join(bases)})" if bases else "")

        symbol = CodeSymbol(
            name=node.name,
            kind=SymbolKind.CLASS,
            file_path=self.rel_path,
            start_line=start_line,
            end_line=end_line,
            signature=sig,
            docstring=docstring,
            decorators=decorators,
            parameters=[],
            return_type=None,
            parent_symbol=prev_class,
            calls=[],
            imports=[],
            bases=bases,
            body_snippet=self._get_snippet(start_line, min(start_line + 15, end_line)),
        )
        self.symbols.append(symbol)

        # Visit children (methods, nested classes)
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visits synchronous functions and methods."""
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visits asynchronous functions and methods."""
        self._handle_function(node, is_async=True)

    def _handle_function(self, node: Any, is_async: bool) -> None:
        """Extracts function/method details and local call targets."""
        docstring = ast.get_docstring(node)
        decorators = [self._format_decorator(d) for d in node.decorator_list]

        param_names = []
        sig_params = []

        def _param_sig(arg_node: ast.arg) -> str:
            if arg_node.annotation:
                try:
                    return f"{arg_node.arg}: {ast.unparse(arg_node.annotation)}"
                except Exception:
                    return arg_node.arg
            return arg_node.arg

        for a in getattr(node.args, "posonlyargs", []):
            param_names.append(a.arg)
            sig_params.append(_param_sig(a))
        for a in node.args.args:
            param_names.append(a.arg)
            sig_params.append(_param_sig(a))
        if node.args.vararg:
            param_names.append(f"*{node.args.vararg.arg}")
            sig_params.append(f"*{_param_sig(node.args.vararg)}")
        for a in node.args.kwonlyargs:
            param_names.append(a.arg)
            sig_params.append(_param_sig(a))
        if node.args.kwarg:
            param_names.append(f"**{node.args.kwarg.arg}")
            sig_params.append(f"**{_param_sig(node.args.kwarg)}")
        params = param_names

        ret_type = None
        if node.returns:
            try:
                ret_type = ast.unparse(node.returns)
            except Exception:
                if isinstance(node.returns, ast.Name):
                    ret_type = node.returns.id
                elif isinstance(node.returns, ast.Constant):
                    ret_type = str(node.returns.value)
                else:
                    ret_type = "object"

        kind = SymbolKind.METHOD if self.current_class else SymbolKind.FUNCTION
        prefix = "async def " if is_async else "def "
        sig = f"{prefix}{node.name}({', '.join(sig_params)})" + (f" -> {ret_type}" if ret_type else "")

        # Collect calls inside this function
        local_calls: List[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._resolve_call_name(child.func)
                if call_name and call_name not in local_calls:
                    local_calls.append(call_name)

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        symbol = CodeSymbol(
            name=node.name,
            kind=kind,
            file_path=self.rel_path,
            start_line=start_line,
            end_line=end_line,
            signature=sig,
            docstring=docstring,
            decorators=decorators,
            parameters=params,
            return_type=ret_type,
            parent_symbol=self.current_class,
            calls=local_calls,
            imports=[],
            bases=[],
            body_snippet=self._get_snippet(start_line, min(start_line + 20, end_line)),
        )
        self.symbols.append(symbol)

    def _resolve_call_name(self, node: ast.AST) -> Optional[str]:
        """Resolves target identifier or method name of a call expression."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None


class PolyglotASTParser:
    """Universal polyglot code parser producing structured AST symbols and relations."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()

    def parse_file(self, file_path: Union[Path, str]) -> List[CodeSymbol]:
        """Parses a single file and returns extracted symbols."""
        p = Path(file_path)
        if not p.is_file():
            return []

        try:
            rel_path = str(p.relative_to(self.workspace_root)).replace("\\", "/")
        except ValueError:
            rel_path = p.as_posix()
        ext = p.suffix.lower()

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        if ext == ".py":
            return self._parse_python(rel_path, content)
        elif ext in {".ts", ".tsx", ".js", ".jsx"}:
            return self._parse_javascript_typescript(rel_path, content)
        elif ext == ".go":
            return self._parse_go(rel_path, content)
        elif ext == ".rs":
            return self._parse_rust(rel_path, content)
        else:
            return self._parse_generic_fallback(rel_path, content)

    def parse_content(self, filename: str, content: str) -> List[CodeSymbol]:
        """Parses string content directly for given virtual filename."""
        rel_path = filename.replace("\\", "/")
        ext = Path(filename).suffix.lower()

        if ext == ".py":
            return self._parse_python(rel_path, content)
        elif ext in {".ts", ".tsx", ".js", ".jsx"}:
            return self._parse_javascript_typescript(rel_path, content)
        elif ext == ".go":
            return self._parse_go(rel_path, content)
        elif ext == ".rs":
            return self._parse_rust(rel_path, content)
        else:
            return self._parse_generic_fallback(rel_path, content)

    parse_source = parse_content

    def _parse_python(self, rel_path: str, content: str) -> List[CodeSymbol]:
        """Parses Python source code with full AST fidelity."""
        try:
            tree = ast.parse(content, filename=rel_path)
            visitor = PythonASTVisitor(rel_path, content)
            visitor.visit(tree)
            return visitor.symbols
        except Exception:
            # Fallback to regex scanner if syntax error in partial file
            return self._parse_generic_fallback(rel_path, content)

    def _parse_javascript_typescript(self, rel_path: str, content: str) -> List[CodeSymbol]:
        """Parses JavaScript and TypeScript source files."""
        symbols: List[CodeSymbol] = []
        lines = content.splitlines()

        # Extract imports
        import_pattern = re.compile(r"import\s+(?:\{([^}]+)\}|\*\s+as\s+(\w+)|(\w+))\s+from\s+['\"]([^'\"]+)['\"]")
        imports: List[Dict[str, Any]] = []
        for i, line in enumerate(lines):
            m = import_pattern.search(line)
            if m:
                specifiers = m.group(1) or m.group(2) or m.group(3)
                module = m.group(4)
                imports.append({"module": module, "specifiers": specifiers, "line": i + 1})

        # Extract classes and interfaces
        class_pattern = re.compile(r"(?:export\s+)?(?:default\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w<>]+))?(?:\s+implements\s+([\w\s,<>]+))?")
        interface_pattern = re.compile(r"(?:export\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w\s,<>]+))?")
        type_alias_pattern = re.compile(r"(?:export\s+)?type\s+(\w+)(?:<[^>]+>)?\s*=")

        # Extract functions and arrow functions
        func_pattern = re.compile(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^\{]+))?")
        arrow_pattern = re.compile(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)(?:\s*:\s*([^=]+))?\s*=>")
        method_pattern = re.compile(r"^\s*(?:(?:public|private|protected|async|static|\*)\s+)*(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{")
        accessor_pattern = re.compile(r"^\s*(?:(?:public|private|protected|static)\s+)?(?:get|set)\s+(\w+)\s*(?:\(([^)]*)\))?(?:\s*:\s*([^{]+))?\s*\{")

        current_class: Optional[str] = None
        class_brace_depth = 0

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            if current_class:
                class_brace_depth += line.count("{") - line.count("}")
                if class_brace_depth <= 0:
                    current_class = None

            # Class definition
            cm = class_pattern.search(line)
            if cm:
                c_name = cm.group(1)
                base = cm.group(2)
                bases = [base] if base else []
                current_class = c_name
                class_brace_depth = line.count("{") - line.count("}")

                symbols.append(CodeSymbol(
                    name=c_name,
                    kind=SymbolKind.CLASS,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 30,  # approximate until closed
                    signature=stripped.split("{")[0].strip(),
                    docstring=None,
                    bases=bases,
                    calls=[],
                    imports=imports,
                    body_snippet=line,
                ))
                continue

            # Interface definition
            im = interface_pattern.search(line)
            if im:
                i_name = im.group(1)
                ext_base = im.group(2)
                bases = [b.strip() for b in ext_base.split(",")] if ext_base else []
                symbols.append(CodeSymbol(
                    name=i_name,
                    kind=SymbolKind.INTERFACE,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 15,
                    signature=stripped.split("{")[0].strip(),
                    bases=bases,
                    body_snippet=line,
                ))
                continue

            # Type alias definition
            tm = type_alias_pattern.search(line)
            if tm:
                t_name = tm.group(1)
                symbols.append(CodeSymbol(
                    name=t_name,
                    kind=SymbolKind.TYPE_ALIAS,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num,
                    signature=stripped,
                    body_snippet=line,
                ))
                continue

            # Function definition
            fm = func_pattern.search(line)
            if fm:
                f_name = fm.group(1)
                params = [p.strip() for p in fm.group(2).split(",") if p.strip()]
                ret_type = fm.group(3).strip() if fm.group(3) else None
                symbols.append(CodeSymbol(
                    name=f_name,
                    kind=SymbolKind.FUNCTION,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 20,
                    signature=stripped.split("{")[0].strip(),
                    parameters=params,
                    return_type=ret_type,
                    calls=self._extract_call_names(content, line_num),
                    body_snippet=line,
                ))
                continue

            # Arrow function
            am = arrow_pattern.search(line)
            if am:
                a_name = am.group(1)
                params = [p.strip() for p in am.group(2).split(",") if p.strip()]
                ret_type = am.group(3).strip() if am.group(3) else None
                symbols.append(CodeSymbol(
                    name=a_name,
                    kind=SymbolKind.FUNCTION,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 15,
                    signature=stripped.split("=>")[0].strip() + " =>",
                    parameters=params,
                    return_type=ret_type,
                    calls=self._extract_call_names(content, line_num),
                    body_snippet=line,
                ))
                continue

            # Method inside class
            if current_class and method_pattern.search(line) and not fm and not cm:
                mm = method_pattern.search(line)
                m_name = mm.group(1)
                if m_name not in {"if", "for", "while", "switch", "catch"}:
                    params = [p.strip() for p in mm.group(2).split(",") if p.strip()]
                    ret_type = mm.group(3).strip() if mm.group(3) else None
                    symbols.append(CodeSymbol(
                        name=m_name,
                        kind=SymbolKind.METHOD,
                        file_path=rel_path,
                        start_line=line_num,
                        end_line=line_num + 15,
                        signature=stripped.split("{")[0].strip(),
                        parameters=params,
                        return_type=ret_type,
                        parent_symbol=current_class,
                        calls=self._extract_call_names(content, line_num),
                        body_snippet=line,
                    ))
                continue

            # Getter / Setter inside class
            if current_class and accessor_pattern.search(line) and not fm and not cm:
                acc_m = accessor_pattern.search(line)
                acc_name = acc_m.group(1)
                p_str = acc_m.group(2)
                params = [p.strip() for p in p_str.split(",") if p_str and p.strip()]
                ret_type = acc_m.group(3).strip() if acc_m.group(3) else None
                symbols.append(CodeSymbol(
                    name=acc_name,
                    kind=SymbolKind.METHOD,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 15,
                    signature=stripped.split("{")[0].strip(),
                    parameters=params,
                    return_type=ret_type,
                    parent_symbol=current_class,
                    calls=self._extract_call_names(content, line_num),
                    body_snippet=line,
                ))

        return symbols

    def _parse_go(self, rel_path: str, content: str) -> List[CodeSymbol]:
        """Parses Go source files."""
        symbols: List[CodeSymbol] = []
        lines = content.splitlines()

        # Struct/Interface: type Name struct / type Name interface
        type_pattern = re.compile(r"^type\s+(\w+)\s+(struct|interface)")
        # Function: func Name(...) ...
        func_pattern = re.compile(r"^func\s+(\w+)\s*\(([^)]*)\)\s*([^{]*)")
        # Method: func (r *Receiver) Name(...) ...
        method_pattern = re.compile(r"^func\s*\(([^)]+)\)\s*(\w+)\s*\(([^)]*)\)\s*([^{]*)")

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            tm = type_pattern.match(stripped)
            if tm:
                name, kind_str = tm.group(1), tm.group(2)
                kind = SymbolKind.STRUCT if kind_str == "struct" else SymbolKind.INTERFACE
                symbols.append(CodeSymbol(
                    name=name,
                    kind=kind,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 20,
                    signature=stripped.split("{")[0].strip(),
                    body_snippet=line,
                ))
                continue

            mm = method_pattern.match(stripped)
            if mm:
                receiver, name, params_str, ret_str = mm.group(1), mm.group(2), mm.group(3), mm.group(4)
                rec_type = receiver.split()[-1].replace("*", "")
                params = [p.strip() for p in params_str.split(",") if p.strip()]
                symbols.append(CodeSymbol(
                    name=name,
                    kind=SymbolKind.METHOD,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 20,
                    signature=stripped.split("{")[0].strip(),
                    parameters=params,
                    return_type=ret_str.strip() or None,
                    parent_symbol=rec_type,
                    calls=self._extract_call_names(content, line_num),
                    body_snippet=line,
                ))
                continue

            fm = func_pattern.match(stripped)
            if fm:
                name, params_str, ret_str = fm.group(1), fm.group(2), fm.group(3)
                params = [p.strip() for p in params_str.split(",") if p.strip()]
                symbols.append(CodeSymbol(
                    name=name,
                    kind=SymbolKind.FUNCTION,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 20,
                    signature=stripped.split("{")[0].strip(),
                    parameters=params,
                    return_type=ret_str.strip() or None,
                    calls=self._extract_call_names(content, line_num),
                    body_snippet=line,
                ))

        return symbols

    def _parse_rust(self, rel_path: str, content: str) -> List[CodeSymbol]:
        """Parses Rust source files."""
        symbols: List[CodeSymbol] = []
        lines = content.splitlines()

        # Struct/Enum/Trait
        type_pattern = re.compile(r"^(?:pub\s+)?(struct|enum|trait)\s+(\w+)")
        # Impl block
        impl_pattern = re.compile(r"^impl(?:\s+([\w:]+)\s+for)?\s+(\w+)")
        # Function: fn name(...) -> ...
        func_pattern = re.compile(r"^(?:pub(?:\([^)]+\))?\s+)?(?:async\s+)?fn\s+(\w+)(?:<[^>]+>)?\s*\(([^)]*)\)(?:\s*->\s*([^{]+))?")

        current_impl: Optional[str] = None
        impl_brace_depth = 0

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            if current_impl:
                impl_brace_depth += line.count("{") - line.count("}")
                if impl_brace_depth <= 0:
                    current_impl = None

            tm = type_pattern.match(stripped)
            if tm:
                kind_str, name = tm.group(1), tm.group(2)
                kind = SymbolKind.STRUCT if kind_str == "struct" else (SymbolKind.ENUM if kind_str == "enum" else SymbolKind.TRAIT)
                symbols.append(CodeSymbol(
                    name=name,
                    kind=kind,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 20,
                    signature=stripped.split("{")[0].strip(),
                    body_snippet=line,
                ))
                continue

            im = impl_pattern.match(stripped)
            if im:
                trait_name, struct_name = im.group(1), im.group(2)
                current_impl = struct_name
                impl_brace_depth = line.count("{") - line.count("}")
                continue

            fm = func_pattern.match(stripped)
            if fm:
                name, params_str, ret_str = fm.group(1), fm.group(2), fm.group(3)
                params = [p.strip() for p in params_str.split(",") if p.strip()]
                kind = SymbolKind.METHOD if current_impl else SymbolKind.FUNCTION
                symbols.append(CodeSymbol(
                    name=name,
                    kind=kind,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 20,
                    signature=stripped.split("{")[0].strip(),
                    parameters=params,
                    return_type=ret_str.strip() if ret_str else None,
                    parent_symbol=current_impl,
                    calls=self._extract_call_names(content, line_num),
                    body_snippet=line,
                ))

        return symbols

    def _parse_generic_fallback(self, rel_path: str, content: str) -> List[CodeSymbol]:
        """Regex-based fallback symbol extractor for any language."""
        symbols: List[CodeSymbol] = []
        lines = content.splitlines()

        class_regex = re.compile(r"(?:class|interface|struct|record|enum)\s+([A-Za-z_][A-Za-z0-9_]*)")
        func_regex = re.compile(r"(?:def|function|fn|func|sub|void|int|bool|char|float|double|auto)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|$)")

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            cm = class_regex.search(stripped)
            if cm:
                symbols.append(CodeSymbol(
                    name=cm.group(1),
                    kind=SymbolKind.CLASS,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 20,
                    signature=stripped[:80],
                    body_snippet=line,
                ))
                continue

            fm = func_regex.search(stripped)
            if fm:
                symbols.append(CodeSymbol(
                    name=fm.group(1),
                    kind=SymbolKind.FUNCTION,
                    file_path=rel_path,
                    start_line=line_num,
                    end_line=line_num + 20,
                    signature=stripped[:80],
                    calls=self._extract_call_names(content, line_num),
                    body_snippet=line,
                ))

        return symbols

    def _extract_call_names(self, content: str, line_num: int, window: int = 25) -> List[str]:
        """Extracts invoked function/method names within a small scope window."""
        lines = content.splitlines()
        start = line_num - 1
        end = min(len(lines), start + window)
        block = "\n".join(lines[start:end])

        # Match function calls like foo(...) or obj.foo(...)
        matches = re.findall(r"(?:[a-zA-Z_]\w*\.)?([a-zA-Z_]\w*)\s*\(", block)
        reserved = {"if", "for", "while", "switch", "catch", "return", "sizeof", "print"}
        seen: List[str] = []
        for m in matches:
            if m not in reserved and m not in seen and len(m) > 1:
                seen.append(m)
        return seen[:20]
