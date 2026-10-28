"""PRUBETH Subagent Interfaces, Roles, and Specifications."""

from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List

class SubagentRole(str, Enum):
    ARCHITECT = "architect"          # High-level architecture, plan breakdown, budget sentinel
    CODER = "coder"                  # Fast implementation & code synthesis in isolated worktree
    CRITIC = "critic"                # Adversarial red-team auditor (catches smells, regressions, security holes)
    TEST_ENGINEER = "test_engineer"  # Author of comprehensive test suites & invariant tests
    DOCS = "docs"                    # Documentation & API reference specialist

class SubagentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    AUDITING = "auditing"
    MERGED = "merged"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class SubagentSpec:
    id: str
    role: SubagentRole
    goal: str
    model_override: Optional[str] = None
    max_turns: int = 8
    worktree_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SubagentResult:
    subagent_id: str
    role: SubagentRole
    success: bool
    state: SubagentState
    output: str
    diff: str = ""
    modified_files: List[str] = field(default_factory=list)
    critic_approved: bool = False
    critic_notes: str = ""
    turns_used: int = 0

    @property
    def summary(self) -> str:
        return self.output

    @property
    def files_modified(self) -> List[str]:
        return self.modified_files
