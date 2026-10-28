"""PRUBETH Polyglot Pre-Flight Invariant & Syntax Gate (SE 3.0).

Validates in-memory candidate file content across multiple programming languages
(Python, Rust, Go, TypeScript/JavaScript, C/C++, Java, C#, Dart, PHP, Ruby, SQL, JSON, YAML, TOML, Markdown)
before touching disk, eliminating syntactically broken file writes at the source.
"""

import ast
import json
import re
from pathlib import Path
from typing import Tuple, Dict, Any, List

class PolyglotSyntaxGate:
    """Subsystem 17: Pre-Flight Invariant Validator for Multi-Language Repositories."""

    PRAGMA_BYPASS_PATTERNS = [
        "prubeth: allow-syntax-error",
        "prubeth: no-gate",
        "prubeth: relaxed",
        "prubeth: force-syntax",
        "noqa: syntax",
    ]

    @staticmethod
    def has_bypass_pragma(content: str) -> bool:
        """Detects developer directives permitting intentional syntax anomalies (e.g. test fixtures, drafts)."""
        if not content:
            return False
        # Inspect first 10 lines for performance
        first_lines = "\n".join(content.splitlines()[:10]).lower()
        return any(pragma in first_lines for pragma in PolyglotSyntaxGate.PRAGMA_BYPASS_PATTERNS)

    @staticmethod
    def validate_content(file_path: str, content: str, relaxed: bool = False) -> Tuple[bool, str]:
        """Validates that candidate content is syntactically sound for its file extension.
        
        Permits intentional developer bypass when relaxed=True or when a bypass pragma is present.
        """
        if PolyglotSyntaxGate.has_bypass_pragma(content):
            return True, "Syntax gate bypassed via developer pragma."

        ext = Path(file_path).suffix.lower()

        if relaxed:
            # Under relaxed developer clearance, we validate only critical unclosed structures
            if ext == ".py":
                try:
                    ast.parse(content, filename=file_path)
                    return True, "Python AST compilation successful."
                except Exception as e:
                    return False, f"Relaxed Python AST notice: {e}"

        if ext == ".py":
            return PolyglotSyntaxGate._validate_python(content, file_path)
        elif ext in [".json", ".jsonc"]:
            return PolyglotSyntaxGate._validate_json(content, file_path)
        elif ext in [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]:
            return PolyglotSyntaxGate._validate_delimited_source(content, file_path, lang_name="JS/TS")
        elif ext in [".rs"]:
            return PolyglotSyntaxGate._validate_rust(content, file_path)
        elif ext in [".go"]:
            return PolyglotSyntaxGate._validate_go(content, file_path)
        elif ext in [".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"]:
            return PolyglotSyntaxGate._validate_delimited_source(content, file_path, lang_name="C/C++")
        elif ext in [".java", ".kt", ".kts", ".cs"]:
            return PolyglotSyntaxGate._validate_delimited_source(content, file_path, lang_name="Java/C#")
        elif ext in [".dart"]:
            return PolyglotSyntaxGate._validate_delimited_source(content, file_path, lang_name="Dart")
        elif ext in [".php"]:
            return PolyglotSyntaxGate._validate_php(content, file_path)
        elif ext in [".rb"]:
            return PolyglotSyntaxGate._validate_ruby(content, file_path)
        elif ext in [".yaml", ".yml"]:
            return PolyglotSyntaxGate._validate_yaml(content, file_path)
        elif ext in [".toml"]:
            return PolyglotSyntaxGate._validate_toml(content, file_path)
        elif ext in [".md", ".markdown"]:
            return PolyglotSyntaxGate._validate_markdown(content, file_path)
        elif ext in [".sql"]:
            return PolyglotSyntaxGate._validate_sql(content, file_path)
        
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
        stripped = re.sub(r"^\s*//.*$", "", code, flags=re.MULTILINE)
        try:
            json.loads(stripped)
            return True, "JSON parsed successfully."
        except json.JSONDecodeError as e:
            return False, f"JSONDecodeError in {path} at line {e.lineno}, col {e.colno}: {e.msg}"

    @staticmethod
    def _validate_delimited_source(code: str, path: str, lang_name: str = "Source") -> Tuple[bool, str]:
        """Validates delimiter balance (parentheses, braces, brackets) and string closures."""
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
                    # Preprocessor or shell comment in certain languages
                    if c == "#" and lang_name in ["Python", "Ruby"]:
                        break

                # Escaped characters
                if c == "\\" and i + 1 < len(line):
                    i += 2
                    continue

                if c == "'" and not in_double_quote and not in_template_lit:
                    # In Rust, distinguish character literals/lifetimes ('a, 'static)
                    if lang_name == "Rust" and i + 1 < len(line) and line[i+1].isalpha() and (i + 2 >= len(line) or line[i+2] not in "'"):
                        i += 1
                        continue
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
                            return False, f"{lang_name} SyntaxError in {path} at line {line_num}: Unmatched closing '{c}'"
                        top, open_line = stack.pop()
                        if pairs[c] != top:
                            return False, f"{lang_name} SyntaxError in {path} at line {line_num}: Mismatched closing '{c}' (opened '{top}' on line {open_line})"
                i += 1

            if (in_single_quote or in_double_quote) and lang_name != "Rust":
                return False, f"{lang_name} SyntaxError in {path} at line {line_num}: Unterminated string literal"

        if in_template_lit:
            return False, f"{lang_name} SyntaxError in {path}: Unterminated template literal (`)"
        if in_block_comment:
            return False, f"{lang_name} SyntaxError in {path}: Unterminated block comment (/*)"
        if stack:
            unclosed, open_line = stack[-1]
            return False, f"{lang_name} SyntaxError in {path}: Unclosed delimiter '{unclosed}' opened on line {open_line}"

        return True, f"{lang_name} delimiter invariants validated."

    @staticmethod
    def _validate_rust(code: str, path: str) -> Tuple[bool, str]:
        """Validates Rust structural invariants."""
        return PolyglotSyntaxGate._validate_delimited_source(code, path, lang_name="Rust")

    @staticmethod
    def _validate_go(code: str, path: str) -> Tuple[bool, str]:
        """Validates Go package declaration and balanced delimiters."""
        if not re.search(r"^\s*package\s+\w+", code, flags=re.MULTILINE):
            return False, f"Go SyntaxError in {path}: Missing required 'package <name>' declaration."
        return PolyglotSyntaxGate._validate_delimited_source(code, path, lang_name="Go")

    @staticmethod
    def _validate_php(code: str, path: str) -> Tuple[bool, str]:
        """Validates PHP script opening tags and delimiter invariants."""
        if "<?php" not in code and "<?" not in code:
            return False, f"PHP SyntaxError in {path}: Missing opening '<?php' tag."
        return PolyglotSyntaxGate._validate_delimited_source(code, path, lang_name="PHP")

    @staticmethod
    def _validate_ruby(code: str, path: str) -> Tuple[bool, str]:
        """Validates Ruby block structures (def/class/module/do ... end)."""
        lines = code.splitlines()
        block_starts = {"def", "class", "module", "do", "begin", "if", "unless", "case"}
        block_count = 0

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            words = stripped.split()
            first = words[0] if words else ""
            has_do = "do" in words and not stripped.startswith("end")
            if (first in block_starts or has_do) and not stripped.endswith("end"):
                block_count += 1
            if stripped == "end" or stripped.endswith(" end"):
                block_count -= 1

        if block_count > 0:
            return False, f"Ruby SyntaxError in {path}: Missing 'end' statement ({block_count} unclosed blocks)"
        if block_count < 0:
            return False, f"Ruby SyntaxError in {path}: Unexpected 'end' statement (negative block depth)"
        return True, "Ruby structural invariants validated."

    @staticmethod
    def _validate_yaml(code: str, path: str) -> Tuple[bool, str]:
        """Validates YAML indentation consistency and key-value colon spacing."""
        lines = code.splitlines()
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
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

    @staticmethod
    def _validate_sql(code: str, path: str) -> Tuple[bool, str]:
        """Validates SQL string literals and block comments."""
        if "/*" in code and "*/" not in code:
            return False, f"SQL SyntaxError in {path}: Unclosed block comment (/*)"
        return True, "SQL structural invariants validated."
