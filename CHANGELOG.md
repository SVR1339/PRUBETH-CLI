# Changelog

All notable changes to the **PRUBETH Autonomous Developer CLI** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
