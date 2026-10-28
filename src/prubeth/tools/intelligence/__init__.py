"""PRUBETH Repository Intelligence Tools Wave.

Exports 10 precision code graph and AST intelligence tools:
1. CodeStructureTool
2. FindCallersTool
3. FindCalleesTool
4. FindTypeDefinitionTool
5. FindImplementationsTool
6. DetectCircularImportsTool
7. TraceDataFlowTool
8. FindDeadCodeTool
9. RankCentralFilesTool
10. ExplainSymbolTool
"""

from typing import List, Type

from prubeth.tools.base import BaseTool
from prubeth.tools.intelligence.code_structure import CodeStructureTool
from prubeth.tools.intelligence.find_callers import FindCallersTool
from prubeth.tools.intelligence.find_callees import FindCalleesTool
from prubeth.tools.intelligence.find_type_definition import FindTypeDefinitionTool
from prubeth.tools.intelligence.find_implementations import FindImplementationsTool
from prubeth.tools.intelligence.detect_circular_imports import DetectCircularImportsTool
from prubeth.tools.intelligence.trace_data_flow import TraceDataFlowTool
from prubeth.tools.intelligence.find_dead_code import FindDeadCodeTool
from prubeth.tools.intelligence.rank_central_files import RankCentralFilesTool
from prubeth.tools.intelligence.explain_symbol import ExplainSymbolTool

ALL_INTELLIGENCE_TOOLS: List[Type[BaseTool]] = [
    CodeStructureTool,
    FindCallersTool,
    FindCalleesTool,
    FindTypeDefinitionTool,
    FindImplementationsTool,
    DetectCircularImportsTool,
    TraceDataFlowTool,
    FindDeadCodeTool,
    RankCentralFilesTool,
    ExplainSymbolTool,
]

__all__ = [
    "ALL_INTELLIGENCE_TOOLS",
    "CodeStructureTool",
    "FindCallersTool",
    "FindCalleesTool",
    "FindTypeDefinitionTool",
    "FindImplementationsTool",
    "DetectCircularImportsTool",
    "TraceDataFlowTool",
    "FindDeadCodeTool",
    "RankCentralFilesTool",
    "ExplainSymbolTool",
]
