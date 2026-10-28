"""PRUBETH In-Memory Code Call Graph & Architectural Dependency Engine.

Constructs directed relational graphs of workspace repositories:
- Symbol-level call graphs (caller -> callee)
- File-level import graphs (importer -> importee)
- Class inheritance hierarchies (child -> parent)
- Topological sorting, circular dependency detection, and PageRank architectural centrality.

Enforces zero external dependencies, deterministic algorithms, and micro-footprint invariants.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

from prubeth.repository.ast_parser import CodeSymbol, SymbolKind


@dataclass
class GraphEdge:
    """Directed relation edge between nodes."""
    source: str
    target: str
    kind: str  # "calls", "imports", "inherits", "contains"
    weight: float = 1.0


class CodeGraph:
    """In-memory directed code and dependency graph."""

    def __init__(self):
        # Maps symbol_id (f"{file_path}::{name}") -> CodeSymbol
        self.symbols: Dict[str, CodeSymbol] = {}
        # Maps simple name -> List[symbol_id] for lookup
        self.name_to_ids: Dict[str, List[str]] = defaultdict(list)
        # File path -> set of symbol_ids
        self.file_symbols: Dict[str, Set[str]] = defaultdict(set)
        # Call graph: caller_id -> set of callee names/ids
        self.call_edges: Dict[str, Set[str]] = defaultdict(set)
        # Reverse call graph: callee_name -> set of caller_ids
        self.caller_edges: Dict[str, Set[str]] = defaultdict(set)
        # Import graph: file_path -> set of imported module/file paths
        self.file_imports: Dict[str, Set[str]] = defaultdict(set)
        # Inheritance graph: child_class_id -> set of base_names
        self.inheritance: Dict[str, Set[str]] = defaultdict(set)
        # Reverse inheritance: base_name -> set of child_class_ids
        self.implementations: Dict[str, Set[str]] = defaultdict(set)

    def add_symbol(self, symbol: CodeSymbol) -> str:
        """Adds a parsed code symbol into the graph and wires edges."""
        sym_id = f"{symbol.file_path}::{symbol.name}"
        self.symbols[sym_id] = symbol
        self.name_to_ids[symbol.name].append(sym_id)
        self.file_symbols[symbol.file_path].add(sym_id)

        # Wire calls
        for call_name in symbol.calls:
            self.call_edges[sym_id].add(call_name)
            self.caller_edges[call_name].add(sym_id)

        # Wire inheritance
        for base in symbol.bases:
            self.inheritance[sym_id].add(base)
            self.implementations[base].add(sym_id)

        # Wire file imports
        for imp in symbol.imports:
            mod = imp.get("module")
            if mod:
                self.file_imports[symbol.file_path].add(mod)

        return sym_id

    def add_file_import(self, source_file: str, imported_target: str) -> None:
        """Adds an explicit file import dependency."""
        self.file_imports[source_file].add(imported_target)

    def find_callers(self, target_symbol_name: str) -> List[CodeSymbol]:
        """Returns all functions or methods that call the specified symbol."""
        caller_ids = self.caller_edges.get(target_symbol_name, set())
        results: List[CodeSymbol] = []
        for c_id in sorted(caller_ids):
            if c_id in self.symbols:
                results.append(self.symbols[c_id])
        return results

    def find_callees(self, caller_symbol_name: str) -> List[Dict[str, Any]]:
        """Returns all calls made by functions matching the specified name."""
        sym_ids = self.name_to_ids.get(caller_symbol_name, [])
        callees: List[Dict[str, Any]] = []

        for s_id in sym_ids:
            sym = self.symbols[s_id]
            for called_name in sorted(self.call_edges.get(s_id, set())):
                # Attempt to resolve called_name to known symbol
                resolved = [self.symbols[t_id] for t_id in self.name_to_ids.get(called_name, [])]
                callees.append({
                    "caller": sym.name,
                    "caller_file": sym.file_path,
                    "callee_name": called_name,
                    "resolved": [r.to_dict() for r in resolved],
                    "is_external": len(resolved) == 0,
                })
        return callees

    def find_implementations(self, base_name: str) -> List[CodeSymbol]:
        """Returns all classes or structs that inherit from or implement base_name."""
        child_ids = self.implementations.get(base_name, set())
        results: List[CodeSymbol] = []
        for c_id in sorted(child_ids):
            if c_id in self.symbols:
                results.append(self.symbols[c_id])
        return results

    def find_type_definition(self, symbol_name: str) -> List[CodeSymbol]:
        """Resolves symbol definitions matching name across workspace."""
        sym_ids = self.name_to_ids.get(symbol_name, [])
        return [self.symbols[s_id] for s_id in sym_ids]

    def detect_circular_imports(self) -> List[List[str]]:
        """Finds all circular import cycles in the workspace using DFS cycle detection."""
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)

            for neighbor in sorted(self.file_imports.get(node, set())):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start_idx = rec_stack.index(neighbor)
                    cycle = rec_stack[cycle_start_idx:] + [neighbor]
                    # Canonicalise cycle representation to prevent duplicates
                    canonical = self._canonicalise_cycle(cycle)
                    if canonical not in cycles:
                        cycles.append(canonical)

            rec_stack.pop()

        for file_node in sorted(self.file_imports.keys()):
            if file_node not in visited:
                dfs(file_node)

        return sorted(cycles)

    @staticmethod
    def _canonicalise_cycle(cycle: List[str]) -> List[str]:
        """Returns a deterministic normalised representation of a cycle."""
        nodes = cycle[:-1]
        if not nodes:
            return cycle
        min_idx = nodes.index(min(nodes))
        rotated = nodes[min_idx:] + nodes[:min_idx]
        return rotated + [rotated[0]]

    def rank_central_files(
        self,
        damping: float = 0.85,
        max_iterations: int = 50,
        tolerance: float = 1e-5
    ) -> List[Tuple[str, float]]:
        """Calculates architectural centrality of repository files using PageRank.
        
        Files imported by many other central files score higher, revealing
        foundational core modules of the project.
        """
        all_files = set(self.file_imports.keys())
        for targets in self.file_imports.values():
            all_files.update(targets)

        if not all_files:
            return []

        files_list = sorted(all_files)
        n = len(files_list)
        initial_score = 1.0 / n
        scores: Dict[str, float] = {f: initial_score for f in files_list}

        # Build incoming edges (target <- sources)
        inbound: Dict[str, List[str]] = defaultdict(list)
        out_degree: Dict[str, int] = defaultdict(int)

        for src, targets in self.file_imports.items():
            valid_targets = [t for t in targets if t in all_files]
            out_degree[src] = len(valid_targets)
            for tgt in valid_targets:
                inbound[tgt].append(src)

        # Iterative power method with dangling-node conservation
        for _ in range(max_iterations):
            new_scores: Dict[str, float] = {}
            max_diff = 0.0

            dangling_sum = sum(scores[node] for node in files_list if out_degree[node] == 0)
            dangling_contrib = damping * (dangling_sum / n)
            base_val = ((1.0 - damping) / n) + dangling_contrib

            for node in files_list:
                incoming_sum = 0.0
                for inc in inbound.get(node, []):
                    deg = out_degree[inc]
                    if deg > 0:
                        incoming_sum += scores[inc] / deg

                new_rank = base_val + damping * incoming_sum
                diff = abs(new_rank - scores[node])
                if diff > max_diff:
                    max_diff = diff
                new_scores[node] = new_rank

            scores = new_scores
            if max_diff < tolerance:
                break

        # Return sorted by descending PageRank score
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [(f, round(score, 6)) for f, score in ranked]

    def find_dead_code(
        self,
        ignore_tests: bool = True,
        ignore_entrypoints: bool = True
    ) -> List[CodeSymbol]:
        """Identifies functions and classes with zero incoming callers."""
        dead_symbols: List[CodeSymbol] = []
        entrypoint_names = {"main", "run", "cli", "app", "start", "handler", "execute", "entrypoint", "__init__"}

        for sym_id, symbol in sorted(self.symbols.items()):
            # Skip non-executable symbols
            if symbol.kind not in {SymbolKind.FUNCTION, SymbolKind.CLASS, SymbolKind.METHOD}:
                continue

            # Skip test files
            if ignore_tests:
                lower_path = symbol.file_path.lower()
                if "test" in lower_path or lower_path.endswith("_test.py") or lower_path.endswith(".spec.ts"):
                    continue

            # Skip entrypoints and dunder methods
            if ignore_entrypoints:
                if symbol.name.lower() in entrypoint_names or symbol.name.startswith("__"):
                    continue

            # Check if any symbol calls this symbol
            caller_ids = self.caller_edges.get(symbol.name, set())
            if not caller_ids:
                dead_symbols.append(symbol)

        return dead_symbols

    def trace_data_flow(
        self,
        start_symbol_name: str,
        max_depth: int = 3,
        direction: str = "forward"
    ) -> Dict[str, Any]:
        """Traces call hierarchy forward (callees) or backward (callers)."""
        visited: Set[str] = set()

        def _traverse(current_name: str, current_depth: int) -> Dict[str, Any]:
            node_info: Dict[str, Any] = {
                "name": current_name,
                "depth": current_depth,
                "nodes": [],
            }
            if current_depth >= max_depth:
                return node_info

            visited.add(current_name)
            if direction == "forward":
                # Find what this calls
                callees = self.find_callees(current_name)
                for c in callees:
                    c_name = c["callee_name"]
                    if c_name not in visited:
                        node_info["nodes"].append(_traverse(c_name, current_depth + 1))
            else:
                # Find who calls this
                callers = self.find_callers(current_name)
                for c in callers:
                    if c.name not in visited:
                        node_info["nodes"].append(_traverse(c.name, current_depth + 1))

            return node_info

        return _traverse(start_symbol_name, 0)
