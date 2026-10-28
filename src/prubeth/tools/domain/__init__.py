"""PRUBETH Domain-Specific Developer Intelligence Tools."""

from prubeth.tools.domain.todo import TodoTool
from prubeth.tools.domain.test_gen import TestGenTool
from prubeth.tools.domain.security_linter import SecurityLinterTool
from prubeth.tools.domain.crash_debugger import CrashDebuggerTool
from prubeth.tools.domain.benchmark import BenchmarkTool
from prubeth.tools.domain.heal import HealTool
from prubeth.tools.domain.spec_contract import SpecContractTool

ALL_DOMAIN_TOOLS = [
    TodoTool,
    TestGenTool,
    SecurityLinterTool,
    CrashDebuggerTool,
    BenchmarkTool,
    HealTool,
    SpecContractTool,
]

__all__ = [
    "TodoTool",
    "TestGenTool",
    "SecurityLinterTool",
    "CrashDebuggerTool",
    "BenchmarkTool",
    "HealTool",
    "SpecContractTool",
    "ALL_DOMAIN_TOOLS",
]
