import ast
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

class RepositoryIntelligence:
    """Subsystem 3: Repository Intelligence & AST Dependency Engine."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".prubeth"}

    def load_project_instructions(self) -> str:
        """Loads Global Schema Rules, Workspace Rules (PRUBETH.md, AGENTS.md, etc.), and Learned Invariants."""
        rules_chunks = []

        # 1. Global User Schema Rules (~/.prubeth/rules/*.md or ~/.prubeth/rules.md)
        global_prubeth_dir = Path.home() / ".prubeth"
        global_rules_file = global_prubeth_dir / "rules.md"
        if global_rules_file.is_file():
            try:
                content = global_rules_file.read_text(encoding="utf-8", errors="ignore").strip()
                if content:
                    rules_chunks.append("### Global Schema Rules (~/.prubeth/rules.md):\n" + content[:3000])
            except Exception:
                pass

        global_rules_dir = global_prubeth_dir / "rules"
        if global_rules_dir.is_dir():
            for rf in sorted(global_rules_dir.glob("*.md")):
                try:
                    c = rf.read_text(encoding="utf-8", errors="ignore").strip()
                    if c:
                        rules_chunks.append(f"### Global Rule ({rf.name}):\n" + c[:2000])
                except Exception:
                    pass

        # 2. Workspace Project Rules (PRUBETH.md takes primary priority)
        candidates = ["PRUBETH.md", ".prubeth/rules.md", "AGENTS.md", "GEMINI.md", "CLAUDE.md", ".agents/rules.md"]
        for c in candidates:
            p = self.workspace_root / c
            if p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore").strip()
                    if content:
                        rules_chunks.append(f"### Workspace Project Rules ({c}):\n" + content[:4000])
                        break
                except Exception:
                    pass

        # 3. Persistent Project Learnings (.prubeth/memory/learnings.json)
        learnings_file = self.workspace_root / ".prubeth" / "memory" / "learnings.json"
        if learnings_file.is_file():
            try:
                raw_learnings = json.loads(learnings_file.read_text(encoding="utf-8", errors="ignore"))
                if raw_learnings:
                    items = [f"- [Learned Rule #{item.get('id', i+1)}] {item.get('directive')}" for i, item in enumerate(raw_learnings) if item.get("directive")]
                    if items:
                        rules_chunks.append("### Persistent Project Learnings & Invariants:\n" + "\n".join(items[:20]))
            except Exception:
                pass

        return "\n\n".join(rules_chunks)

    def extract_ast_signatures(self, file_path: Path) -> List[str]:
        """Parses Python file AST and returns method/class signatures."""
        sigs = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                tree = ast.parse(f.read(), filename=str(file_path))
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    sigs.append(f"  class {node.name}:")
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            args = [a.arg for a in sub.args.args if a.arg != "self"]
                            sigs.append(f"    def {sub.name}({', '.join(args)})")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [a.arg for a in node.args.args]
                    sigs.append(f"  def {node.name}({', '.join(args)})")
        except Exception:
            pass
        return sigs

    def build_context_skeleton(self, max_files: int = 30) -> str:
        """Generates a dense, token-efficient architectural overview of the repo."""
        lines = ["### Repository Architecture & Skeleton:"]
        instructions = self.load_project_instructions()
        if instructions:
            lines.append(instructions + "\n")

        indexed = 0
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.ignored]
            for file in files:
                if file.endswith((".py", ".ts", ".js", ".json", ".toml", ".yaml")):
                    p = Path(root) / file
                    rel = p.relative_to(self.workspace_root).as_posix()
                    if file.endswith(".py"):
                        sigs = self.extract_ast_signatures(p)
                        if sigs:
                            lines.append(f"📁 `{rel}`")
                            lines.extend(sigs[:10])
                            indexed += 1
                    else:
                        lines.append(f"📄 `{rel}`")
                        indexed += 1
                if indexed >= max_files:
                    break
            if indexed >= max_files:
                break

        return "\n".join(lines)

    def find_symbol_references(self, symbol_name: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """DeepMind Monorepo AST reference tracker: finds definitions and call sites of a symbol across the workspace."""
        references: List[Dict[str, Any]] = []
        clean_target = symbol_name.strip()
        if not clean_target:
            return references

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.ignored]
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.workspace_root).as_posix()

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    lines = content.splitlines()
                    tree = ast.parse(content, filename=str(file_path))
                except Exception:
                    continue

                class ReferenceVisitor(ast.NodeVisitor):
                    def __init__(self):
                        self.scope_stack: List[str] = []

                    def visit_ClassDef(self, node: ast.ClassDef):
                        is_def = (node.name == clean_target)
                        line_no = node.lineno
                        line_text = lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""
                        if is_def:
                            references.append({
                                "file": rel_path,
                                "line": line_no,
                                "scope": " -> ".join(self.scope_stack) or "module",
                                "kind": "class_definition",
                                "is_definition": True,
                                "context": line_text
                            })
                        self.scope_stack.append(f"class {node.name}")
                        self.generic_visit(node)
                        self.scope_stack.pop()

                    def visit_FunctionDef(self, node: ast.FunctionDef):
                        self._handle_function(node)

                    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                        self._handle_function(node)

                    def _handle_function(self, node):
                        is_def = (node.name == clean_target)
                        line_no = node.lineno
                        line_text = lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""
                        if is_def:
                            references.append({
                                "file": rel_path,
                                "line": line_no,
                                "scope": " -> ".join(self.scope_stack) or "module",
                                "kind": "function_definition",
                                "is_definition": True,
                                "context": line_text
                            })
                        self.scope_stack.append(f"def {node.name}()")
                        self.generic_visit(node)
                        self.scope_stack.pop()

                    def visit_Call(self, node: ast.Call):
                        # Matches Direct Function Call: func(...) or obj.func(...)
                        func_name = ""
                        if isinstance(node.func, ast.Name):
                            func_name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            func_name = node.func.attr

                        if func_name == clean_target:
                            line_no = getattr(node, "lineno", 0)
                            line_text = lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""
                            references.append({
                                "file": rel_path,
                                "line": line_no,
                                "scope": " -> ".join(self.scope_stack) or "module",
                                "kind": "call",
                                "is_definition": False,
                                "context": line_text
                            })
                        self.generic_visit(node)

                    def visit_Attribute(self, node: ast.Attribute):
                        if node.attr == clean_target and not isinstance(getattr(node, "ctx", None), ast.Store):
                            line_no = getattr(node, "lineno", 0)
                            line_text = lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""
                            # Avoid duplicate if already visited as Call
                            if not any(r["file"] == rel_path and r["line"] == line_no for r in references):
                                references.append({
                                    "file": rel_path,
                                    "line": line_no,
                                    "scope": " -> ".join(self.scope_stack) or "module",
                                    "kind": "attribute_access",
                                    "is_definition": False,
                                    "context": line_text
                                })
                        self.generic_visit(node)

                    def visit_Name(self, node: ast.Name):
                        if node.id == clean_target and isinstance(node.ctx, ast.Load):
                            line_no = getattr(node, "lineno", 0)
                            line_text = lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""
                            if not any(r["file"] == rel_path and r["line"] == line_no for r in references):
                                references.append({
                                    "file": rel_path,
                                    "line": line_no,
                                    "scope": " -> ".join(self.scope_stack) or "module",
                                    "kind": "symbol_reference",
                                    "is_definition": False,
                                    "context": line_text
                                })
                        self.generic_visit(node)

                try:
                    visitor = ReferenceVisitor()
                    visitor.visit(tree)
                except Exception:
                    pass

                if len(references) >= max_results:
                    break

            if len(references) >= max_results:
                break

        return references[:max_results]

    def list_all_symbols(self, max_symbols: int = 100) -> List[Dict[str, Any]]:
        """Extracts all top-level and class-level symbol definitions across workspace Python files."""
        symbols: List[Dict[str, Any]] = []

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.ignored]
            for file in sorted(files):
                if not file.endswith(".py"):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.workspace_root).as_posix()

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    tree = ast.parse(content, filename=str(file_path))
                except Exception:
                    continue

                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        symbols.append({
                            "name": node.name,
                            "type": "class",
                            "file": rel_path,
                            "line": node.lineno
                        })
                        for sub in node.body:
                            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                args = [a.arg for a in sub.args.args]
                                symbols.append({
                                    "name": f"{node.name}.{sub.name}",
                                    "type": "method",
                                    "file": rel_path,
                                    "line": sub.lineno,
                                    "signature": f"({', '.join(args)})"
                                })
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in node.args.args]
                        symbols.append({
                            "name": node.name,
                            "type": "function",
                            "file": rel_path,
                            "line": node.lineno,
                            "signature": f"({', '.join(args)})"
                        })

                if len(symbols) >= max_symbols:
                    break
            if len(symbols) >= max_symbols:
                break

        return symbols[:max_symbols]
