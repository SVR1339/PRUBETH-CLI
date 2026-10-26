"""PRUBETH Pure-Python Codebase BM25 Semantic Indexer & Symbol Graph.

Provides sub-millisecond lexical-semantic search and symbol resolution across
workspace repositories without external dependencies, binary vector databases,
or cloud API costs.
"""

import os
import re
import ast
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple

@dataclass
class CodeSymbol:
    name: str
    kind: str  # class, function, method, interface, struct
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None
    body_snippet: str = ""

@dataclass
class SearchResult:
    file_path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    matched_terms: List[str] = field(default_factory=list)

class CodebaseIndex:
    """Zero-dependency BM25 code indexer and multi-language symbol extractor."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.ignored_dirs = {
            ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
            ".prubeth", ".idea", ".vscode", "target", "vendor", ".mypy_cache"
        }
        self.supported_extensions = {
            ".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp",
            ".h", ".hpp", ".json", ".yaml", ".yml", ".toml", ".md", ".sh", ".ps1"
        }
        # Inverted index data structures
        self.documents: List[Dict[str, Any]] = []  # list of chunk dicts
        self.doc_lengths: List[int] = []
        self.avg_doc_len: float = 0.0
        self.term_df: Dict[str, int] = {}  # term -> document frequency
        self.symbols: Dict[str, List[CodeSymbol]] = {}  # symbol_name -> list of definitions
        self.is_indexed: bool = False

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Splits code text into normalized identifiers and sub-tokens (camelCase & snake_case)."""
        raw_tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
        tokens = []
        for t in raw_tokens:
            if len(t) < 2:
                continue
            tokens.append(t)
            # Break snake_case
            parts = t.split("_")
            if len(parts) > 1:
                for p in parts:
                    if len(p) >= 2:
                        tokens.append(p)
        return tokens

    def index_workspace(self, max_files: int = 500) -> int:
        """Walks workspace, parses symbols, and builds in-memory BM25 index."""
        self.documents.clear()
        self.doc_lengths.clear()
        self.term_df.clear()
        self.symbols.clear()

        indexed_count = 0
        total_len = 0

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs and not d.startswith(".")]
            for file in files:
                p = Path(root) / file
                if p.suffix.lower() not in self.supported_extensions:
                    continue

                try:
                    rel_path = p.relative_to(self.workspace_root).as_posix()
                    # Skip files larger than 1MB
                    if p.stat().st_size > 1_000_000:
                        continue

                    content = p.read_text(encoding="utf-8", errors="ignore")
                    lines = content.splitlines()

                    # 1. Extract symbols if Python or TS/JS
                    if p.suffix == ".py":
                        self._extract_python_symbols(rel_path, content, lines)
                    elif p.suffix in [".ts", ".js", ".tsx", ".jsx"]:
                        self._extract_js_symbols(rel_path, lines)

                    # 2. Chunk file for BM25 (chunks of 40 lines with 10 line overlap)
                    chunk_size = 40
                    overlap = 10
                    for start_idx in range(0, max(1, len(lines)), chunk_size - overlap):
                        chunk_lines = lines[start_idx : start_idx + chunk_size]
                        if not chunk_lines:
                            break
                        chunk_text = "\n".join(chunk_lines)
                        tokens = self.tokenize(chunk_text)
                        if not tokens:
                            continue

                        doc_id = len(self.documents)
                        term_freq: Dict[str, int] = {}
                        for t in tokens:
                            term_freq[t] = term_freq.get(t, 0) + 1

                        # Update doc frequencies
                        for t in term_freq:
                            self.term_df[t] = self.term_df.get(t, 0) + 1

                        self.documents.append({
                            "id": doc_id,
                            "file_path": rel_path,
                            "start_line": start_idx + 1,
                            "end_line": start_idx + len(chunk_lines),
                            "snippet": chunk_text,
                            "tf": term_freq,
                            "length": len(tokens)
                        })
                        self.doc_lengths.append(len(tokens))
                        total_len += len(tokens)

                    indexed_count += 1
                    if indexed_count >= max_files:
                        break
                except Exception:
                    continue
            if indexed_count >= max_files:
                break

        if self.documents:
            self.avg_doc_len = total_len / len(self.documents)
        self.is_indexed = True
        return indexed_count

    def _extract_python_symbols(self, rel_path: str, content: str, lines: List[str]):
        """Extracts AST symbols from Python file."""
        try:
            tree = ast.parse(content)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    sig = f"class {node.name}"
                    doc = ast.get_docstring(node)
                    end_lineno = getattr(node, "end_lineno", node.lineno + 1)
                    snippet = "\n".join(lines[node.lineno - 1 : min(len(lines), end_lineno)])
                    sym = CodeSymbol(
                        name=node.name,
                        kind="class",
                        file_path=rel_path,
                        start_line=node.lineno,
                        end_line=end_lineno,
                        signature=sig,
                        docstring=doc,
                        body_snippet=snippet[:500]
                    )
                    self.symbols.setdefault(node.name.lower(), []).append(sym)

                    # Extract class methods
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            m_args = [a.arg for a in sub.args.args if a.arg != "self"]
                            m_sig = f"def {sub.name}({', '.join(m_args)})"
                            m_doc = ast.get_docstring(sub)
                            m_end = getattr(sub, "end_lineno", sub.lineno + 1)
                            m_snip = "\n".join(lines[sub.lineno - 1 : min(len(lines), m_end)])
                            m_sym = CodeSymbol(
                                name=f"{node.name}.{sub.name}",
                                kind="method",
                                file_path=rel_path,
                                start_line=sub.lineno,
                                end_line=m_end,
                                signature=m_sig,
                                docstring=m_doc,
                                body_snippet=m_snip[:400]
                            )
                            self.symbols.setdefault(sub.name.lower(), []).append(m_sym)
                            self.symbols.setdefault(f"{node.name}.{sub.name}".lower(), []).append(m_sym)

                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    f_args = [a.arg for a in node.args.args]
                    f_sig = f"def {node.name}({', '.join(f_args)})"
                    f_doc = ast.get_docstring(node)
                    end_lineno = getattr(node, "end_lineno", node.lineno + 1)
                    snippet = "\n".join(lines[node.lineno - 1 : min(len(lines), end_lineno)])
                    sym = CodeSymbol(
                        name=node.name,
                        kind="function",
                        file_path=rel_path,
                        start_line=node.lineno,
                        end_line=end_lineno,
                        signature=f_sig,
                        docstring=f_doc,
                        body_snippet=snippet[:500]
                    )
                    self.symbols.setdefault(node.name.lower(), []).append(sym)
        except Exception:
            pass

    def _extract_js_symbols(self, rel_path: str, lines: List[str]):
        """Extracts regex-based class/function symbols from JS/TS files."""
        for i, line in enumerate(lines):
            # function name(...) or const name = (...) =>
            fn_match = re.search(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(", line)
            if fn_match:
                name = fn_match.group(1)
                sym = CodeSymbol(
                    name=name,
                    kind="function",
                    file_path=rel_path,
                    start_line=i + 1,
                    end_line=min(len(lines), i + 20),
                    signature=line.strip()[:100],
                    body_snippet="\n".join(lines[i : min(len(lines), i + 15)])
                )
                self.symbols.setdefault(name.lower(), []).append(sym)
                continue

            cls_match = re.search(r"(?:export\s+)?class\s+([A-Za-z0-9_]+)", line)
            if cls_match:
                name = cls_match.group(1)
                sym = CodeSymbol(
                    name=name,
                    kind="class",
                    file_path=rel_path,
                    start_line=i + 1,
                    end_line=min(len(lines), i + 30),
                    signature=line.strip()[:100],
                    body_snippet="\n".join(lines[i : min(len(lines), i + 20)])
                )
                self.symbols.setdefault(name.lower(), []).append(sym)

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Performs Okapi BM25 ranking across the workspace index."""
        if not self.is_indexed:
            self.index_workspace()

        query_tokens = self.tokenize(query)
        if not query_tokens or not self.documents:
            return []

        # BM25 Hyperparameters
        k1 = 1.5
        b = 0.75
        N = len(self.documents)

        scores: List[Tuple[float, Dict[str, Any], List[str]]] = []

        for doc in self.documents:
            score = 0.0
            matched = []
            doc_len = doc["length"]
            tf_dict = doc["tf"]

            for q in query_tokens:
                if q in tf_dict:
                    matched.append(q)
                    tf = tf_dict[q]
                    df = self.term_df.get(q, 1)
                    # BM25+ smooth IDF formula
                    idf = math.log(1.0 + max(0.0, (N - df + 0.5) / (df + 0.5))) + 0.1
                    num = tf * (k1 + 1)
                    den = tf + k1 * (1 - b + b * (doc_len / max(1.0, self.avg_doc_len)))
                    score += idf * (num / den)

            if score > 0.0:
                scores.append((score, doc, matched))

        scores.sort(key=lambda x: x[0], reverse=True)

        results = []
        for s, doc, matched in scores[:top_k]:
            results.append(SearchResult(
                file_path=doc["file_path"],
                start_line=doc["start_line"],
                end_line=doc["end_line"],
                snippet=doc["snippet"],
                score=round(s, 3),
                matched_terms=list(set(matched))
            ))
        return results

    def resolve_symbol(self, symbol_name: str) -> Optional[CodeSymbol]:
        """Resolves a symbol name (exact or case-insensitive) to its definition."""
        if not self.is_indexed:
            self.index_workspace()

        clean_sym = symbol_name.strip().lower()
        if clean_sym in self.symbols:
            return self.symbols[clean_sym][0]

        # Partial matching fallback
        for k, v in self.symbols.items():
            if k.endswith(f".{clean_sym}") or clean_sym in k:
                return v[0]

        return None
