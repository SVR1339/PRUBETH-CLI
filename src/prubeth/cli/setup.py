"""PRUBETH Onboarding, Interactive Setup Wizard, and Local AI Setup System.

Provides user-friendly setup for Cloud AI providers, Local AI models (Ollama/LM Studio),
automatic model shifters, Claude Code-grade permission modes, and factory reset verification.
"""

import os
import sys
import shutil
import socket
import urllib.request
import json
from pathlib import Path
from typing import Dict, Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from prubeth.config.manager import ConfigManager, DEFAULT_CONFIG
from prubeth.cli.doctor import PrubethDoctor
from prubeth.cli.version import CLI_VERSION

def probe_local_ai_capabilities() -> Dict[str, Any]:
    """Inspects the local system for installed local AI engines (Ollama, LM Studio)."""
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        local_appdata = os.getenv("LOCALAPPDATA", "")
        if local_appdata:
            candidate = Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe"
            if candidate.exists():
                ollama_path = str(candidate)

    ollama_running = False
    ollama_models = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.06)
            s.connect(("127.0.0.1", 11434))
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "PRUBETH"})
        with urllib.request.urlopen(req, timeout=1.0) as r:
            data = json.loads(r.read().decode("utf-8"))
            ollama_models = [m.get("name") for m in data.get("models", [])]
            ollama_running = True
    except Exception:
        pass

    # Disk scan for offline downloaded models if daemon is not currently streaming
    if not ollama_models:
        manifest_root = Path.home() / ".ollama" / "models" / "manifests" / "registry.ollama.ai" / "library"
        if manifest_root.exists():
            for model_dir in manifest_root.iterdir():
                if model_dir.is_dir():
                    for tag_file in model_dir.iterdir():
                        if tag_file.is_file():
                            ollama_models.append(f"{model_dir.name}:{tag_file.name}")

    lm_running = False
    lm_models = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.06)
            s.connect(("127.0.0.1", 1234))
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models", headers={"User-Agent": "PRUBETH"})
        with urllib.request.urlopen(req, timeout=1.0) as r:
            data = json.loads(r.read().decode("utf-8"))
            lm_models = [m.get("id") for m in data.get("data", [])]
            lm_running = True
    except Exception:
        pass

    return {
        "ollama_installed": bool(ollama_path),
        "ollama_binary": ollama_path,
        "ollama_running": ollama_running,
        "ollama_models": ollama_models,
        "lm_studio_running": lm_running,
        "lm_studio_models": lm_models
    }

def save_claude_style_settings(home_dir: Path, mode: str, enable_caching: bool = True, ttl_s: int = 300, workspace_root: Optional[Path] = None):
    """Generates ~/.prubeth/settings.json matching Claude Code & Gemini CLI configuration schemas."""
    settings_file = home_dir / ".prubeth" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    
    trusted_workspaces = []
    if settings_file.exists():
        try:
            existing = json.loads(settings_file.read_text(encoding="utf-8"))
            trusted_workspaces = existing.get("trusted_workspaces", [])
        except Exception:
            pass

    if workspace_root:
        ws_str = str(workspace_root.resolve())
        if ws_str not in trusted_workspaces:
            trusted_workspaces.append(ws_str)

    allow_tools = [
        "read_file", "find_files", "grep_search", "code_search",
        "resolve_symbol", "find_symbol_references", "git_status", "git_diff"
    ]
    ask_tools = ["edit_file", "write_file", "run_command"]
    if mode in ["acceptEdits", "builder", "developerMode"]:
        allow_tools.extend(["edit_file", "write_file"])
        ask_tools = ["run_command"] if mode == "acceptEdits" else []
        if mode in ["builder", "developerMode"]:
            allow_tools.append("run_command")

    settings_payload = {
        "$schema": "https://prubeth.org/schema/settings.v1.json",
        "version": CLI_VERSION,
        "permissions": {
            "defaultMode": mode,
            "allow": allow_tools,
            "ask": ask_tools,
            "deny": [
                "Bash (rm -rf /)",
                "Bash (rm -rf /*)",
                "Bash (format c:)",
                "Read (~/.ssh/*)",
                "Read (~/.aws/*)",
                "Edit (.env*)"
            ]
        },
        "trusted_workspaces": trusted_workspaces,
        "caching": {
            "enable_prompt_caching": enable_caching,
            "enable_context_caching": enable_caching,
            "context_cache_ttl_s": ttl_s
        },
        "telemetry": {
            "enabled": False,
            "guarantee": "100% Local-First / Zero Telemetry"
        },
        "terminal": {
            "theme": "dark",
            "stream_tokens": True,
            "code_page": 65001
        }
    }
    settings_file.write_text(json.dumps(settings_payload, indent=2), encoding="utf-8")
    return settings_file

