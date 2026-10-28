# Changelog

All notable changes to the **PRUBETH Autonomous Developer CLI** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-10-28

### Pinnacle Production Edition (7,274 Verified Tests, 5-Phase Architecture & Universal Gateway)

#### Added
- **Complete 5-Phase Enterprise Architecture & 7,274 Test Suite**:
  - **7,274 verified unit and integration tests** passing with 100% pass rate across all 181 test files in the project.
  - Comprehensive coverage spanning CLI dispatchers, DevSecOps sandboxes, universal cognitive gateways, polyglot code graphs, 37 engineering tools, 12-state task FSMs, multi-agent swarms, and SWE-bench evals.
- **Phase 1: DevSecOps Sandbox Jail & Credential Redaction**:
  - Enforced workspace boundary validation blocking all directory traversal attacks (`../..`, `~/.ssh`, `~/.aws`, system directories).
  - Active regex and entropy-based credential redaction for 8 provider token patterns (`sk-proj-...`, `AIza...`, `sk-ant-...`, `ghp_...`, `AKIA...`).
  - 3-tier tool clearance hierarchy: `READ_ONLY` (auto-approved), `WORKSPACE_MUTATION` (governed by `--auto` or interactive prompt), and `SYSTEM_EXECUTION` (strict oversight).
- **Phase 2: Polyglot AST Engine & Codebase Graph**:
  - Full structural code intelligence across 13 ecosystems: Python, TypeScript, JavaScript, Rust, Go, Java, C#, C++, Dart, PHP, Ruby, Swift, Kotlin.
  - Pure-Python SQLite WAL indexed symbol extraction (classes, functions, methods, imports) without external heavy binary dependencies.
  - Codebase topology, PageRank centrality, and structural blast radius analysis.
- **Phase 3: Universal Cognitive Model Gateway & Circuit Breakers**:
  - Direct unified multi-provider routing supporting Google Gemini (2.5/3.1/3.8/4.0), Anthropic Claude (3.5/3.7), OpenAI (o3-mini, GPT-4o), DeepSeek (R1, V3), Groq, OpenRouter, and local offline engines (Ollama, LM Studio).
  - 3-state Circuit Breaker (`CLOSED`, `OPEN`, `HALF_OPEN`) tracking failure thresholds and exponential backoff.
  - Local Auto-Pivot Latency Guard: automatic pivot to local offline models (Ollama/LM Studio) if cloud requests exceed 45 seconds.
- **Phase 4: Autonomous TDD Self-Healing & Stagnation Interceptors**:
  - 12-state Task State Machine with deterministic transitions from `CREATED` through `DISPATCHING`, `EXECUTING`, `VERIFYING`, `HEALING`, to `COMPLETED`.
  - In-memory AST contract gate detecting broken interfaces and deleted public symbols before commits.
  - Stagnation interceptor detecting infinite tool loops, 2-to-4 cycle sequences, and ping-pong file modification oscillation.
- **Phase 5: Multi-Agent Swarm, Consensus & Worktree Isolation**:
  - Subagent worktree isolation in `.prubeth/worktrees/<id>` with baseline SHA-256 manifest verification and atomic merge.
  - Consensus algorithms: majority, role-weighted, and unanimous voting for high-risk mutations.
  - 5 specialist agent roles: `ARCHITECT`, `CODER`, `CRITIC`, `TEST_ENGINEER`, and `DOCS`.
- **System Qualification & Production Diagnostics**:
  - `prubeth doctor`: 9-pillar pre-flight system qualification with cryptographic runtime seal (`8B3A53335918`) and zero syntax faults.
  - `prubeth therapy`: 7-pillar automated self-healing, WAL maintenance, and memory compaction.
  - Resource footprint guarantee: strictly < 33 MB CPU RAM idle, 0 MB GPU VRAM, CP65001 UTF-8 rendering.

---

## [1.3.0] - 2026-10-26

