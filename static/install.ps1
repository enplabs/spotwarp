# ==============================================================================
# 🚀 SpotWarp Official Universal Installer (Windows PowerShell)
# ==============================================================================
# Usage:
#   irm https://gpu-action.com/install.ps1 | iex
# ==============================================================================

Write-Host ""
Write-Host "  ____              _ __        __                 " -ForegroundColor Cyan
Write-Host " / ___| _ __   ___ | |\ \      / /_ _ _ __ _ __    " -ForegroundColor Cyan
Write-Host " \___ \| '_ \ / _ \| __\ \ /\ / / _` | '__| '_ \   " -ForegroundColor Cyan
Write-Host "  ___) | |_) | (_) | |_ \ V  V / (_| | |  | |_) |  " -ForegroundColor Cyan
Write-Host " |____/| .__/ \___/ \__| \_/\_/ \__,_|_|  | .__/   " -ForegroundColor Cyan
Write-Host "       |_|                                |_|      " -ForegroundColor Cyan
Write-Host ""
Write-Host "SpotWarp: Spot GPU Continuous Backup & Cross-Cloud Failover Daemon" -ForegroundColor White
Write-Host "Version: v3.4.2" -ForegroundColor Green
Write-Host ""

$installDir = "$HOME\AppData\Local\Programs\SpotWarp"
if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

$binTarget = "$installDir\spotwarp.exe"
$binaryInstalled = $false

# 1. Attempt Standalone Windows Binary Download (C-Compiled, Python-Free)
$releaseUrl = "https://github.com/enplabs/spotwarp/releases/latest/download/spotwarp-windows-x64.exe"
Write-Host "[*] Downloading pre-compiled standalone binary (spotwarp-windows-x64.exe)..." -ForegroundColor Cyan
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $releaseUrl -OutFile $binTarget -UseBasicParsing -TimeoutSec 15
    if (Test-Path $binTarget) {
        $testVer = & $binTarget --version 2>$null
        if ($testVer -like "*SpotWarp*") {
            $binaryInstalled = $true
            Write-Host "[+] Successfully installed standalone binary to $binTarget!" -ForegroundColor Green
        }
    }
} catch {
    # Fallback silently to pip
}

# 2. Resilient Fallback to pip
if (-not $binaryInstalled) {
    Write-Host "[*] Falling back to pip installation..." -ForegroundColor Yellow
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host "[!] Python not found in PATH. Please install Python 3.8+ from python.org." -ForegroundColor Yellow
        Exit 1
    }
    python -m pip install --upgrade --quiet "spotwarp>=3.4.2"
    Write-Host "[+] Successfully installed spotwarp package!" -ForegroundColor Green
} else {
    # Add to User PATH if not present
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$installDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$installDir;$userPath", "User")
        $env:Path = "$installDir;$env:Path"
    }
}

# 3. Smart Sniffing for Cloud Keys
$vastKeyFile = "$HOME\.vast_api_key"
$runpodKeyFile = "$HOME\.runpod\config.toml"
$hasVast = (Test-Path $vastKeyFile) -or [bool]$env:VAST_API_KEY
$hasRunpod = (Test-Path $runpodKeyFile) -or [bool]$env:RUNPOD_API_KEY

Write-Host ""
Write-Host "================================================================" -ForegroundColor White
Write-Host "[+] SpotWarp v3.4.2 is READY!" -ForegroundColor Green
if ($hasVast) {
    Write-Host "    ? Auto-detected Vast.ai API Key" -ForegroundColor Green
}
if ($hasRunpod) {
    Write-Host "    ? Auto-detected RunPod API Key" -ForegroundColor Green
}
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Complete setup with your license key:" -ForegroundColor White
Write-Host "     spotwarp init" -ForegroundColor Cyan
Write-Host "     (Or start directly: spotwarp start --license-key <YOUR_KEY> -d)" -ForegroundColor Gray
Write-Host "  2. Don't have a license key? Get one at:" -ForegroundColor White
Write-Host "     https://gpu-action.com/pricing" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor White
Write-Host ""
