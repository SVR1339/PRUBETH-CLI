"""PRUBETH Automated Unit Test Skeleton Generator Tool."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Any, List, Optional

from prubeth.tools.base import BaseTool, ToolParameter, ToolResult, ToolClearanceLevel
from prubeth.repository.ast_parser import PolyglotASTParser, SymbolKind


class TestGenTool(BaseTool):
    """Generates comprehensive unit test skeleton for functions or classes."""

    __test__ = False
    name = "test_gen"
    description = "Synthesizes comprehensive unit test skeletons with fixtures, happy-path, and edge cases."
    clearance_level = ToolClearanceLevel.READ_ONLY

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Path to the file containing the target symbol.",
                required=True
            ),
            ToolParameter(
                name="symbol_name",
                type="string",
                description="Target function or class name to generate tests for.",
                required=True
            ),
            ToolParameter(
                name="framework",
                type="string",
                description="Target test framework: 'pytest' (default) or 'unittest'.",
                required=False,
                default="pytest"
            )
        ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        file_path = arguments.get("file_path", "").strip()
        symbol_name = arguments.get("symbol_name", "").strip()
        framework = arguments.get("framework", "pytest").lower()

        if not file_path or not symbol_name:
            return ToolResult.fail("Missing file_path or symbol_name.", exit_code=1)

        p = Path(file_path)
        if not p.is_file():
            return ToolResult.fail(f"File '{file_path}' does not exist.", exit_code=1)

        parser = PolyglotASTParser()
        symbols = parser.parse_file(file_path)

        target_sym = None
        for sym in symbols:
            if sym.name == symbol_name:
                target_sym = sym
                break

        if not target_sym:
            return ToolResult.fail(
                f"Symbol '{symbol_name}' not found in '{file_path}'.",
                exit_code=1
            )

        module_import = p.stem
        # Derive module path e.g. src.prubeth.module
        parts = list(p.with_suffix("").parts)
        if "src" in parts:
            idx = parts.index("src")
            mod_dot = ".".join(parts[idx:])
        else:
            mod_dot = p.stem

        if target_sym.kind == SymbolKind.CLASS:
            code = self._generate_class_tests(target_sym, mod_dot, framework)
        else:
            code = self._generate_function_tests(target_sym, mod_dot, framework)

        return ToolResult.ok(
            code,
            metadata={"symbol": symbol_name, "kind": target_sym.kind.value, "module": mod_dot}
        )

    def _generate_function_tests(self, sym: Any, mod_dot: str, framework: str) -> str:
        name = sym.name
        params = [p for p in sym.parameters if p not in ("self", "cls")]
        param_args = ", ".join(f"{p}=None" for p in params)

        lines = [
            f'"""Automated unit tests for {name}."""',
            "",
            "import pytest",
            f"from {mod_dot} import {name}",
            "",
            f"def test_{name}_baseline():",
            f'    """Test standard valid invocation."""',
            f"    # TODO: Supply valid test arguments",
            f"    # result = {name}({param_args})",
            f"    # assert result is not None",
            "    pass",
            "",
            f"def test_{name}_edge_cases():",
            f'    """Test boundary conditions and edge cases."""',
            f"    # TODO: Add edge case assertions (empty, None, boundary numbers)",
            "    pass",
            "",
            f"def test_{name}_raises_on_invalid_input():",
            f'    """Test that invalid input raises appropriate exceptions."""',
            f"    # with pytest.raises((ValueError, TypeError)):",
            f"    #     {name}()",
            "    pass",
        ]
        return "\n".join(lines)

    def _generate_class_tests(self, sym: Any, mod_dot: str, framework: str) -> str:
        name = sym.name
        lines = [
            f'"""Automated unit tests for class {name}."""',
            "",
            "import pytest",
            f"from {mod_dot} import {name}",
            "",
            "@pytest.fixture",
            f"def {name.lower()}_instance():",
            f'    """Fixture providing an initialized {name} instance."""',
            f"    # TODO: Provide required constructor arguments",
            f"    return {name}()",
            "",
            f"def test_{name.lower()}_initialisation({name.lower()}_instance):",
            f'    """Verify correct instantiation."""',
            f"    assert {name.lower()}_instance is not None",
            "",
            f"def test_{name.lower()}_methods({name.lower()}_instance):",
            f'    """Verify public method invocations."""',
            "    pass",
        ]
        return "\n".join(lines)