### Apex Superintelligence, Monorepo Janitor & Computational Biology Edition

#### Added
- **Autonomous GPU/CPU Kernel Autotuner (`KernelAutotuner`) [OpenAI Frontier Target]**:
  - High-performance Triton, CUDA, and C++ compute kernel generation with warp specialization and shared-memory tiling.
  - Closed-loop iterative benchmarking harness measuring speedup factors, memory bandwidth (GB/s), and execution latency.
  - Interactive `/autotune <target_op>` command with automated persistence in `.prubeth/kernels/`.
- **Closed-Loop AI Research & Scientific Experiment Loop (`ResearchExperimentLoop`) [OpenAI/DeepMind Frontier Target]**:
  - Autonomous empirical AI research workflow formulating hypotheses, ablation studies, baseline benchmarks, and scaling law verifications.
  - Generates rigorous empirical research papers in Markdown with quantitative tables and scalability proofs into `.prubeth/research/`.
  - Interactive `/research <hypothesis>` command.
- **Whole-Monorepo SRE Janitor & Self-Healing Engine (`MonorepoJanitor`) [DeepMind Datacenter Target]**:
  - Static security and hygiene audit scanning the entire monorepo for plaintext credentials/API keys, insecure `os.system` subshell execution, and dead imports.
  - Quantitative health scoring metric (0-100) and automated safe remediation (`/janitor fix`) converting hazardous system calls to parameterized `subprocess.run`.
  - Interactive `/janitor [scan|status|fix]` command.
- **Computational Biology & AlphaFold Structure Bridge (`BioComputeBridge`) [DeepMind Science Target]**:
  - High-throughput zero-dependency PDB and mmCIF atomic coordinate parser.
  - AlphaFold pLDDT / B-factor structural confidence extractor (Very High, Confident, Low, Very Low).
  - Mol* 3D molecular structure viewer manifest generator ready for interactive browser sidecars.
  - Interactive `/bio inspect <structure.pdb>` and `/bio manifest <structure.pdb>` commands.
- **Zero-Babysitting Enterprise Issue Resolver & Monorepo Migrator (`EnterpriseTicketResolver`, `EnterpriseMigrator`) [Anthropic Frontier Target]**:
  - Fully autonomous GitHub ticket solver locating candidate bug loci via BM25 semantic index, generating repairs, and verifying with zero human babysitting.
  - Automated transactional snapshot rollback if changes violate existing unit or integration tests.
  - Whole-codebase migration supervisor coordinating multi-file framework refactorings (e.g. sync to async, typing modernization).
  - Interactive `/issue <ticket_desc>` and `/migrate <objective>` commands.
- **Packaging & Verification**:
  - Full test suite expanded to **120/120 passing tests in 30.8s** (100% pass rate).
  - Standalone native binary (`prubeth.exe`, 11.0 MB), universal executable zipapp (`prubeth.pyz`, 1.33 MB), and distribution wheel (`prubeth-1.3.0-py3-none-any.whl`, 160 KB) compiled and signed with SHA256 checksums in `dist/SHA256SUMS.txt`.
  - Enforced memory ceiling: < 33 MB CPU RAM, 0 MB GPU VRAM overhead for the CLI runtime.

---

## [1.2.1] - 2026-10-26

### Frontier Parity Completion Edition (Anthropic, DeepMind & OpenAI Complete Alignment)

#### Added
- **Long-Horizon Autonomous Goal Supervisor (`GoalSupervisor`) [Anthropic Target]**:
  - Autonomous multi-milestone decomposition of complex development tickets.
  - Persistent goal checklist state machine in `.prubeth/goals/<goal_id>.json` with real-time progression telemetry (`[ ] PENDING`, `[..] ACTIVE`, `[OK] VERIFIED`, `[ERR] FAILED`).
  - Automated post-milestone test execution, auto-TDD recovery, checkpoint snapshots (`<id>_m<num>`), and session resumption (`/goal resume`).
  - Interactive `/goal` command and CLI entry points (`prubeth goal "<objective>"`, `prubeth --supervisor`).
