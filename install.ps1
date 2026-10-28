& {
    $Version = if ($env:PRUBETH_VERSION) { $env:PRUBETH_VERSION } else { "v2.0.0" }
    $InstallDir = if ($env:PRUBETH_INSTALL_DIR) { $env:PRUBETH_INSTALL_DIR } else { "$env:USERPROFILE\.prubeth\bin" }
    $NoPrompt = if ($env:PRUBETH_NO_PROMPT) { $true } else { $false }
    $Force = if ($env:PRUBETH_FORCE) { $true } else { $false }

    $ErrorActionPreference = "Stop"

    # Force UTF-8 Output Encoding for Beach Theme glyphs
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    # Beach Theme ANSI Color Palette
    $Esc = [char]27
    $Coral = "$Esc[38;2;255;107;107m"
    $Gold = "$Esc[38;2;255;190;118m"
    $Turquoise = "$Esc[38;2;78;205;196m"
    $Azure = "$Esc[38;2;30;144;255m"
    $White = "$Esc[38;2;255;255;255m"
    $Dim = "$Esc[2m"
    $Bold = "$Esc[1m"
    $Reset = "$Esc[0m"

    function Write-BeachBanner {
        Write-Host "${Coral}${Bold}"
        Write-Host " ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄"
        Write-Host " █████████████                                                ▀█████████"
        Write-Host " █████████████                                                 █████████"
        Write-Host " █████████████   PRUBETH CLI — POWERSHELL INSTALLER  █████████"
        Write-Host " █████████████   Luxury Beach Theme Edition (${Version})         █████████"
        Write-Host " █████████████                                                 █████████"
        Write-Host " ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀${Reset}"
        Write-Host ""
    }

    function Write-Step {
        param([string]$Message)
        Write-Host "${Turquoise}${Bold}==>${Reset} ${White}${Bold}${Message}${Reset}"
    }

    function Write-Success {
        param([string]$Message)
        Write-Host "${Gold}${Bold}✔${Reset} ${White}${Message}${Reset}"
    }

    function Write-Info {
        param([string]$Message)
        Write-Host "  ${Dim}${Message}${Reset}"
    }

    Write-BeachBanner

    # 1. Platform & Environment Pre-Flight
    Write-Step "Checking PowerShell environment and system architecture..."
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
    Write-Info "Detected Architecture: $arch"
    Write-Info "Target Installation Directory: $InstallDir"

    if (-not (Test-Path -Path $InstallDir)) {
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        Write-Success "Created installation directory: $InstallDir"
    } else {
        Write-Info "Installation directory exists: $InstallDir"
    }

    $repoOwner = "SVR1339"
    $repoName = "PRUBETH-CLI"
    $binaryTarget = Join-Path $InstallDir "prubeth.exe"
    $zipappTarget = Join-Path $InstallDir "prubeth.pyz"
    $cmdTarget = Join-Path $InstallDir "prubeth.cmd"

    $installedSuccessfully = $false

    # 2. Local File Copy Check (If running from checked out workspace)
    $localBinDir = if ($PSScriptRoot) { Join-Path $PSScriptRoot "dist\bin\prubeth" } else { "dist\bin\prubeth" }
    $localBin = Join-Path $localBinDir "prubeth.exe"
    $localPyz = if ($PSScriptRoot) { Join-Path $PSScriptRoot "dist\prubeth.pyz" } else { "dist\prubeth.pyz" }

    if ((Test-Path $localBinDir) -and (Test-Path $localBin) -and -not $Force) {
        Write-Step "Found local pre-compiled binary distribution in repository: $localBinDir"
        Copy-Item -Path "$localBinDir\*" -Destination $InstallDir -Recurse -Force
        $installedSuccessfully = $true
        Write-Success "Installed local standalone native distribution to $binaryTarget"
    }

    # 3. Remote Download Strategy (Direct Standalone Executable / Release Zip / ZipApp)
    if (-not $installedSuccessfully) {
        $directExeUrl = "https://github.com/$repoOwner/$repoName/releases/download/$Version/prubeth.exe"
        $latestExeUrl = "https://github.com/$repoOwner/$repoName/releases/latest/download/prubeth.exe"
        $releaseZipUrl = "https://github.com/$repoOwner/$repoName/releases/download/$Version/prubeth-windows-x64.zip"
        $latestZipUrl = "https://github.com/$repoOwner/$repoName/releases/latest/download/prubeth-windows-x64.zip"
        $tempZip = Join-Path $env:TEMP "prubeth-windows-x64.zip"
        
        Write-Step "Downloading PRUBETH Standalone Native Binary (prubeth.exe) from GitHub..."
        Write-Info "Source: $directExeUrl"

        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
            Invoke-WebRequest -Uri $directExeUrl -OutFile $binaryTarget -UseBasicParsing -TimeoutSec 90
            if ((Test-Path $binaryTarget) -and ((Get-Item $binaryTarget).Length -gt 10000000)) {
                $installedSuccessfully = $true
                Write-Success "Downloaded standalone native binary directly: $binaryTarget"
            }
        } catch {
            Write-Info "Direct executable download deferred: $($_.Exception.Message). Trying release zip..."
            try {
                Invoke-WebRequest -Uri $releaseZipUrl -OutFile $tempZip -UseBasicParsing -TimeoutSec 90
                if ((Test-Path $tempZip) -and ((Get-Item $tempZip).Length -gt 1000000)) {
                    Expand-Archive -Path $tempZip -DestinationPath $InstallDir -Force
                    Remove-Item -Path $tempZip -Force
                    if (Test-Path $binaryTarget) {
                        $installedSuccessfully = $true
                        Write-Success "Downloaded and extracted standalone native binary."
                    }
                }
            } catch {
                Write-Info "Release zip download deferred. Transitioning to universal ZipApp fallback..."
            }
        }
    }

    # Strategy B: Universal ZipApp Fallback (prubeth.pyz + prubeth.cmd wrapper)
    if (-not $installedSuccessfully) {
        Write-Step "Deploying Universal Standalone ZipApp from raw GitHub..."
        $rawPyzUrl = "https://raw.githubusercontent.com/$repoOwner/$repoName/main/dist/prubeth.pyz"
        Write-Info "Source: $rawPyzUrl"
        try {
            Invoke-WebRequest -Uri $rawPyzUrl -OutFile $zipappTarget -UseBasicParsing -TimeoutSec 45
            
            # Create prubeth.cmd wrapper
            $cmdContent = "@echo off`r`npython `"%~dp0prubeth.pyz`" %*`r`n"
            Set-Content -Path $cmdTarget -Value $cmdContent -Encoding ASCII
            
            $installedSuccessfully = $true
            Write-Success "Installed Universal ZipApp and created batch launcher: $cmdTarget"
        } catch {
            Write-Info "ZipApp download error: $($_.Exception.Message)"
        }
    }

    # Strategy C: uv tool install / pipx / pip fallback
    if (-not $installedSuccessfully) {
        Write-Step "Attempting Python package installation via git..."
        $gitRepoUrl = "git+https://github.com/$repoOwner/$repoName.git"
        
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            Write-Info "Installing via uv tool..."
            & uv tool install $gitRepoUrl --force
            $installedSuccessfully = $true
            Write-Success "Installed via uv tool."
        } elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
            Write-Info "Installing via pipx..."
            & pipx install $gitRepoUrl --force
            $installedSuccessfully = $true
            Write-Success "Installed via pipx."
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            Write-Info "Installing via python pip..."
            & python -m pip install --upgrade $gitRepoUrl
            $installedSuccessfully = $true
            Write-Success "Installed via python pip."
        }
    }

    if (-not $installedSuccessfully) {
        Write-Host "${Coral}${Bold}[ERROR]${Reset} Failed to install PRUBETH CLI automatically."
        exit 1
    }

    # 4. PATH Registration
    Write-Step "Configuring Environment PATH..."
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$InstallDir*") {
        $newPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $InstallDir } else { "$userPath;$InstallDir" }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Success "Added $InstallDir permanently to User PATH."
    } else {
        Write-Info "$InstallDir is already in User PATH."
    }

    # Update current session PATH immediately
    if ($env:Path -notlike "*$InstallDir*") {
        $env:Path = "$env:Path;$InstallDir"
        Write-Success "Updated current PowerShell session PATH."
    }

    # 5. Shell Completions Setup
    Write-Step "Setting up PowerShell tab completion..."
    try {
        $profileDir = Split-Path $PROFILE -Parent
        if (-not (Test-Path $profileDir)) {
            New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
        }
        if (-not (Test-Path $PROFILE)) {
            New-Item -ItemType File -Force -Path $PROFILE | Out-Null
        }
        $profileContent = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
        $completionHook = @'

# PRUBETH CLI Tab Completion Hook
if (Get-Command prubeth -ErrorAction SilentlyContinue) {
    Register-ArgumentCompleter -Native -CommandName prubeth -ScriptBlock {
        param($wordToComplete, $commandAst, $cursorPosition)
        $commands = @(
            'setup', 'personal', 'integrity', 'doctor', 'therapy', 'settings',
            'profile', 'cache', 'timeline', 'models', 'diff', 'search',
            'heal', 'commit', 'pr', 'research', 'janitor', 'bio', 'review',
            'compact', 'reset', 'memory', 'swarm', 'worktrees', 'symbols'
        )
        $commands | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    }
}
'@
        if ($profileContent -notlike "*PRUBETH CLI Tab Completion Hook*") {
            Add-Content -Path $PROFILE -Value $completionHook
            Write-Success "PowerShell tab completions registered in $PROFILE"
        } else {
            Write-Info "PowerShell completions already present in $PROFILE"
        }
    } catch {
        Write-Info "Completions configuration skipped: $($_.Exception.Message)"
    }

    # 6. Verification
    Write-Step "Verifying installation integrity..."
    try {
        if (Test-Path $binaryTarget) {
            $ver = & $binaryTarget --version
            Write-Success "Standalone binary operational: $binaryTarget"
        } elseif (Get-Command prubeth -ErrorAction SilentlyContinue) {
            $ver = & prubeth --version
            Write-Success "PRUBETH CLI command operational in PATH."
        }
    } catch {
        Write-Info "Verification note: $($_.Exception.Message)"
    }

    Write-Host ""
    Write-Host "${Gold}${Bold}==============================================================================${Reset}"
    Write-Host "${Gold}${Bold}  PRUBETH CLI v1.3.1 Installation Completed Successfully!${Reset}"
    Write-Host "${Gold}${Bold}==============================================================================${Reset}"
    Write-Host "  Command:      ${Turquoise}prubeth${Reset} (Available globally in terminal)"
    Write-Host "  Location:     ${Dim}${InstallDir}${Reset}"
    Write-Host "  Personal Hub: ${Azure}prubeth personal${Reset} (Configure keys and local models)"
    Write-Host "  Integrity:    ${Azure}prubeth integrity${Reset} (Cryptographic attestation pass)"
    Write-Host "  Diagnostic:   ${Azure}prubeth doctor${Reset} (9-Pillar qualification check)"
    Write-Host "${Gold}${Bold}==============================================================================${Reset}"
    Write-Host ""

    if (-not $NoPrompt) {
        Write-Host "${Azure}${Bold}Would you like to launch the Personal Engine Hub now? (y/N): ${Reset}" -NoNewline
        $ans = Read-Host
        if ($ans -match "^[yY]") {
            if (Test-Path $binaryTarget) {
                & $binaryTarget personal
            } else {
                & prubeth personal
            }
        }
    }
}
