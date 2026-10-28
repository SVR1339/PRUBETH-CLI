"""PRUBETH Spec-Driven Development (SDD) & Pre-Flight AST Contract Invariant Gate.

Validates proposed code mutations against project architectural invariants,
detects breaking signature changes (removed functions, altered parameters,
modified return types), and determines impact across the project call graph
before files are written to disk.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple

from prubeth.repository.graph import CodeGraph


class BreakingChangeSeverity(str, Enum):
    ERROR = "ERROR"        # Will break callers definitively
    WARNING = "WARNING"    # May break callers under certain conditions
    INFO = "INFO"          # Non-breaking architectural alteration


@dataclass
class ParameterSignature:
    name: str
    kind: str             # POSITIONAL_ONLY, POSITIONAL_OR_KEYWORD, VAR_POSITIONAL, KEYWORD_ONLY, VAR_KEYWORD
    has_default: bool = False
    default_repr: Optional[str] = None
    type_annotation: Optional[str] = None


@dataclass
class FunctionContract:
    name: str
    qualname: str
    is_async: bool
    parameters: List[ParameterSignature]
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    line_number: int = 1


@dataclass
class ClassContract:
    name: str
    bases: List[str]
    methods: Dict[str, FunctionContract] = field(default_factory=dict)
    docstring: Optional[str] = None
    line_number: int = 1


@dataclass
class BreakingChange:
    symbol_name: str
    severity: BreakingChangeSeverity
    message: str
    old_signature: Optional[str] = None
    new_signature: Optional[str] = None
    callers_affected: List[str] = field(default_factory=list)


@dataclass
class ContractVerificationResult:
    valid: bool
    file_path: str
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)
    affected_callers: List[str] = field(default_factory=list)
    remediation_advice: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(b.severity == BreakingChangeSeverity.ERROR for b in self.breaking_changes)

    @property
    def has_warnings(self) -> bool:
        return any(b.severity == BreakingChangeSeverity.WARNING for b in self.breaking_changes)


class PythonContractExtractor(ast.NodeVisitor):
    """Extracts typed interface contracts from Python AST."""

    def __init__(self):
        self.functions: Dict[str, FunctionContract] = {}
        self.classes: Dict[str, ClassContract] = {}
        self._class_stack: List[str] = []

    def _unparse(self, node: Optional[ast.AST]) -> Optional[str]:
        if node is None:
            return None
        try:
            return ast.unparse(node)
        except Exception:
            return None

    def _parse_arguments(self, args_node: ast.arguments) -> List[ParameterSignature]:
        params: List[ParameterSignature] = []

        # Positional only args (Python 3.8+)
        posonly = getattr(args_node, "posonlyargs", [])
        num_posonly_defaults = len(args_node.defaults) - (len(args_node.args) + len(posonly) - len(args_node.defaults))
        # Standard defaults align with the right-hand side of posonly + args
        all_pos = posonly + args_node.args
        defaults_offset = len(all_pos) - len(args_node.defaults)

        for i, arg in enumerate(posonly):
            has_def = i >= defaults_offset
            def_str = self._unparse(args_node.defaults[i - defaults_offset]) if has_def else None
            ann_str = self._unparse(arg.annotation)
            params.append(ParameterSignature(
                name=arg.arg,
                kind="POSITIONAL_ONLY",
                has_default=has_def,
                default_repr=def_str,
                type_annotation=ann_str,
            ))

        for i, arg in enumerate(args_node.args):
            total_idx = len(posonly) + i
            has_def = total_idx >= defaults_offset
            def_str = self._unparse(args_node.defaults[total_idx - defaults_offset]) if has_def else None
            ann_str = self._unparse(arg.annotation)
            params.append(ParameterSignature(
                name=arg.arg,
                kind="POSITIONAL_OR_KEYWORD",
                has_default=has_def,
                default_repr=def_str,
                type_annotation=ann_str,
            ))

        if args_node.vararg:
            ann_str = self._unparse(args_node.vararg.annotation)
            params.append(ParameterSignature(
                name=args_node.vararg.arg,
                kind="VAR_POSITIONAL",
                has_default=False,
                type_annotation=ann_str,
            ))

        # Keyword-only args
        for i, arg in enumerate(args_node.kwonlyargs):
            default_node = args_node.kw_defaults[i]
            has_def = default_node is not None
            def_str = self._unparse(default_node) if has_def else None
            ann_str = self._unparse(arg.annotation)
            params.append(ParameterSignature(
                name=arg.arg,
                kind="KEYWORD_ONLY",
                has_default=has_def,
                default_repr=def_str,
                type_annotation=ann_str,
            ))

        if args_node.kwarg:
            ann_str = self._unparse(args_node.kwarg.annotation)
            params.append(ParameterSignature(
                name=args_node.kwarg.arg,
                kind="VAR_KEYWORD",
                has_default=False,
                type_annotation=ann_str,
            ))

        return params

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = [self._unparse(b) or "" for b in node.bases]
        docstring = ast.get_docstring(node)
        class_contract = ClassContract(
            name=node.name,
            bases=bases,
            docstring=docstring,
            line_number=node.lineno
        )
        self.classes[node.name] = class_contract
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_func(node, is_async=True)

    def _process_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        params = self._parse_arguments(node.args)
        ret_type = self._unparse(node.returns)
        docstring = ast.get_docstring(node)
        decorators = [self._unparse(d) or "" for d in node.decorator_list]

        if self._class_stack:
            class_name = self._class_stack[-1]
            qualname = f"{class_name}.{node.name}"
            contract = FunctionContract(
                name=node.name,
                qualname=qualname,
                is_async=is_async,
                parameters=params,
                return_type=ret_type,
                docstring=docstring,
                decorators=decorators,
                line_number=node.lineno,
            )
            if class_name in self.classes:
                self.classes[class_name].methods[node.name] = contract
        else:
            qualname = node.name
            contract = FunctionContract(
                name=node.name,
                qualname=qualname,
                is_async=is_async,
                parameters=params,
                return_type=ret_type,
                docstring=docstring,
                decorators=decorators,
                line_number=node.lineno,
            )
            self.functions[node.name] = contract


class ASTContractGate:
    """Pre-flight contract verification engine before files are modified."""

    def __init__(
        self,
        code_graph: Optional[CodeGraph] = None,
        graph: Optional[CodeGraph] = None,
        strict_mode: bool = True
    ):
        self.code_graph = code_graph or graph
        self.strict_mode = strict_mode

    def verify_proposed_change(
        self,
        file_path: str,
        new_content: str,
        old_content: str = "",
        force: bool = False
    ) -> ContractVerificationResult:
        """Alias for verify_change with flexible parameter order."""
        return self.verify_change(file_path, old_content, new_content, force=force)

    def verify_change(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        force: bool = False
    ) -> ContractVerificationResult:
        """Verifies if applying new_content over old_content introduces breaking contract changes."""
        ext = Path(file_path).suffix.lower()

        # Non-Python files or files without previous content
        if not old_content.strip():
            return ContractVerificationResult(valid=True, file_path=file_path)

        if ext != ".py":
            polyglot_exts = {".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".cs", ".rb", ".php", ".swift", ".kt"}
            if ext in polyglot_exts:
                return self._verify_polyglot_contracts(file_path, old_content, new_content, force=force)
            # General fallback: check basic syntax balance
            return self._verify_polyglot_balance(file_path, old_content, new_content)

        return self._verify_python_contracts(file_path, old_content, new_content, force=force)

    def _verify_polyglot_contracts(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        force: bool = False
    ) -> ContractVerificationResult:
        """Verifies architectural contracts for non-Python supported languages."""
        balance_res = self._verify_polyglot_balance(file_path, old_content, new_content)
        if not balance_res.valid:
            return balance_res

        from prubeth.repository.ast_parser import PolyglotASTParser, SymbolKind
        parser = PolyglotASTParser()
        try:
            old_symbols = {s.name: s for s in parser.parse_content(file_path, old_content)}
            new_symbols = {s.name: s for s in parser.parse_content(file_path, new_content)}
        except Exception:
            return balance_res

        breaking_changes: List[BreakingChange] = []
        affected_callers_all: Set[str] = set()
        remediations: List[str] = []

        # Check for removed or renamed symbols (functions, classes, interfaces, structs, traits)
        for name, old_sym in old_symbols.items():
            if name.startswith("_"):
                continue

            if name not in new_symbols:
                callers = self._get_callers(name)
                affected_callers_all.update(callers)
                sev = BreakingChangeSeverity.ERROR if callers else BreakingChangeSeverity.WARNING
                breaking_changes.append(BreakingChange(
                    symbol_name=name,
                    severity=sev,
                    message=f"Public {old_sym.kind.value if hasattr(old_sym.kind, 'value') else old_sym.kind} '{name}' was removed or renamed.",
                    old_signature=old_sym.signature,
                    callers_affected=callers
                ))
                remediations.append(f"Retain '{name}' or update callers: {callers}")
            else:
                new_sym = new_symbols[name]
                # Compare parameter count if both have parameters
                if old_sym.parameters is not None and new_sym.parameters is not None:
                    if len(new_sym.parameters) > len(old_sym.parameters):
                        added_params = new_sym.parameters[len(old_sym.parameters):]
                        mandatory_added = [p for p in added_params if "=" not in p and "?" not in p]
                        if mandatory_added:
                            callers = self._get_callers(name)
                            affected_callers_all.update(callers)
                            breaking_changes.append(BreakingChange(
                                symbol_name=name,
                                severity=BreakingChangeSeverity.ERROR if callers else BreakingChangeSeverity.WARNING,
                                message=f"Added mandatory parameter(s) {mandatory_added} to '{name}' without default values.",
                                old_signature=old_sym.signature,
                                new_signature=new_sym.signature,
                                callers_affected=callers
                            ))
                            remediations.append(f"Add default value or optional marker for new parameter(s) {mandatory_added} in '{name}'.")

        has_blocking_errors = any(b.severity == BreakingChangeSeverity.ERROR for b in breaking_changes)
        is_valid = True if force else not has_blocking_errors

        return ContractVerificationResult(
            valid=is_valid,
            file_path=file_path,
            breaking_changes=breaking_changes,
            diagnostics=[b.message for b in breaking_changes],
            affected_callers=sorted(list(affected_callers_all)),
            remediation_advice=remediations,
        )

    def _verify_polyglot_balance(
        self,
        file_path: str,
        old_content: str,
        new_content: str
    ) -> ContractVerificationResult:
        """Basic balance check for braces, brackets, and parentheses in polyglot files."""
        pairs = {"{": "}", "[": "]", "(": ")"}
        stack: List[Tuple[str, int]] = []
        in_string: Optional[str] = None
        escaped = False

        for idx, char in enumerate(new_content):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == in_string:
                    in_string = None
                continue

            if char in ('"', "'", "`"):
                in_string = char
                continue

            if char in pairs:
                stack.append((char, idx))
            elif char in pairs.values():
                if not stack:
                    return ContractVerificationResult(
                        valid=False,
                        file_path=file_path,
                        breaking_changes=[BreakingChange(
                            symbol_name="syntax",
                            severity=BreakingChangeSeverity.ERROR,
                            message=f"Unmatched closing delimiter '{char}' at character index {idx}."
                        )]
                    )
                top, _ = stack.pop()
                if pairs[top] != char:
                    return ContractVerificationResult(
                        valid=False,
                        file_path=file_path,
                        breaking_changes=[BreakingChange(
                            symbol_name="syntax",
                            severity=BreakingChangeSeverity.ERROR,
                            message=f"Mismatched delimiter: expected '{pairs[top]}' but found '{char}' at index {idx}."
                        )]
                    )

        if stack:
            top, pos = stack[-1]
            return ContractVerificationResult(
                valid=False,
                file_path=file_path,
                breaking_changes=[BreakingChange(
                    symbol_name="syntax",
                    severity=BreakingChangeSeverity.ERROR,
                    message=f"Unclosed delimiter '{top}' opened at index {pos}."
                )]
            )

        return ContractVerificationResult(valid=True, file_path=file_path)

    def _verify_python_contracts(
        self,
        file_path: str,
        old_code: str,
        new_code: str,
        force: bool = False
    ) -> ContractVerificationResult:
        # 1. Parse both old and new ASTs
        try:
            old_ast = ast.parse(old_code, filename=file_path)
        except SyntaxError as e:
            # If old code already had syntax error, allow fix
            return ContractVerificationResult(
                valid=True,
                file_path=file_path,
                diagnostics=[f"Old code had pre-existing syntax error: {e}"]
            )

        try:
            new_ast = ast.parse(new_code, filename=file_path)
        except SyntaxError as e:
            return ContractVerificationResult(
                valid=False,
                file_path=file_path,
                breaking_changes=[BreakingChange(
                    symbol_name="syntax",
                    severity=BreakingChangeSeverity.ERROR,
                    message=f"New code contains Python syntax error at line {e.lineno}, col {e.offset}: {e.msg}"
                )],
                diagnostics=[f"SyntaxError: {e}"]
            )

        # 2. Extract contracts
        old_extractor = PythonContractExtractor()
        old_extractor.visit(old_ast)

        new_extractor = PythonContractExtractor()
        new_extractor.visit(new_ast)

        breaking_changes: List[BreakingChange] = []
        affected_callers_all: Set[str] = set()
        remediations: List[str] = []

        # 3. Check for removed or renamed top-level functions
        for name, old_fn in old_extractor.functions.items():
            if name.startswith("_"):
                # Private function; less severe
                continue

            if name not in new_extractor.functions:
                callers = self._get_callers(name)
                affected_callers_all.update(callers)
                sev = BreakingChangeSeverity.ERROR if callers else BreakingChangeSeverity.WARNING
                breaking_changes.append(BreakingChange(
                    symbol_name=name,
                    severity=sev,
                    message=f"Public function '{name}' was removed or renamed.",
                    old_signature=self._format_sig(old_fn),
                    callers_affected=callers
                ))
                remediations.append(f"Retain '{name}' as a deprecated alias or update affected callers: {callers}")
            else:
                new_fn = new_extractor.functions[name]
                changes = self._compare_function_signatures(old_fn, new_fn)
                breaking_changes.extend(changes)

        # 4. Check for removed or altered classes
        for cls_name, old_cls in old_extractor.classes.items():
            if cls_name.startswith("_"):
                continue

            if cls_name not in new_extractor.classes:
                callers = self._get_callers(cls_name)
                affected_callers_all.update(callers)
                sev = BreakingChangeSeverity.ERROR if callers else BreakingChangeSeverity.WARNING
                breaking_changes.append(BreakingChange(
                    symbol_name=cls_name,
                    severity=sev,
                    message=f"Public class '{cls_name}' was removed or renamed.",
                    callers_affected=callers
                ))
            else:
                new_cls = new_extractor.classes[cls_name]
                # Compare class methods
                for m_name, old_m in old_cls.methods.items():
                    if m_name.startswith("_") and m_name != "__init__":
                        continue
                    if m_name not in new_cls.methods:
                        qual = f"{cls_name}.{m_name}"
                        callers = self._get_callers(m_name)
                        affected_callers_all.update(callers)
                        breaking_changes.append(BreakingChange(
                            symbol_name=qual,
                            severity=BreakingChangeSeverity.ERROR if callers else BreakingChangeSeverity.WARNING,
                            message=f"Public method '{qual}' was removed or renamed.",
                            old_signature=self._format_sig(old_m),
                            callers_affected=callers
                        ))
                    else:
                        new_m = new_cls.methods[m_name]
                        changes = self._compare_function_signatures(old_m, new_m)
                        breaking_changes.extend(changes)

        has_blocking_errors = any(b.severity == BreakingChangeSeverity.ERROR for b in breaking_changes)
        is_valid = True if force else not has_blocking_errors

        return ContractVerificationResult(
            valid=is_valid,
            file_path=file_path,
            breaking_changes=breaking_changes,
            diagnostics=[b.message for b in breaking_changes],
            affected_callers=sorted(list(affected_callers_all)),
            remediation_advice=remediations,
        )

    def _compare_function_signatures(
        self,
        old_fn: FunctionContract,
        new_fn: FunctionContract
    ) -> List[BreakingChange]:
        changes: List[BreakingChange] = []
        callers = self._get_callers(old_fn.name)

        old_params = {p.name: p for p in old_fn.parameters}
        new_params = {p.name: p for p in new_fn.parameters}

        # 1. Added non-default parameter?
        for p in new_fn.parameters:
            if p.name not in old_params:
                # Disregard self or cls
                if p.name in ("self", "cls"):
                    continue
                # If newly added parameter does NOT have a default value, it breaks callers!
                if not p.has_default and p.kind not in ("VAR_POSITIONAL", "VAR_KEYWORD"):
                    changes.append(BreakingChange(
                        symbol_name=old_fn.qualname,
                        severity=BreakingChangeSeverity.ERROR,
                        message=f"Added mandatory parameter '{p.name}' to '{old_fn.qualname}' without default value.",
                        old_signature=self._format_sig(old_fn),
                        new_signature=self._format_sig(new_fn),
                        callers_affected=callers
                    ))

        # 2. Removed existing parameter?
        for p in old_fn.parameters:
            if p.name in ("self", "cls"):
                continue
            if p.name not in new_params:
                changes.append(BreakingChange(
                    symbol_name=old_fn.qualname,
                    severity=BreakingChangeSeverity.ERROR,
                    message=f"Removed parameter '{p.name}' from '{old_fn.qualname}'.",
                    old_signature=self._format_sig(old_fn),
                    new_signature=self._format_sig(new_fn),
                    callers_affected=callers
                ))

        # 3. Changed asyncness
        if old_fn.is_async != new_fn.is_async:
            state = "asynchronous" if new_fn.is_async else "synchronous"
            changes.append(BreakingChange(
                symbol_name=old_fn.qualname,
                severity=BreakingChangeSeverity.ERROR,
                message=f"Function '{old_fn.qualname}' changed from {'async' if old_fn.is_async else 'sync'} to {state}.",
                old_signature=self._format_sig(old_fn),
                new_signature=self._format_sig(new_fn),
                callers_affected=callers
            ))

        return changes

    def _get_callers(self, symbol_name: str) -> List[str]:
        if self.code_graph:
            callers = self.code_graph.find_callers(symbol_name)
            res = []
            for c in callers:
                if isinstance(c, str):
                    res.append(c)
                elif hasattr(c, "name"):
                    res.append(c.name)
            return sorted(res)
        return []

    def _format_sig(self, fn: FunctionContract) -> str:
        param_strs = []
        for p in fn.parameters:
            s = p.name
            if p.type_annotation:
                s += f": {p.type_annotation}"
            if p.has_default:
                s += f" = {p.default_repr}"
            param_strs.append(s)
        prefix = "async def " if fn.is_async else "def "
        ret = f" -> {fn.return_type}" if fn.return_type else ""
        return f"{prefix}{fn.name}({', '.join(param_strs)}){ret}"
