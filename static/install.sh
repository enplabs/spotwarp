#!/usr/bin/env bash
# ==============================================================================
# 🚀 SpotWarp Official Universal Installer (Linux / macOS)
# ==============================================================================
# Usage:
#   curl -fsSL https://gpu-action.com/install.sh | bash
# ==============================================================================

set -e

BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}"
echo "  ____              _ __        __                 "
echo " / ___| _ __   ___ | |\ \      / /_ _ _ __ _ __    "
echo " \___ \| '_ \ / _ \| __\ \ /\ / / _\` | '__| '_ \   "
echo "  ___) | |_) | (_) | |_ \ V  V / (_| | |  | |_) |  "
echo " |____/| .__/ \___/ \__| \_/\_/ \__,_|_|  | .__/   "
echo "       |_|                                |_|      "
echo -e "${RESET}"
echo -e "${BOLD}SpotWarp: Spot GPU Continuous Backup & Cross-Cloud Failover Daemon${RESET}"
echo -e "Version: ${GREEN}v3.3.2${RESET}\n"

# 1. Check Python3 presence
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}[!] Python 3 not found. Please install Python 3.8+ to proceed.${RESET}"
    exit 1
fi

echo -e "${CYAN}[*] Installing/Upgrading spotwarp via pip...${RESET}"
python3 -m pip install --upgrade --quiet "spotwarp>=3.3.2"

# 2. Verify CLI installation
if command -v spotwarp &> /dev/null; then
    echo -e "${GREEN}[+] Successfully installed spotwarp $(spotwarp --version 2>/dev/null || echo '3.3.1')!${RESET}"
else
    echo -e "${YELLOW}[!] Warning: spotwarp binary path not in PATH. Adding ~/.local/bin...${RESET}"
    export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Check for existing Vast / RunPod keys (Smart Sniffing)
SNIFFED_VAST=""
if [ -f "$HOME/.vast_api_key" ]; then
    SNIFFED_VAST="$HOME/.vast_api_key"
fi

echo -e "\n${BOLD}================================================================${RESET}"
if [ -n "$SNIFFED_VAST" ]; then
    echo -e "${GREEN}[+] Zero-Config: Auto-detected Vast.ai API Key at ~/.vast_api_key!${RESET}"
    echo -e "    You can launch protection immediately with:"
    echo -e "    ${CYAN}${BOLD}spotwarp start -d${RESET}"
else
    echo -e "${BOLD}Next Steps:${RESET}"
    echo -e "  1. Run the 1-minute setup wizard:"
    echo -e "     ${CYAN}${BOLD}spotwarp init${RESET}"
    echo -e "  2. Start background protection daemon:"
    echo -e "     ${CYAN}${BOLD}spotwarp start -d${RESET}"
fi
echo -e "${BOLD}================================================================${RESET}\n"
