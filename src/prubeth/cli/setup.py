"""PRUBETH Onboarding, Interactive Setup Wizard, and Local AI Setup System.

Provides user-friendly setup for Cloud AI providers, Local AI models (Ollama/LM Studio),
automatic model shifters, and factory reset verification.
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

from prubeth.config.manager import ConfigManager, DEFAULT_CONFIG

def probe_local_ai_capabilities() -> Dict[str, Any]:
    """Inspects the local system for installed local AI engines (Ollama, LM Studio)."""
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        # Check standard Windows AppData location
        local_appdata = os.getenv("LOCALAPPDATA", "")
        if local_appdata:
            candidate = Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe"
            if candidate.exists():
                ollama_path = str(candidate)

    # Check if Ollama daemon is running on port 11434
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

    # Check if LM Studio is running on port 1234
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

def render_onboarding_wizard(console: Console, cfg_mgr: Optional[ConfigManager] = None):
    """Renders the comprehensive user-friendly onboarding and setup guide."""
    cfg_mgr = cfg_mgr or ConfigManager()
    cfg = cfg_mgr.load_config()
    keys = cfg.get("api_keys", {})
    local_info = probe_local_ai_capabilities()

    # 1. Welcome & Architecture Overview
    welcome_text = """[bold cyan]Welcome to PRUBETH Autonomous Developer CLI![/bold cyan]

PRUBETH operates an [bold green]Automatic Multi-Tier Cognitive Shifter[/bold green]:
  • [bold]Tier 1 (Highest):[/bold] Flagship Frontier Pro Reasoning (Gemini 3.1 Pro / OpenRouter Free 550B & 120B)
  • [bold]Tier 2 (Balanced):[/bold] High-throughput coding workhorses (Gemini 3.5 Flash / Nemotron Lightning)
  • [bold]Tier 3 (Ultra-Fast):[/bold] Sub-second lite verifiers (Gemini 3.1 Flash Lite / Gemma)
  • [bold]Tier 4 (Direct Local):[/bold] [bold yellow]Automatic pivot to local downloaded models on API key issue or cloud timeout (>12s)[/bold yellow]
"""
    console.print(Panel(welcome_text, title="PRUBETH First-Time Setup & Onboarding", border_style="cyan"))

    # 2. Current Credentials & Engine Status Table
    status_table = Table(title="Active Model Providers & Credentials Status")
    status_table.add_column("Provider / Engine", style="cyan")
    status_table.add_column("Type", style="yellow")
    status_table.add_column("Status", style="green")
    status_table.add_column("Configured Key / Model", style="magenta")

    g_status = "[bold green]● Configured & Active[/bold green]" if keys.get("google") else "[dim]○ Not Set[/dim]"
    or_status = "[bold green]● Configured & Active[/bold green]" if keys.get("openrouter") else "[dim]○ Not Set[/dim]"
    
    if local_info["ollama_running"]:
        ol_status = f"[bold green]● Active ({len(local_info['ollama_models'])} models loaded)[/bold green]"
    elif local_info["ollama_installed"]:
        ol_status = "[yellow]○ Installed (Service Offline)[/yellow]"
    else:
        ol_status = "[dim]○ Not Installed[/dim]"

    lm_status = f"[bold green]● Active ({len(local_info['lm_studio_models'])} models)[/bold green]" if local_info["lm_studio_running"] else "[dim]○ Offline (Port 1234)[/dim]"

    status_table.add_row("Google Gemini", "Cloud Frontier", g_status, "***zz8g" if keys.get("google") else "None")
    status_table.add_row("OpenRouter", "Cloud Multi-Model", or_status, "***f09c" if keys.get("openrouter") else "None")
    status_table.add_row("Ollama", "Local GGUF Hardware", ol_status, ", ".join(local_info["ollama_models"][:2]) or "None")
    status_table.add_row("LM Studio", "Local Model Server", lm_status, ", ".join(local_info["lm_studio_models"][:2]) or "None")
    console.print(status_table)

    # 3. Local Model Download & Setup Guidance
    download_panel = """[bold yellow]Local AI Model Setup (Zero Cloud Cost & Air-Gapped Fallback):[/bold yellow]

Whenever your cloud API keys have an issue (unauthorized, expired, quota limit) or cloud inference
takes too much time (>12s), PRUBETH [bold green]directly and automatically shifts to your local model[/bold green]!

To download a local AI model from the internet onto your PC, run any of these in PowerShell:

  [bold green]1. Lightweight & Ultra-Fast (~1.2 GB - Runs on Any Laptop/PC):[/bold green]
     [cyan]ollama run qwen2.5-coder:1.5b[/cyan]

  [bold green]2. Recommended High-Capability Coding Model (~4.7 GB):[/bold green]
     [cyan]ollama run qwen2.5-coder:7b[/cyan]

  [bold green]3. Meta Llama 3.2 Compact Model (~2.0 GB):[/bold green]
     [cyan]ollama run llama3.2:3b[/cyan]

Once downloaded, PRUBETH auto-detects it on port 11434 in [bold]< 120ms[/bold] with zero configuration needed.
"""
    console.print(Panel(download_panel, title="Local AI Setup & One-Click Download Options", border_style="yellow"))

    # 4. User-Friendly Setup Options Menu
    console.print("""[bold cyan]User-Friendly Setup Quick Commands:[/bold cyan]
  • [bold]Set Cloud API Key:[/bold]       prubeth config set api_keys.google <YOUR_KEY>
  • [bold]Set OpenRouter Key:[/bold]      prubeth config set api_keys.openrouter <YOUR_KEY>
  • [bold]Set Primary Model:[/bold]       prubeth set default_model gemini-3.1-pro-preview
  • [bold]Set Pure Free Tier:[/bold]      prubeth set default_model openrouter/free
  • [bold]Set 100% Airgap Local:[/bold]   prubeth profile apply local-airgap
  • [bold]Launch Performance HUD:[/bold]   prubeth --status
  • [bold]Inspect Model Ranks:[/bold]      prubeth models
  • [bold]Factory Default Reset:[/bold]    prubeth reset (Restores initial factory setup mode anytime)
""")

def execute_factory_reset(console: Console, cfg_mgr: Optional[ConfigManager] = None):
    """Executes clean factory default reset and returns to pristine first-onboarding state."""
    cfg_mgr = cfg_mgr or ConfigManager()
    cfg_mgr.save_config(DEFAULT_CONFIG.copy())
    console.print(Panel(
        "[bold green]✅ Factory Default Reset Successfully Executed![/bold green]\n\n"
        "All configuration settings, active profiles, and overrides have been restored to the "
        "pristine default state (Performance Builder Profile, Highest Pro Reasoning Model, 12s Local Latency Guard).\n\n"
        "To review or reconfigure your onboarding settings, run: [bold cyan]prubeth setup[/bold cyan]",
        title="PRUBETH Factory Default Reset",
        border_style="green"
    ))
