"""PRUBETH Polyglot Language & Multi-Stack Ecosystem (SE 3.0).

Subsystem 20: Comprehensive polyglot language stack definitions and auto-detection
for Python, TypeScript, JavaScript, Rust, Go, Java, C#, C/C++, Dart/Flutter, PHP,
Ruby, Swift, and Kotlin.
"""

from prubeth.polyglot.stacks import (
    LanguageStack,
    SUPPORTED_STACKS,
    get_stack_by_id,
    detect_stack_from_workspace
)
from prubeth.polyglot.manager import PolyglotLanguageManager

__all__ = [
    "LanguageStack",
    "SUPPORTED_STACKS",
    "get_stack_by_id",
    "detect_stack_from_workspace",
    "PolyglotLanguageManager"
]