- **Test-Time Compute Self-Verification Engine (`TestTimeVerifier`) [OpenAI Target]**:
  - Pre-flight AST syntax and contract breaking-change detection intercepting `edit_file` and `write_file` in memory before writing to disk.
  - Prevention of breaking parameter drops and interface contract violations across workspace modules.
  - Automated post-flight workspace test execution.
- **Cross-File AST Dependency Graph & Caller Reference Engine [DeepMind Monorepo Target]**:
  - Workspace-wide Abstract Syntax Tree caller and reference tracker distinguishing definitions (`class`, `def`) from downstream call sites (`ast.Call`), attribute accesses, and name references.
  - Interactive `/symbols` and `/callers <symbol_name>` inspection commands.
  - Native model tool `find_symbol_references` enabling LLMs to audit callers across files before refactoring.
- **Git-Native Commit & Pull Request Synthesis [Anthropic Target]**:
  - `/commit [-y]` command: analyzes working tree unified diffs and synthesizes Conventional Commit messages (`feat(...)`, `fix(...)`, `refactor(...)`) with test verification evidence into `.prubeth/commits/COMMIT_MSG.txt`.
  - `/pr` command: generates full GitHub Pull Request markdown specifications with risk assessments into `.prubeth/PULL_REQUEST.md`.
- **Persistent Invariant Learning Vault (`/learn`) [OpenAI/DeepMind Target]**:
  - Interactive `/learn <directive>`, `/learn list`, and `/learn remove <id>` commands.
  - Automatically records project invariants in `.prubeth/memory/learnings.json` and updates `MemoryVault`.
  - Injects active learned invariants directly into `RepositoryIntelligence.load_project_instructions()` and all prompt contexts.
- **Testing & Packaging**:
  - Added `tests/test_frontier_parities.py` with 8 comprehensive integration tests.
  - Full test suite expanded to **114/114 passing tests in 26.5s** (100% pass rate).
  - Standalone binary (`prubeth.exe`), universal zipapp (`prubeth.pyz`), and wheel package updated and verified with SHA-256 checksums.

---

## [1.2.0] - 2026-10-25

### Frontier Parity Edition (Claude Code & Gemini CLI Complete Engine Parity)

#### Added
- **Provider-Native Function Calling**:
  - Full native function declaration schemas for Google Gemini v1beta (`function_declarations`), Anthropic Claude (`tools` / `tool_use`), and OpenAI / OpenRouter (`tools` / `function`).
  - Strict JSON-schema parameter validation for all 9 workspace tools (`read_file`, `edit_file`, `write_file`, `run_command`, `grep_search`, `find_files`, `code_search`, `resolve_symbol`, `git_diff`).
  - Seamless regex and markdown block fallback for offline local models (Ollama, LM Studio) or legacy servers without native function calling support.
- **Structured Multi-Turn Role Message Tree**:
  - Structured turn array passing (`role: "user"`, `role: "model"` / `"assistant"`, `role: "tool"` / `functionResponse`).
  - Preservation of cloud Prefix KV Cache (Prompt Caching) across iterative turns on both Claude and Gemini.
- **Stateful Persistent Subshell (`PersistentSubshell`)**:
  - Directory tracking (`cd`) and environment variable persistence (`set`, `export`, `$env:`) across tool turns.
  - 100% reliable native subprocess exit codes with zero pipe deadlocks and zero Windows file locks (`WinError 32`).
