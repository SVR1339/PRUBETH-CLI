# Contributing to PRUBETH Autonomous Developer CLI

Thank you for your interest in contributing to **PRUBETH**! PRUBETH is an elite, multi-model autonomous software engineering runtime engineered to Tier-1 industry standards.

---

## 1. Development Principles & Core Invariants

All contributions must strictly respect PRUBETH's foundational architectural invariants:

1. **Memory & Resource Boundary**:
   - Pure-Python orchestration footprint must remain **$< 33\text{ MB}$ CPU RAM**.
   - **$0\text{ MB}$ GPU VRAM reservation** by the orchestrator runtime.
2. **Zero External Git Binary Dependency**:
   - PRUBETH's snapshotting, shadow worktrees, and rollback mechanisms are 100% self-contained in pure Python. No external `git.exe` or git package may be added as a mandatory prerequisite.
3. **Multi-Model Neutrality & Zero Lock-In**:
   - Core runtime logic must never bind exclusively to a single vendor. Provider adapters must remain decoupled.
4. **Resilience Invariant (Plan B Always Armed)**:
   - Destructive modifications must always capture pre-execution snapshots. Failure states must automatically invoke rollback or Plan B contingency cascades.
5. **Zero Font Blur & Terminal Standard**:
   - Terminal output must adhere to PRINCE Stage 3 standards (Code Page 65001 / UTF-8 ANSI, no subpixel blur, no truncation).

---

## 2. Setting Up Your Development Environment

### Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13.
- Standard terminal with UTF-8 support (Windows Terminal, iTerm2, Alacritty, GNOME Terminal).

### Setup Steps
```bash
# 1. Clone the repository
git clone https://github.com/prubeth-org/prubeth.git
cd prubeth

# 2. Create and activate a virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 3. Install in editable mode with development dependencies
pip install --upgrade pip
pip install -e .
pip install pytest pyinstaller rich
```

---

## 3. Running the Test & Diagnostic Suite

PRUBETH requires 100% pass rates across all qualification pillars before any commit or PR can be merged.

```bash
# 1. Run the system qualification doctor
prubeth doctor

# 2. Run the complete automated test suite
python -m unittest discover -s tests -p "test_*.py" -v

# 3. Verify CLI subcommands and completions
prubeth --help
prubeth settings
prubeth swarm roles
prubeth consensus
prubeth mcp list
prubeth completion powershell
```

---

## 4. Coding Standards & Conventions

- **Typing**: Use static type annotations (`typing.Dict`, `typing.List`, `typing.Optional`, etc.) across all function definitions.
- **Error Handling**: Never catch bare `Exception` without re-raising or logging structured context. System errors must cleanly surface via the event logger.
- **Socket Safety**: Network probes (e.g. for local models or IPC bridge) must always utilize context managers (`with socket.socket(...) as s:`) to avoid socket leaks on Windows.
- **Commit Messages**: Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
  - `feat(models): add automatic latency fallback threshold`
  - `fix(cli): resolve socket descriptor leak in doctor check`
  - `docs(readme): update local AI download instructions`
  - `test(runtime): add test case for factory default reset`

---

## 5. Submitting a Pull Request (PR)

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Implement your changes following all architectural invariants.
3. Add unit tests in the `tests/` directory verifying new behavior.
4. Ensure all existing tests pass (`python -m unittest discover -s tests -p "test_*.py"`).
5. Open a Pull Request referencing the issue number with a clear description of the change, reproduction steps, and `prubeth doctor` verification output.
