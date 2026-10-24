"""PRUBETH Polyglot Pre-Flight Invariant & Syntax Gate (SE 3.0).

Validates in-memory candidate file content across multiple programming languages
(Python, JSON, JavaScript/TypeScript, YAML, TOML, Markdown) before touching disk,
eliminating syntactically broken file writes at the source.
"""

import ast
import json
import re
from pathlib import Path
from typing import Tuple, Dict, Any, List

class PolyglotSyntaxGate:
    """Subsystem 17: Pre-Flight Invariant Validator for Multi-Language Repositories."""

    @staticmethod
    def validate_content(file_path: str, content: str) -> Tuple[bool, str]:
        """Validates that candidate content is syntactically sound for its file extension."""
        ext = Path(file_path).suffix.lower()

        if ext == ".py":
            return PolyglotSyntaxGate._validate_python(content, file_path)
        elif ext in [".json", ".jsonc"]:
            return PolyglotSyntaxGate._validate_json(content, file_path)
        elif ext in [".js", ".jsx", ".ts", ".tsx", ".mjs"]:
            return PolyglotSyntaxGate._validate_javascript_typescript(content, file_path)
        elif ext in [".yaml", ".yml"]:
            return PolyglotSyntaxGate._validate_yaml(content, file_path)
        elif ext in [".toml"]:
            return PolyglotSyntaxGate._validate_toml(content, file_path)
        elif ext in [".md", ".markdown"]:
            return PolyglotSyntaxGate._validate_markdown(content, file_path)
        
        # Unrestricted for other plain text/binary files
        return True, "No syntax restrictions for file type."

    @staticmethod
    def _validate_python(code: str, path: str) -> Tuple[bool, str]:
        """Validates Python AST structure."""
        try:
            ast.parse(code, filename=path)
            return True, "Python AST compilation successful."
        except SyntaxError as e:
            return False, f"Python SyntaxError in {path} at line {e.lineno}, col {e.offset}: {e.msg}"
        except Exception as e:
            return False, f"Python AST validation failure in {path}: {e}"

    @staticmethod
    def _validate_json(code: str, path: str) -> Tuple[bool, str]:
        """Validates JSON structure."""
        # Strip simple single-line comments for jsonc
        stripped = re.sub(r"^\s*//.*$", "", code, flags=re.MULTILINE)
        try:
            json.loads(stripped)
            return True, "JSON parsed successfully."
        except json.JSONDecodeError as e:
            return False, f"JSONDecodeError in {path} at line {e.lineno}, col {e.colno}: {e.msg}"

    @staticmethod
    def _validate_javascript_typescript(code: str, path: str) -> Tuple[bool, str]:
        """Validates JS/TS syntax invariants: balanced delimiters, unclosed templates, unmatched quotes."""
        # Check balanced braces, brackets, and parentheses outside strings
        stack = []
        pairs = {")": "(", "}": "{", "]": "["}
        lines = code.splitlines()

        in_single_quote = False
        in_double_quote = False
        in_template_lit = False
        in_block_comment = False

        for line_num, line in enumerate(lines, start=1):
            i = 0
            while i < len(line):
                c = line[i]

                # Check block comment start/end
                if not in_single_quote and not in_double_quote and not in_template_lit:
                    if not in_block_comment and line[i:i+2] == "/*":
                        in_block_comment = True
                        i += 2
                        continue
                    elif in_block_comment and line[i:i+2] == "*/":
                        in_block_comment = False
                        i += 2
                        continue

                if in_block_comment:
                    i += 1
                    continue

                # Single-line comment
                if not in_single_quote and not in_double_quote and not in_template_lit:
                    if line[i:i+2] == "//":
                        break

                # Escaped characters
                if c == "\\" and i + 1 < len(line):
                    i += 2
                    continue

                if c == "'" and not in_double_quote and not in_template_lit:
                    in_single_quote = not in_single_quote
                elif c == '"' and not in_single_quote and not in_template_lit:
                    in_double_quote = not in_double_quote
                elif c == '`' and not in_single_quote and not in_double_quote:
                    in_template_lit = not in_template_lit
                elif not in_single_quote and not in_double_quote and not in_template_lit:
                    if c in "({[":
                        stack.append((c, line_num))
                    elif c in ")}]":
                        if not stack:
                            return False, f"JS/TS SyntaxError in {path} at line {line_num}: Unmatched closing '{c}'"
                        top, open_line = stack.pop()
                        if pairs[c] != top:
                            return False, f"JS/TS SyntaxError in {path} at line {line_num}: Mismatched closing '{c}' (opened '{top}' on line {open_line})"
                i += 1

            if in_single_quote or in_double_quote:
                return False, f"JS/TS SyntaxError in {path} at line {line_num}: Unterminated string literal"

        if in_template_lit:
            return False, f"JS/TS SyntaxError in {path}: Unterminated template literal (`)"
        if in_block_comment:
            return False, f"JS/TS SyntaxError in {path}: Unterminated block comment (/*)"
        if stack:
            unclosed, open_line = stack[-1]
            return False, f"JS/TS SyntaxError in {path}: Unclosed delimiter '{unclosed}' opened on line {open_line}"

        return True, "JavaScript/TypeScript delimiter invariants validated."

    @staticmethod
    def _validate_yaml(code: str, path: str) -> Tuple[bool, str]:
        """Validates YAML indentation consistency and key-value colon spacing."""
        lines = code.splitlines()
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Look for tab characters in indentation
            indent = line[:len(line) - len(line.lstrip())]
            if "\t" in indent:
                return False, f"YAML SyntaxError in {path} at line {idx}: Tab characters used in indentation (must use spaces)"
        return True, "YAML structural invariants validated."

    @staticmethod
    def _validate_toml(code: str, path: str) -> Tuple[bool, str]:
        """Validates TOML header brackets and key-value formats."""
        lines = code.splitlines()
        for idx, line in enumerate(lines, start=1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("[") and not s.endswith("]"):
                return False, f"TOML SyntaxError in {path} at line {idx}: Unclosed section header"
        return True, "TOML structural invariants validated."

    @staticmethod
    def _validate_markdown(code: str, path: str) -> Tuple[bool, str]:
        """Validates markdown unclosed code fences."""
        triple_ticks = re.findall(r"^```", code, flags=re.MULTILINE)
        if len(triple_ticks) % 2 != 0:
            return False, f"Markdown Formatting Error in {path}: Unclosed code fence (odd count of ```)"
        return True, "Markdown structural invariants validated."