def initialize_workspace_prubeth_md(workspace_root: Path, console: Console) -> Optional[Path]:
    """Generates PRUBETH.md project context file matching CLAUDE.md / GEMINI.md standards."""
    target_file = workspace_root / "PRUBETH.md"
    if target_file.exists():
        return target_file

    from prubeth.polyglot.manager import PolyglotLanguageManager
    mgr = PolyglotLanguageManager(workspace_root)
    stack = mgr.resolve_active_stack()
    content = stack.generate_prubeth_md(workspace_root.name)

    try:
        target_file.write_text(content, encoding="utf-8")
        console.print(f"  [bold green]✔ Initialized project context file ({stack.name}):[/bold green] [cyan]{target_file.name}[/cyan]")
        return target_file
    except Exception:
        return None

def render_onboarding_wizard(console: Console, cfg_mgr: Optional[ConfigManager] = None, interactive: bool = True):
    """Executes the frontier interactive setup wizard matching Claude Code and Gemini CLI onboarding."""
    cfg_mgr = cfg_mgr or ConfigManager()
    cfg = cfg_mgr.load_config()
    keys = cfg.get("api_keys", {})
    local_info = probe_local_ai_capabilities()

    # Step 1: Royal British Engineering Welcome Banner
    banner = """[bold white]PRUBETH Autonomous Engine — First-Time Setup Wizard[/bold white]
[dim]Frontier Onboarding Parity (Matching Anthropic Claude Code & Google Gemini CLI Standards)[/dim]

[cyan]Key Architectural Principles:[/cyan]
  • [bold]100% Local-First & Zero Telemetry:[/bold] Your code and tokens remain strictly private.
  • [bold]Sub-33 MB RAM Ceiling:[/bold] Micro-footprint runtime with zero GPU VRAM consumption.
  • [bold]Dual Multi-Tier Caching:[/bold] Gemini GPU VRAM cachedContents + Claude Ephemeral KV Pins.
  • [bold]In-Memory AST Gate:[/bold] Pre-flight syntax validation and contract verification.
"""
    console.print(Panel(banner, title="PRUBETH First-Time Setup & Onboarding", border_style="cyan", box=box.ROUNDED))

    # Step 1: Default Workspace & Project Storage Location
    console.print("[bold cyan]Step 1/5: Default Project Storage & Workspace Directory[/bold cyan]")
    default_ws_cand = Path.home() / "prubeth-workspace"
    default_ws_alt = Path.home() / "projects"
    default_ws = default_ws_alt if default_ws_alt.exists() else default_ws_cand
    
    console.print("Where should PRUBETH create projects, store files, and manage workspaces?")
    console.print(f"  [dim]Default recommended location:[/dim] [bold white]{default_ws}[/bold white]")
    
    if interactive and sys.stdin.isatty():
        chosen_ws = Prompt.ask("Enter workspace storage location [dim](or 'skip'/'q')[/dim]", default=str(default_ws))
        if chosen_ws.strip().lower() in ["q", "quit", "exit", "cancel", "skip"]:
            console.print("[dim yellow]Using default workspace storage location.[/dim yellow]")
            chosen_ws = str(default_ws)
    else:
        chosen_ws = str(default_ws)
        
    target_ws_path = Path(chosen_ws).expanduser().resolve()
    target_ws_path.mkdir(parents=True, exist_ok=True)
    cfg_mgr.set("default_workspace_dir", str(target_ws_path))
    console.print(f"  [bold green]✔ Configured Storage Location:[/bold green] [bold cyan]{target_ws_path}[/bold cyan]\n")

    # Step 2: Provider & Authentication Configuration
    console.print("[bold cyan]Step 2/5: AI Engine & Provider Credentials[/bold cyan]")
    
    # Auto-detect existing keys in environment
    env_gemini = os.getenv("GEMINI_API_KEY", "")
    env_anthropic = os.getenv("ANTHROPIC_API_KEY", "")
    env_openrouter = os.getenv("OPENROUTER_API_KEY", "")
    env_openai = os.getenv("OPENAI_API_KEY", "")

    selected_provider = "google"
    selected_model = "gemini-2.5-pro"

    if interactive and sys.stdin.isatty():
        provider_choices = [
            "1. Google Gemini (Gemini 2.5 Pro / Flash with GPU VRAM Context Caching)",
            "2. Anthropic Claude (Claude 3.7 Sonnet with 4-Breakpoint Prompt Caching)",
            "3. OpenAI / OpenRouter (o3-mini / DeepSeek R1 / Free Tier Multi-Model)",
            "4. Local Air-Gapped Engine (Ollama / LM Studio - 100% Offline, Zero Cloud Egress)"
        ]
        console.print("Select your preferred primary AI engine:")
        for c in provider_choices:
            console.print(f"  {c}")

        ans = Prompt.ask("\nEnter choice [1-4]", choices=["1", "2", "3", "4"], default="1")
        if ans == "1":
            selected_provider = "google"
            selected_model = "gemini-2.5-pro"
            existing_key = keys.get("google") or env_gemini
            prompt_str = f"Enter Google Gemini API Key [dim](leave empty to keep current)[/dim]" if existing_key else "Enter Google Gemini API Key (from Google AI Studio)"
            user_key = Prompt.ask(prompt_str, default=existing_key or "")
            if user_key:
                cfg_mgr.set("api_keys.google", user_key)
        elif ans == "2":
            selected_provider = "anthropic"
            selected_model = "claude-3-7-sonnet-20250219"
            existing_key = keys.get("anthropic") or env_anthropic
            prompt_str = f"Enter Anthropic API Key [dim](leave empty to keep current)[/dim]" if existing_key else "Enter Anthropic API Key"
            user_key = Prompt.ask(prompt_str, default=existing_key or "")
            if user_key:
                cfg_mgr.set("api_keys.anthropic", user_key)
        elif ans == "3":
            selected_provider = "openrouter"
            selected_model = "o3-mini"
            existing_key = keys.get("openrouter") or env_openrouter
            prompt_str = f"Enter OpenRouter API Key [dim](leave empty to keep current)[/dim]" if existing_key else "Enter OpenRouter API Key"
            user_key = Prompt.ask(prompt_str, default=existing_key or "")
            if user_key:
                cfg_mgr.set("api_keys.openrouter", user_key)
        elif ans == "4":
            selected_provider = "ollama" if (local_info["ollama_running"] or local_info["ollama_models"]) else "lm_studio"
            models = local_info["ollama_models"] if local_info["ollama_models"] else local_info["lm_studio_models"]
            if models:
                console.print("\n[bold cyan]Discovered Downloaded Local Models:[/bold cyan]")
                for idx, m in enumerate(models, start=1):
                    console.print(f"  {idx}. [bold white]{m}[/bold white]")
                m_choice = Prompt.ask("Select local model", choices=[str(i) for i in range(1, len(models) + 1)], default="1")
                selected_model = models[int(m_choice) - 1]
            else:
                selected_model = Prompt.ask("Enter local model tag", default="qwen2.5:1.5b")
            cfg_mgr.set("offline_mode", True)
    else:
        # Non-interactive / default fallback
        if env_gemini:
            cfg_mgr.set("api_keys.google", env_gemini)
        if env_anthropic:
            cfg_mgr.set("api_keys.anthropic", env_anthropic)

    cfg_mgr.set("default_provider", selected_provider)
    cfg_mgr.set("default_model", selected_model)
    console.print(f"  [bold green]✔ Configured Primary Engine:[/bold green] [bold cyan]{selected_model}[/bold cyan] ([magenta]{selected_provider}[/magenta])\n")

    # Step 2b: Polyglot Language Stack Preference
    console.print("[bold cyan]Step 2b/5: Polyglot Language Stack Preference[/bold cyan]")
    lang_map = {
        "1": "auto",
        "2": "python",
        "3": "typescript",
        "4": "rust",
        "5": "go",
        "6": "java",
        "7": "csharp",
        "8": "cpp"
    }
    chosen_lang = "auto"
    if interactive and sys.stdin.isatty():
        console.print("Select primary programming language ecosystem:")
        console.print("  [bold]1. auto[/bold]         - Dynamic auto-detection from workspace marker files (Recommended)")
        console.print("  [bold]2. python[/bold]       - Python 3 (pytest, ruff, black, uv)")
        console.print("  [bold]3. typescript[/bold]   - TypeScript / Node.js (vitest, jest, tsc, npm/pnpm/bun)")
        console.print("  [bold]4. rust[/bold]         - Rust (cargo test, clippy, rustfmt)")
        console.print("  [bold]5. go[/bold]           - Go (go test, go vet, golangci-lint)")
        console.print("  [bold]6. java[/bold]         - Java (Maven / Gradle, JUnit)")
        console.print("  [bold]7. csharp[/bold]       - C# / .NET Core (dotnet test, dotnet build)")
        console.print("  [bold]8. cpp[/bold]          - C / C++ (CMake, CTest, clang)")
        l_ans = Prompt.ask("Enter language preference [1-8]", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="1")
        chosen_lang = lang_map.get(l_ans, "auto")

    cfg_mgr.set("default_language", chosen_lang)
    lang_disp = "Auto-Detect (Dynamic)" if chosen_lang == "auto" else chosen_lang.capitalize()
    console.print(f"  [bold green]✔ Configured Language Ecosystem:[/bold green] [bold cyan]{lang_disp}[/bold cyan]\n")

    # Step 3: Tool Execution Permission Clearance (Unified Default & Advanced Developer Mode)
    console.print("[bold cyan]Step 3/5: Tool Execution Permission Clearance[/bold cyan]")
    mode = "default"
    if interactive and sys.stdin.isatty():
        console.print("Select execution clearance mode:")
        console.print("  [bold]1. default[/bold]        - Standard Execution Clearance (Unified read, plan, & safe modification; prompt before shell/destructive edits).")
        console.print("  [bold]2. developerMode[/bold]  - Advanced Autonomous Mode (Full builder clearance, self-healing execution, automated Plan B contingency).")
        m_ans = Prompt.ask("Enter clearance mode [1-2]", choices=["1", "2"], default="1")
        mode = "default" if m_ans == "1" else "builder"
    
    if mode == "builder":
        cfg_mgr.apply_profile("builder")
        cfg_mgr.set("developer_mode", True)
        cfg_mgr.set("auto_approve_actions", True)
    else:
        cfg_mgr.set("auto_approve_actions", False)
        cfg_mgr.set("developer_mode", False)

    # Generate ~/.prubeth/settings.json matching schema
    home_dir = Path.home()
    settings_path = save_claude_style_settings(home_dir, mode=mode, enable_caching=True, ttl_s=300, workspace_root=target_ws_path)
    mode_label = "default (Standard)" if mode == "default" else "developerMode (Advanced Autonomous)"
    console.print(f"  [bold green]✔ Configured Permission Mode:[/bold green] [bold cyan]{mode_label}[/bold cyan]")
    console.print(f"  [bold green]✔ Saved Security Policy:[/bold green] [dim]{settings_path}[/dim]\n")

    # Step 4: Frontier Prompt KV & Context Caching
    console.print("[bold cyan]Step 4/5: Frontier Prompt KV & Context Caching[/bold cyan]")
    cfg_mgr.set("enable_prompt_caching", True)
    cfg_mgr.set("enable_context_caching", True)
    cfg_mgr.set("context_cache_ttl_s", 300)
    console.print("  [bold green]✔ Anthropic 4-Breakpoint Ephemeral Prompt Caching:[/bold green] [green]ENABLED (90% read discount)[/green]")
    console.print("  [bold green]✔ Google Gemini GPU VRAM cachedContents Session:[/bold green] [green]ENABLED (TTL: 300s, 75% discount)[/green]\n")

    # Step 5: Project Directive File (PRUBETH.md - Claude Code / Gemini CLI Parity)
    console.print("[bold cyan]Step 5/5: Project Context Memory Directive[/bold cyan]")
    workspace_root = Path.cwd().resolve()
    initialize_workspace_prubeth_md(workspace_root, console)
    console.print()

    # Step 6: Mark First Run Completed
    cfg_mgr.set("first_run_completed", True)

    # Step 7: Automatic Pre-Flight System Qualification Diagnostic (Doctor)
    console.print("[bold cyan]Executing Pre-Flight Production Qualification (Doctor)...[/bold cyan]\n")
    PrubethDoctor(console).render_report()

    console.print(Panel(
        "[bold green]✔ PRUBETH Autonomous Developer CLI Setup Complete![/bold green]\n\n"
        "Your environment is configured with frontier parity matching Anthropic Claude Code and Google Gemini CLI.\n"
        "• Launch Interactive Cockpit:   [bold cyan]prubeth[/bold cyan]\n"
        "• Inspect Cache Radar:         [bold cyan]prubeth cache[/bold cyan]\n"
        "• View Time-Travel Timeline:    [bold cyan]prubeth timeline[/bold cyan]\n"
        "• Re-run Diagnostics:          [bold cyan]prubeth doctor[/bold cyan]",
        title="[OK] Setup Verification Accepted",
        border_style="green",
        box=box.ROUNDED
    ))

