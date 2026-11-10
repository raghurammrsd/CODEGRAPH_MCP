# CodeGraph One-Command Installer for Windows (PowerShell)
# Installs CodeGraph Engine and automatically configures Cursor, Claude, Antigravity, Cline, and Codex.
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Installing CodeGraph Engine & MCP Server (Windows)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$Repo = "raghurammrsd/CODEGRAPH_MCP"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\codegraph"
$BinaryPath = Join-Path $InstallDir "codegraph.exe"

# Ensure install directory exists
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$Installed = $false

# 1. Try uv tool if available
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "-> Installing via uv tool..." -ForegroundColor Green
    try {
        uv tool install --force "codegraph-engine>=3.0.1"
        $Installed = $true
    } catch {
        Write-Host "-> uv tool install failed, falling back..." -ForegroundColor Yellow
    }
}

# 2. Try pip / python if available
if (-not $Installed -and (Get-Command pip -ErrorAction SilentlyContinue)) {
    Write-Host "-> Installing via pip..." -ForegroundColor Green
    try {
        pip install --upgrade "codegraph-engine>=3.0.1"
        $Installed = $true
    } catch {
        Write-Host "-> pip install failed, falling back..." -ForegroundColor Yellow
    }
}

if (-not $Installed -and (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "-> Installing via python -m pip..." -ForegroundColor Green
    try {
        python -m pip install --upgrade "codegraph-engine>=3.0.1"
        $Installed = $true
    } catch {
        Write-Host "-> python -m pip install failed, falling back..." -ForegroundColor Yellow
    }
}

# 3. Fallback: Download standalone prebuilt binary from GitHub Releases
if (-not $Installed) {
    Write-Host "-> Downloading standalone zero-dependency Windows executable..." -ForegroundColor Green
    $Arch = if ([System.Environment]::Is64BitOperatingSystem) { "amd64" } else { "arm64" }
    $ReleaseUrl = "https://github.com/$Repo/releases/latest/download/codegraph-windows-$Arch.exe"
    
    try {
        Invoke-WebRequest -Uri $ReleaseUrl -OutFile $BinaryPath -UseBasicParsing
        $Installed = $true
    } catch {
        Write-Error "Failed to download binary from $ReleaseUrl. Please install Python 3.12+ or uv."
        exit 1
    }
}

# Ensure directory is on User PATH
$UserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
    $env:Path = "$env:Path;$InstallDir"
}

# Resolve codegraph command
$CodeGraphCmd = "codegraph"
if (-not (Get-Command codegraph -ErrorAction SilentlyContinue)) {
    if (Test-Path $BinaryPath) {
        $CodeGraphCmd = $BinaryPath
    } else {
        $CodeGraphCmd = "python -m codegraph"
    }
}

Write-Host "-> Verifying CodeGraph installation..." -ForegroundColor Green
& $CodeGraphCmd --version

Write-Host ""
Write-Host "-> Automatically configuring AI Coding Clients (Antigravity, Cursor, Claude Desktop, Cline)..." -ForegroundColor Green
& $CodeGraphCmd install -y --target all

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "CodeGraph successfully installed and configured on Windows!" -ForegroundColor Cyan
Write-Host "Run 'codegraph mcp doctor' anytime to verify connection." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
