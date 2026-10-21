# ==============================================================================
# 🚀 SpotWarp Official Universal Installer for SaladCloud (Windows PowerShell)
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
Write-Host "SpotWarp: Zero-Loss Checkpoint Backup & Same-Cloud Failover for SaladCloud" -ForegroundColor White
Write-Host "Version: v3.5.2" -ForegroundColor Green
Write-Host ""

$installDir = "$HOME\AppData\Local\Programs\SpotWarp"
if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

$binTarget = "$installDir\spotwarp.exe"
$binaryInstalled = $false

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
}

if (-not $binaryInstalled) {
    Write-Host "[*] Falling back to pip installation..." -ForegroundColor Yellow
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host "[!] Python not found in PATH. Please install Python 3.8+ from python.org." -ForegroundColor Yellow
        Exit 1
    }
    python -m pip install --upgrade --quiet "spotwarp"
    Write-Host "[+] Successfully installed spotwarp package!" -ForegroundColor Green
} else {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$installDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$installDir;$userPath", "User")
        $env:Path = "$installDir;$env:Path"
    }
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor White
Write-Host "[+] SpotWarp v3.5.2 (SaladCloud Edition) is READY!" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Configure your SaladCloud API key & Organization:" -ForegroundColor White
Write-Host "     spotwarp init" -ForegroundColor Cyan
Write-Host "  2. Start protecting your SaladCloud containers in background:" -ForegroundColor White
Write-Host "     spotwarp start -d" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor White
Write-Host ""