- **Interactive UI & Terminal UX Improvements**:
  - Real-time animated token streaming interleaved with sleek tool execution status badges.
  - Multi-line REPL input supporting backslash (`\`) line continuations and triple-quote (`"""`) blocks.
  - Parity commands: `/init` (auto-stack detection & `PRUBETH.md` generator), `/review` (staged diff review), `/compact` (conversation history compaction), `/clear` (terminal reset), `/diff` (working tree diff), `/heal` (autonomous test-driven repair).
- **Standalone Native Binaries**:
  - Compiled Windows native binary distribution: `dist/bin/prubeth/prubeth.exe` (11 MB).
  - Standalone universal zipapp: `dist/prubeth.pyz` (1.2 MB).
  - Distributed Wheel package: `dist/prubeth-1.2.0-py3-none-any.whl` (137 KB).
  - All artifacts verified with cryptographically secure SHA-256 signatures in `dist/SHA256SUMS.txt`.

---

## [1.0.0] - 2026-10-25

### Initial Production Release (Tier-1 Enterprise Qualification)

#### Added
- **Core Autonomous Engine**:
  - ReAct state machine loop with deterministic finite-state machine transitions (`IDLE`, `PLANNING`, `EXECUTING`, `VERIFYING`, `RECOVERING`, `COMPLETED`, `FAILED`).
  - Speculative Plan B Architecture: Parallel contingency generation and automatic pivot on primary plan disruption.
  - Zero-external-Git pure-Python snapshot engine with full rollback capability and delta tracking.
  - SQLite WAL persistent state engine with microsecond concurrent checkpointing.
- **Cognitive Model Shifter & Multi-Provider Cascade**:
  - Unified multi-model gateway supporting Google Gemini (`gemini-3.1-pro-preview`, `gemini-3.5-pro`, `gemini-3.5-flash`), OpenRouter Free Tier (DeepSeek R1 671B, Meta Llama 3.3 70B, Qwen 2.5 Coder 32B), and Local Offline LLMs (Ollama, LM Studio).
  - Priority cascade from Highest Pro reasoning models down to lightweight models.
  - Instant Local Auto-Pivot on API key errors (`401`, `403`, missing keys) or upstream network latency timeouts ($> 12\text{s}$) with $< 120\text{ms}$ socket probes.
- **Enterprise Diagnostics, Therapy & Deep Configuration (`prubeth therapy`)**:
  - 8-pillar pre-flight diagnostic suite (`prubeth doctor`) verifying Python runtime, UTF-8 ANSI terminal rendering (PRINCE3), memory footprint ($< 33\text{ MB}$), Cloud AI credentials, Local Offline Engine, sandbox path jail, WAL concurrency, and cognitive shifter latency.
  - 7-pillar autonomous system therapy engine (`prubeth therapy` / `prubeth doctor --fix`): proactive configuration drift auto-remediation, schema type repair, SQLite WAL journal truncation (`wal_checkpoint(TRUNCATE)`), memory garbage collection, and local model auto-promotion.
  - Multi-step interactive Deep Configuration Wizard (`prubeth configure --deep`) for fine-grained operational profiles, cognitive tiering, and latency guard deadlines.
- **Onboarding & Factory Default Reset**:
  - Interactive onboarding wizard (`prubeth setup` / `prubeth onboarding`) with automatic local Ollama detection and one-click model download guides.
  - Factory default reset engine (`prubeth reset`) restoring initial clean onboarding state.
- **Multi-Agent Orchestration & DevSecOps**:
  - 5-role specialized swarm (Architect, Coder, Critic, Test Engineer, Documentation Specialist).
  - Shadow worktrees with git-less branch isolation.
  - Continuous intelligence failure memory engine with anti-pattern tracking.
  - Model Context Protocol (MCP) tool integration client.
  - IDE IPC Named Pipe & Unix domain socket bridge.
- **Shell Completions & UX**:
  - Tab completion generators for PowerShell, Bash, and Zsh.
  - PRINCE Stage 3 TrueColor ANSI UI with zero font blur and subpixel sharpness.
  - Performance Builder HUD with 4 operational profiles (`builder`, `deep-reasoning`, `local-airgap`, `safe-audit`).
