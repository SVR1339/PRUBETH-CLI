# PRUBETH Security Policy & Governance

PRUBETH Autonomous CLI is engineered under the **Zero-Compromise Security Architecture** adhering to the DevSecOps guidelines followed by Tier-1 enterprise organizations (Google, Anthropic, HashiCorp).

---

## 1. Supported Versions

Only the latest active minor release receives official security patches and vulnerability mitigations.

| Version | Supported          | Security Maintenance Tier |
| :------ | :----------------- | :------------------------ |
| 1.0.x   | :white_check_mark: | Active Tier-1 Support     |
| < 1.0.0 | :x:                | Deprecated                |

---

## 2. Reporting a Vulnerability

We prioritize coordinated vulnerability disclosure. If you discover a security vulnerability within the PRUBETH runtime, sandbox boundaries, or memory engine, **do not open a public GitHub issue**.

### Reporting Channel
- **Security Contact**: `security@prubeth.org` (or encrypted communication via repository maintainers)
- **Response SLA**:
  - **Initial Triage & Acknowledgment**: Within 24 hours.
  - **Reproduction & Severity Assessment (CVSS v3.1)**: Within 72 hours.
  - **Patch Release & Security Advisory (CVE)**: Within 7 calendar days.

### What to Include
1. Exact CLI version (`prubeth version` or `prubeth doctor`).
2. Operating system and terminal architecture.
3. Minimal reproducible proof-of-concept (PoC) showing the security boundary breach.
4. Impact assessment (e.g. arbitrary code execution outside sandbox, credential exfiltration, path traversal).

---

## 3. Threat Model & Security Architecture

### 3.1 Path Jail & Sandbox Containment
- The PRUBETH execution engine enforces path validation on all file manipulation tools (`file_write`, `file_edit`, `file_delete`, `patch_apply`).
- Any attempt to escape the working workspace root via directory traversal (`../`, `..\`), symlinks pointing outside the workspace, or absolute paths targeting system directories (`C:\Windows`, `/etc`, `/usr`) is intercepted and rejected with `SecurityViolationError`.

### 3.2 Command Execution Safeguards
- Blacklisted destructive commands (`rm -rf /`, `format`, `dd`, `mkfs`, `del /f /s /q C:\`) are blocked at the AST parsing level.
- Multi-step destructive operations trigger mandatory interactive human authorization (`[y/N]`) unless explicitly bypassed with `--auto` in ephemeral container environments.

### 3.3 Zero-Telemetry Guarantee
- PRUBETH adheres to a **100% Local-First, Zero-Telemetry** policy:
  - **Zero Telemetry**: No anonymous usage metrics, heartbeat pings, or diagnostic telemetry are transmitted.
  - **Zero Code Transmission to Third Parties**: User source code and prompts are sent **exclusively** to the provider explicitly configured by the user (Google Gemini, OpenRouter, or Local Ollama/LM Studio).
  - **Zero Model Retraining**: Neither PRUBETH nor its local engines retain user code for model training.

### 3.4 Credential & Secret Protection
- API keys stored in `~/.prubeth/config.json` or environment variables (`GOOGLE_API_KEY`, `OPENROUTER_API_KEY`) are masked in all console outputs, log files, and `prubeth doctor` reports (e.g., `***zz8g`).
- WAL database (`.prubeth/prubeth.db`) stores encrypted/hashed state metadata and does not write raw credentials to disk.

---

## 4. Coordinated Disclosure & Recognition

Security researchers reporting valid vulnerabilities adhering to this policy will be credited in our public Security Advisories and release notes.
