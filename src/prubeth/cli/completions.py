"""Subsystem: PRUBETH Shell Completion Script Generator.

Generates native shell completion scripts for PowerShell, Bash, and Zsh.
Standard feature in Tier-1 CLIs (`gcloud`, `gh`, `docker`, `kubectl`).
"""

def generate_powershell_completion() -> str:
    return r"""# PRUBETH CLI PowerShell Tab Completion Script
# Add to your PowerShell profile: Invoke-Expression (& prubeth completion powershell)

Register-ArgumentCompleter -Native -CommandName prubeth -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    
    $commands = @(
        'run', 'settings', 'status', 'tune', 'models', 'setup', 'onboarding', 'reset', 
        'inspect', 'profile', 'toggle', 'set', 'config', 'configure', 'therapy', 'heal', 'swarm', 
        'worktrees', 'memory', 'bridge', 'consensus', 'mcp', 'doctor', 'version', 'help', 'completion'
    )
    
    $profiles = @('builder', 'deep-reasoning', 'local-airgap', 'safe-audit')
    $settings = @(
        'default_model', 'default_provider', 'cloud_timeout_s', 'watchdog_timeout_s',
        'speculative_plan_b', 'enable_prompt_caching', 'developer_mode', 'offline_mode'
    )

    $elements = $commandAst.ToString().Split(' ')
    if ($elements.Count -le 2) {
        $commands | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    } elseif ($elements[1] -eq 'profile' -and $elements.Count -le 3) {
        $profiles | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    } elseif ($elements[1] -in @('inspect', 'toggle') -and $elements.Count -le 3) {
        $settings | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    }
}
"""

def generate_bash_completion() -> str:
    return r"""# PRUBETH CLI Bash Completion Script
# Add to ~/.bashrc: eval "$(prubeth completion bash)"

_prubeth_completions() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="run settings status tune models setup onboarding reset inspect profile toggle set config configure therapy heal swarm worktrees memory bridge consensus mcp doctor version help completion"

    if [ $COMP_CWORD -eq 1 ]; then
        COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        return 0
    fi
}
complete -F _prubeth_completions prubeth
"""

def generate_zsh_completion() -> str:
    return r"""#compdef prubeth
# PRUBETH CLI Zsh Completion Script

_prubeth() {
    local -a commands
    commands=(
        'run:Execute autonomous coding goal'
        'settings:Display performance settings HUD'
        'status:Display full status dashboard'
        'tune:Launch hardware telemetry & SPI benchmark'
        'models:Inspect model preference hierarchy'
        'setup:Launch interactive onboarding wizard'
        'reset:Restore factory default configuration'
        'doctor:Run system qualification diagnostic'
        'completion:Generate shell tab completion script'
    )
    _describe 'command' commands
}
_prubeth "$@"
"""

def install_shell_completion(shell_name: str = None) -> tuple:
    """Automatically discovers profile path and safely installs completion script."""
    import os
    from pathlib import Path

    if not shell_name:
        if os.name == "nt":
            shell_name = "powershell"
        else:
            shell_env = os.getenv("SHELL", "").lower()
            if "zsh" in shell_env:
                shell_name = "zsh"
            else:
                shell_name = "bash"

    shell_name = shell_name.lower()

    if shell_name in ["powershell", "pwsh"]:
        possible_paths = [
            Path.home() / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
            Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
            Path.home() / "OneDrive" / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
            Path.home() / "OneDrive" / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
        ]
        target_file = None
        for p in possible_paths:
            if p.parent.exists():
                target_file = p
                break
        if not target_file:
            target_file = possible_paths[0]

        target_file.parent.mkdir(parents=True, exist_ok=True)
        if not target_file.exists():
            target_file.write_text("# PowerShell Profile\n", encoding="utf-8")

        existing_text = target_file.read_text(encoding="utf-8", errors="ignore")
        if "Register-ArgumentCompleter -Native -CommandName prubeth" in existing_text:
            return True, f"PRUBETH completion already installed in: {target_file}"

        completion_script = generate_powershell_completion()
        with open(target_file, "a", encoding="utf-8") as f:
            f.write("\n\n" + completion_script + "\n")

        return True, f"Successfully installed PRUBETH completion to:\n  {target_file}\n\nActivate now with: . '{target_file}'"

    elif shell_name == "bash":
        target_file = Path.home() / ".bashrc"
        existing_text = target_file.read_text(encoding="utf-8", errors="ignore") if target_file.exists() else ""
        if "_prubeth_completions" in existing_text:
            return True, f"PRUBETH completion already installed in: {target_file}"

        completion_script = generate_bash_completion()
        with open(target_file, "a", encoding="utf-8") as f:
            f.write("\n\n" + completion_script + "\n")
        return True, f"Successfully installed PRUBETH completion to: {target_file}\nActivate with: source ~/.bashrc"

    elif shell_name == "zsh":
        target_file = Path.home() / ".zshrc"
        existing_text = target_file.read_text(encoding="utf-8", errors="ignore") if target_file.exists() else ""
        if "_prubeth" in existing_text:
            return True, f"PRUBETH completion already installed in: {target_file}"

        completion_script = generate_zsh_completion()
        with open(target_file, "a", encoding="utf-8") as f:
            f.write("\n\n" + completion_script + "\n")
        return True, f"Successfully installed PRUBETH completion to: {target_file}\nActivate with: source ~/.zshrc"

    return False, f"Unsupported shell: {shell_name}"
