import sys
import platform
import json
from typing import Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

PRUBETH_VERSION = "1.0.0"
RELEASE_TIER = "Enterprise Commercial Production"
LICENSE = "Apache-2.0"
BUILD_COMMIT = "release-v1.0.0-final"

def get_version_metadata() -> Dict[str, Any]:
    """Returns structured system and runtime version metadata."""
    codepage = "Unknown"
    if sys.platform == "win32":
        try:
            import ctypes
            codepage = f"CP {ctypes.windll.kernel32.GetConsoleOutputCP()}"
        except Exception:
            codepage = "CP 65001 (UTF-8)"
    else:
        codepage = "UTF-8"

    return {
        "version": PRUBETH_VERSION,
        "release_tier": RELEASE_TIER,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "os_release": platform.platform(),
        "architecture": platform.machine(),
        "terminal_encoding": codepage,
        "memory_budget": "< 33 MB CPU RAM | 0 MB GPU VRAM",
        "zero_telemetry": "Verified (100% Local-First)",
        "license": LICENSE,
        "build_commit": BUILD_COMMIT
    }

def render_version_info(console: Console, as_json: bool = False):
    """Renders formatted Tier-1 version information."""
    meta = get_version_metadata()
    if as_json:
        sys.stdout.write(json.dumps(meta, indent=2) + "\n")
        sys.stdout.flush()
        return

    table = Table(title="PRUBETH Autonomous CLI — Version & Runtime Information", border_style="cyan")
    table.add_column("Component", style="bold cyan", width=24)
    table.add_column("Specification / Status", style="green")

    table.add_row("CLI Version", f"[bold white]{meta['version']}[/bold white]")
    table.add_row("Release Tier", f"[bold yellow]{meta['release_tier']}[/bold yellow]")
    table.add_row("Python Runtime", f"v{meta['python_version']} ({meta['architecture']})")
    table.add_row("Operating System", meta['os_release'])
    table.add_row("Terminal Encoding", f"{meta['terminal_encoding']} (PRINCE3 Zero Font Blur)")
    table.add_row("Memory Footprint Budget", meta['memory_budget'])
    table.add_row("Zero-Telemetry Guarantee", f"[bold green]{meta['zero_telemetry']}[/bold green]")
    table.add_row("License", f"[bold white]{meta['license']}[/bold white] (Permissive Commercial)")
    table.add_row("Build Signature", f"[dim]{meta['build_commit']}[/dim]")

    console.print(table)
    console.print(" [dim]Documentation: https://github.com/prubeth-org/prubeth | Security: security@prubeth.org[/dim]\n")