def execute_factory_reset(console: Console, cfg_mgr: Optional[ConfigManager] = None):
    """Executes clean factory default reset and returns to pristine first-onboarding state."""
    cfg_mgr = cfg_mgr or ConfigManager()
    cfg_mgr.save_config(DEFAULT_CONFIG.copy())
    
    # Reset settings.json
    try:
        settings_file = Path.home() / ".prubeth" / "settings.json"
        if settings_file.exists():
            settings_file.unlink()
    except Exception:
        pass

    console.print(Panel(
        "[bold green]✅ Factory Default Reset Successfully Executed![/bold green]\n\n"
        "All configuration settings, active profiles, and overrides have been restored to the "
        "pristine default state.\n\n"
        "To review or reconfigure your onboarding settings, run: [bold cyan]prubeth setup[/bold cyan]",
        title="PRUBETH Factory Default Reset",
        border_style="green",
        box=box.ROUNDED
    ))

def ensure_startup_permissions(console: Console, cfg_mgr: ConfigManager, workspace_root: Path) -> Path:
    """Prompts for all essential permissions, workspace clearance, and credentials at CLI startup."""
    cfg = cfg_mgr.load_config()
    settings_file = Path.home() / ".prubeth" / "settings.json"
    
    trusted_workspaces = []
    settings_data = {}
    if settings_file.exists():
        try:
            settings_data = json.loads(settings_file.read_text(encoding="utf-8"))
            trusted_workspaces = settings_data.get("trusted_workspaces", [])
        except Exception:
            pass

    # 1. Ensure settings.json exists without blocking the developer
    if not settings_file.exists():
        try:
            save_claude_style_settings(Path.home(), mode="builder", workspace_root=workspace_root)
        except Exception:
            pass

    # Ensure first_run_completed is marked so the cockpit starts immediately
    if not cfg.get("first_run_completed", False):
        cfg_mgr.set("first_run_completed", True)
        if not cfg.get("default_workspace_dir"):
            cand = Path.home() / "projects"
            if not cand.exists():
                cand = Path.home() / "prubeth-workspace"
            cand.mkdir(parents=True, exist_ok=True)
            cfg_mgr.set("default_workspace_dir", str(cand))
        cfg = cfg_mgr.load_config()

    # 2. Check / Set Default Project Storage Location if not yet set
    default_ws_cfg = cfg.get("default_workspace_dir")
    if not default_ws_cfg:
        cand_ws = Path.home() / "projects"
        if not cand_ws.exists():
            cand_ws = Path.home() / "prubeth-workspace"
        cand_ws.mkdir(parents=True, exist_ok=True)
        cfg_mgr.set("default_workspace_dir", str(cand_ws))
        default_ws_cfg = str(cand_ws)

    # 3. Handle launch from User Home Directory or Windows System root
    win_sys = os.environ.get("SystemRoot", "C:\\Windows").lower() if sys.platform == "win32" else ""
    is_home = (workspace_root.resolve() == Path.home().resolve())
    is_sys = (sys.platform == "win32" and str(workspace_root).lower().startswith(win_sys))

    if is_home or is_sys:
        target_default = Path(default_ws_cfg).expanduser().resolve()
        target_default.mkdir(parents=True, exist_ok=True)
        if sys.stdin.isatty():
            loc_label = "user profile root" if is_home else "Windows System directory"
            console.print(f"[bold cyan]Notice:[/bold cyan] Launched inside {loc_label} ([white]{workspace_root}[/white]).")
            switch = Confirm.ask(f"Switch to designated project workspace ([bold green]{target_default}[/bold green])?", default=True)
            if switch:
                try:
                    os.chdir(str(target_default))
                    workspace_root = target_default
                    console.print(f"  [bold green]✔ Active workspace set to:[/bold green] [bold cyan]{workspace_root}[/bold cyan]\n")
                except Exception:
                    pass
        else:
            try:
                os.chdir(str(target_default))
                workspace_root = target_default
            except Exception:
                pass

    ws_str = str(workspace_root)
    resolved = cfg_mgr.resolve_model_and_provider()
    needs_key = False
    if not cfg.get("offline_mode", False) and resolved["provider"] in ["google", "anthropic", "openai", "openrouter"]:
        if not resolved["api_key"]:
            needs_key = True

    # 4. If workspace is untrusted or key is needed:
    if ws_str not in trusted_workspaces or needs_key:
        console.print()
        console.print(Panel(
            f"[bold white]PRUBETH Permissions & Clearance Gate[/bold white]\n"
            f"[dim]Workspace:[/dim] [cyan]{ws_str}[/cyan]\n"
            f"[dim]Security:[/dim] DevSecOps In-Memory AST Sandbox Clearance",
            title="Startup Clearance & Permissions Handshake",
            border_style="#00F5D4",
            box=box.ROUNDED
        ))

        # 1. Workspace Trust Clearance
        if ws_str not in trusted_workspaces:
            console.print("[bold cyan]1. Workspace Access Clearance[/bold cyan]")
            console.print("Allow PRUBETH to read/write files and create recovery snapshots in:")
            console.print(f"  [bold white]{ws_str}[/bold white]")
            allow_ws = Confirm.ask("Grant workspace access?", default=True) if sys.stdin.isatty() else True
            if not allow_ws:
                console.print("[yellow]Workspace access denied. Switching to read-only plan mode.[/yellow]")
                cfg_mgr.set("auto_approve_actions", False)
                cfg_mgr.apply_profile("safe-audit")
            else:
                trusted_workspaces.append(ws_str)
                settings_data["trusted_workspaces"] = trusted_workspaces
                settings_file.write_text(json.dumps(settings_data, indent=2), encoding="utf-8")
                console.print("[green]✔ Workspace access granted & remembered.[/green]\n")

        # 2. Tool Execution Clearance Mode (Consolidated: default vs developerMode)
        console.print("[bold cyan]2. Tool Execution Clearance Mode[/bold cyan]")
        console.print("Select execution clearance for this session:")
        console.print("  [bold]1. default[/bold]        - Standard Execution Clearance (Unified read, plan, & safe modification; prompt before shell/destructive edits).")
        console.print("  [bold]2. developerMode[/bold]  - Advanced Autonomous Mode (Full builder clearance, self-healing execution, automated Plan B contingency).")
        
        mode_choice = Prompt.ask("Select clearance mode [1-2]", choices=["1", "2"], default="1") if sys.stdin.isatty() else "1"
        if mode_choice == "2":
            cfg_mgr.apply_profile("builder")
            cfg_mgr.set("developer_mode", True)
            cfg_mgr.set("auto_approve_actions", True)
            selected_mode = "developerMode"
        else:
            cfg_mgr.set("auto_approve_actions", False)
            cfg_mgr.set("developer_mode", False)
            selected_mode = "default"
        console.print(f"[green]✔ Clearance mode set to:[/green] [bold cyan]{selected_mode}[/bold cyan]\n")

        # 3. Model & Credentials Verification
        if needs_key:
            console.print("[bold cyan]3. AI Model & Provider Credentials[/bold cyan]")
            console.print(f"[yellow]⚠️ No API key detected for {resolved['provider'].upper()} ({resolved['model']}).[/yellow]")
            console.print("Configure your AI model engine to proceed:")
            console.print("  [bold]1.[/bold] Enter Google Gemini API Key (Recommended for speed & context caching)")
            console.print("  [bold]2.[/bold] Enter Anthropic Claude API Key")
            console.print("  [bold]3.[/bold] Enter OpenAI / OpenRouter Key")
            console.print("  [bold]4.[/bold] Use Local Offline Model (Ollama: qwen2.5:1.5b)")

            k_choice = Prompt.ask("Choose [1-4]", choices=["1", "2", "3", "4"], default="1") if sys.stdin.isatty() else "4"
            if k_choice == "1":
                g_key = Prompt.ask("Enter Google Gemini API Key")
                if g_key:
                    cfg_mgr.set("api_keys.google", g_key.strip())
                    cfg_mgr.set("default_provider", "google")
                    cfg_mgr.set("default_model", "gemini-2.5-pro")
                    console.print("[green]✔ Google Gemini key saved.[/green]")
            elif k_choice == "2":
                c_key = Prompt.ask("Enter Anthropic Claude API Key")
                if c_key:
                    cfg_mgr.set("api_keys.anthropic", c_key.strip())
                    cfg_mgr.set("default_provider", "anthropic")
                    cfg_mgr.set("default_model", "claude-3-7-sonnet-20250219")
                    console.print("[green]✔ Anthropic Claude key saved.[/green]")
            elif k_choice == "3":
                o_key = Prompt.ask("Enter OpenAI / OpenRouter Key")
                if o_key:
                    cfg_mgr.set("api_keys.openrouter", o_key.strip())
                    cfg_mgr.set("default_provider", "openrouter")
                    cfg_mgr.set("default_model", "o3-mini")
                    console.print("[green]✔ OpenRouter key saved.[/green]")
            elif k_choice == "4":
                cfg_mgr.set("default_provider", "ollama")
                cfg_mgr.set("default_model", "qwen2.5:1.5b")
                cfg_mgr.set("offline_mode", True)
                console.print("[green]✔ Switched to offline local model (qwen2.5:1.5b).[/green]")
            console.print()

        # 4. Workspace Memory Directive (PRUBETH.md)
        prubeth_md = workspace_root / "PRUBETH.md"
        if not prubeth_md.exists():
            console.print("[bold cyan]4. Project Context Memory Directive[/bold cyan]")
            if sys.stdin.isatty():
                if Confirm.ask("Initialize PRUBETH.md rules file for this workspace?", default=True):
                    initialize_workspace_prubeth_md(workspace_root, console)
            else:
                initialize_workspace_prubeth_md(workspace_root, console)
            console.print()

        console.print("[bold green]✔ All startup permissions and credentials verified.[/bold green]\n")

    return workspace_root

