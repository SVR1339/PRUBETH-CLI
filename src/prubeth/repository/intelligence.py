import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

class RepositoryIntelligence:
    """Subsystem 3: Repository Intelligence Engine."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".prubeth"}

    def load_project_instructions(self) -> str:
        """Loads AGENTS.md, GEMINI.md, or CLAUDE.md if present in the repo root."""
        candidates = ["AGENTS.md", "GEMINI.md", "CLAUDE.md", ".agents/rules.md"]
        for c in candidates:
            p = self.workspace_root / c
            if p.is_file():
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        return f"### Project Instructions from {c}:\n" + f.read(4000)
                except Exception:
                    pass
        return ""

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
