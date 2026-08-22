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
Write-Host "Version: v3.3.1" -ForegroundColor Green
Write-Host ""

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[!] Python not found in PATH. Please install Python 3.8+ from python.org." -ForegroundColor Yellow
    Exit 1
}

Write-Host "[*] Installing/Upgrading spotwarp via pip..." -ForegroundColor Cyan
python -m pip install --upgrade --quiet "spotwarp>=3.3.1"

# 2. Check installation
$spotwarpCmd = Get-Command spotwarp -ErrorAction SilentlyContinue
if ($spotwarpCmd) {
    Write-Host "[+] Successfully installed spotwarp v3.3.1!" -ForegroundColor Green
} else {
    Write-Host "[+] Installed spotwarp module. (Run via: python -m spotwarp or spotwarp)" -ForegroundColor Green
}

# 3. Check for Smart Sniffed keys
$vastKeyFile = "$HOME\.vast_api_key"
Write-Host ""
Write-Host "================================================================" -ForegroundColor White
if (Test-Path $vastKeyFile) {
    Write-Host "[+] Zero-Config: Auto-detected Vast.ai API Key at $vastKeyFile!" -ForegroundColor Green
    Write-Host "    You can launch protection immediately with:" -ForegroundColor White
    Write-Host "    spotwarp start -d" -ForegroundColor Cyan
} else {
    Write-Host "Next Steps:" -ForegroundColor White
    Write-Host "  1. Run the 1-minute setup wizard:" -ForegroundColor White
    Write-Host "     spotwarp init" -ForegroundColor Cyan
    Write-Host "  2. Start background protection daemon:" -ForegroundColor White
    Write-Host "     spotwarp start -d" -ForegroundColor Cyan
}
Write-Host "================================================================" -ForegroundColor White
Write-Host ""
