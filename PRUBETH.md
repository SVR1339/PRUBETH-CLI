# PRUBETH CLI Operational Schema & Engineering Rules

## 1. Project Invariants
- **Memory Ceiling**: Strictly under 33 MB CPU RAM; 0 MB GPU VRAM.
- **Portability**: Pure Python standard library with zero mandatory external binary prerequisites (no external Git, no ripgrep, no Node.js required).
- **License**: Apache-2.0 commercial open source.

## 2. Architecture & Subsystems
- **Subsystem 1**: Finite State Machine (TaskStateMachine) with 9 formal states.
- **Subsystem 2**: Autonomous Runtime Controller with Speculative Plan B contingency architecture.
- **Subsystem 3**: Repository Intelligence with AST symbol extraction and global rule ingestion.
- **Subsystem 4**: Tool Execution Engine with security path jail and audit logging.
- **Subsystem 5**: Deterministic Snapshot Manager with pure-Python SHA-256 tree rollback.
- **Subsystem 6**: Universal Model Gateway with multi-provider cascade and sub-120ms local engine detection.
- **Subsystem 7**: Polyglot Syntax Gate (Python AST, JSON, JS/TS, Markdown, YAML validation).
- **Subsystem 8**: Independent Verifier (Unittest, Pytest, Go test, Cargo test, NPM test).
- **Subsystem 9**: System Therapist for self-healing configuration drift and SQLite maintenance.
- **Subsystem 10**: Task Database (SQLite WAL mode) with transactional audit trail.
- **Subsystem 11**: Memory Vault for continuous cross-session learning and anti-pattern avoidance.
- **Subsystem 12**: Fluid ReAct Execution Engine (Claude Code & Gemini CLI parity with streaming thought).
- **Subsystem 13**: Provider-Native Function Calling Engine (Google Gemini v1beta, Anthropic Claude, OpenAI).
- **Subsystem 14**: Persistent Subshell Engine with working directory tracking (`cd`) and environment persistence.
- **Subsystem 15**: Standalone Binary Packaging Pipeline (`prubeth.exe`, universal `prubeth.pyz`).

## 3. Code Quality & Modification Rules
- Prefer targeted `edit_file` with exact match anchors rather than whole-file overwrites.
- Preserve existing comments, docstrings, and type annotations during refactoring.
- Maintain 100% test passing rate across all unit, ATDD, BDD, SRE, and Fault Injection suites.