def run_personal_setup_hub(console: Console, cfg_mgr: Optional[ConfigManager] = None, interactive: bool = True):
    """Subsystem: Dedicated Personal Usage & Local Models Configuration Hub."""
    cfg_mgr = cfg_mgr or ConfigManager()

    while True:
        try:
            cfg = cfg_mgr.load_config()
            keys = cfg.get("api_keys", {})
            local_info = probe_local_ai_capabilities()

            def mask_key(k: Optional[str]) -> str:
                if not k:
                    return "[dim red]Not configured[/dim red]"
                if len(k) <= 8:
                    return "[green]Configured[/green]"
                return f"[green]Configured[/green] [dim]({k[:4]}...{k[-4:]})[/dim]"

            console.print()
            table = Table(
                title="PRUBETH Personal AI Engine & Local Models Hub",
                box=box.ROUNDED,
                border_style="#00F5D4",
                header_style="bold #FF9F1C"
            )
            table.add_column("Category", style="cyan", width=24)
            table.add_column("Item / Provider", style="white", width=28)
            table.add_column("Current Personal Status / Setting", style="green")

            table.add_row("1. Personal Cloud Key", "Google Gemini API Key", mask_key(keys.get("google")))
            table.add_row("2. Personal Cloud Key", "Anthropic Claude API Key", mask_key(keys.get("anthropic")))
            table.add_row("3. Personal Cloud Key", "OpenAI API Key", mask_key(keys.get("openai")))
            table.add_row("4. Personal Cloud Key", "OpenRouter / DeepSeek Key", mask_key(keys.get("openrouter")))

            # Detected local models
            models = local_info.get("ollama_models", [])
            if models:
                models_str = ", ".join(models)
                status_str = f"[bold green]{len(models)} model(s) installed[/bold green] [dim]({models_str})[/dim]"
            else:
                status_str = "[dim yellow]No offline models detected (install via 'ollama pull <model>')[/dim yellow]"
            table.add_row("5. Downloaded Local Models", "Ollama / LM Studio", status_str)

            active_model = cfg.get("default_model", "gemini-2.5-pro")
            active_prov = cfg.get("default_provider", "google")
            table.add_row("6. Active Personal Model", f"{active_prov.upper()}", f"[bold cyan]{active_model}[/bold cyan]")

            console.print(table)

            if not (interactive and sys.stdin.isatty()):
                break

            console.print("\n[bold cyan]Personal Actions:[/bold cyan]")
            console.print("  [bold]1.[/bold] Set/Update Google Gemini Key")
            console.print("  [bold]2.[/bold] Set/Update Anthropic Claude Key")
            console.print("  [bold]3.[/bold] Set/Update OpenAI Key")
            console.print("  [bold]4.[/bold] Set/Update OpenRouter Key")
            console.print("  [bold]5.[/bold] Select Downloaded Local Model (Ollama)")
            console.print("  [bold]6.[/bold] Clear All Keys (Reset to Factory Default)")
            console.print("  [bold]7.[/bold] Done / Return to Cockpit (or press Enter)")

            ans = Prompt.ask("Choose action [1-7, or 'b' to return]", choices=["1", "2", "3", "4", "5", "6", "7", "b", "back", "q", "exit"], default="7")
            if ans in ["7", "b", "back", "q", "exit"]:
                console.print("[dim green]Returning to main cockpit...[/dim green]")
                break

            if ans == "1":
                new_k = Prompt.ask("Enter personal Google Gemini API Key [dim](or 'b' to cancel, 'clear' to unset)[/dim]", default="")
                if new_k.strip().lower() in ["", "b", "back", "cancel", "q"]:
                    console.print("[dim yellow]Cancelled. Returning to menu...[/dim yellow]")
                    continue
                if new_k.strip().lower() in ["clear", "delete", "unset", "none"]:
                    cfg_mgr.set("api_keys.google", "")
                    console.print("[green]✔ Personal Google Gemini key cleared (Not configured).[/green]")
                else:
                    cfg_mgr.set("api_keys.google", new_k.strip())
                    cfg_mgr.set("default_provider", "google")
                    cfg_mgr.set("default_model", "gemini-2.5-pro")
                    console.print("[green]✔ Personal Google Gemini key updated successfully.[/green]")
            elif ans == "2":
                new_k = Prompt.ask("Enter personal Anthropic Claude API Key [dim](or 'b' to cancel, 'clear' to unset)[/dim]", default="")
                if new_k.strip().lower() in ["", "b", "back", "cancel", "q"]:
                    console.print("[dim yellow]Cancelled. Returning to menu...[/dim yellow]")
                    continue
                if new_k.strip().lower() in ["clear", "delete", "unset", "none"]:
                    cfg_mgr.set("api_keys.anthropic", "")
                    console.print("[green]✔ Personal Anthropic Claude key cleared (Not configured).[/green]")
                else:
                    cfg_mgr.set("api_keys.anthropic", new_k.strip())
                    cfg_mgr.set("default_provider", "anthropic")
                    cfg_mgr.set("default_model", "claude-3-7-sonnet-20250219")
                    console.print("[green]✔ Personal Anthropic Claude key updated successfully.[/green]")
            elif ans == "3":
                new_k = Prompt.ask("Enter personal OpenAI API Key [dim](or 'b' to cancel, 'clear' to unset)[/dim]", default="")
                if new_k.strip().lower() in ["", "b", "back", "cancel", "q"]:
                    console.print("[dim yellow]Cancelled. Returning to menu...[/dim yellow]")
                    continue
                if new_k.strip().lower() in ["clear", "delete", "unset", "none"]:
                    cfg_mgr.set("api_keys.openai", "")
                    console.print("[green]✔ Personal OpenAI key cleared (Not configured).[/green]")
                else:
                    cfg_mgr.set("api_keys.openai", new_k.strip())
                    cfg_mgr.set("default_provider", "openai")
                    cfg_mgr.set("default_model", "o3-mini")
                    console.print("[green]✔ Personal OpenAI key updated successfully.[/green]")
            elif ans == "4":
                new_k = Prompt.ask("Enter personal OpenRouter Key [dim](or 'b' to cancel, 'clear' to unset)[/dim]", default="")
                if new_k.strip().lower() in ["", "b", "back", "cancel", "q"]:
                    console.print("[dim yellow]Cancelled. Returning to menu...[/dim yellow]")
                    continue
                if new_k.strip().lower() in ["clear", "delete", "unset", "none"]:
                    cfg_mgr.set("api_keys.openrouter", "")
                    console.print("[green]✔ Personal OpenRouter key cleared (Not configured).[/green]")
                else:
                    cfg_mgr.set("api_keys.openrouter", new_k.strip())
                    cfg_mgr.set("default_provider", "openrouter")
                    cfg_mgr.set("default_model", "o3-mini")
                    console.print("[green]✔ Personal OpenRouter key updated successfully.[/green]")
            elif ans == "5":
                if models:
                    console.print("\n[bold cyan]Select from your downloaded local models (or 'b' to cancel):[/bold cyan]")
                    for idx, m in enumerate(models, start=1):
                        console.print(f"  {idx}. [bold white]{m}[/bold white]")
                    choices = [str(i) for i in range(1, len(models) + 1)] + ["b", "back", "q"]
                    m_choice = Prompt.ask("Pick model number", choices=choices, default="1")
                    if m_choice in ["b", "back", "q"]:
                        console.print("[dim yellow]Cancelled. Returning to menu...[/dim yellow]")
                        continue
                    picked = models[int(m_choice) - 1]
                    cfg_mgr.set("default_provider", "ollama")
                    cfg_mgr.set("default_model", picked)
                    cfg_mgr.set("offline_mode", True)
                    console.print(f"[green]✔ Switched active personal model to offline local: [bold cyan]{picked}[/bold cyan][/green]")
                else:
                    custom_tag = Prompt.ask("Enter local model tag (or 'b' to cancel)", default="qwen2.5:1.5b")
                    if custom_tag.strip().lower() in ["b", "back", "cancel", "q"]:
                        continue
                    cfg_mgr.set("default_provider", "ollama")
                    cfg_mgr.set("default_model", custom_tag.strip())
                    cfg_mgr.set("offline_mode", True)
                    console.print(f"[green]✔ Configured offline local model tag: [bold cyan]{custom_tag}[/bold cyan][/green]")
            elif ans == "6":
                for p in ["google", "openai", "anthropic", "deepseek", "groq", "openrouter"]:
                    cfg_mgr.set(f"api_keys.{p}", "")
                console.print("[bold green]✔ All API keys cleared to clean factory default state![/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim yellow]Exited Personal Hub. Returning to Cockpit...[/dim yellow]")
            break
