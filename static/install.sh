#!/usr/bin/env bash
# ==============================================================================
# 🚀 SpotWarp Official Universal Installer (Linux / macOS)
# ==============================================================================
# Fast, zero-dependency standalone binary installer with resilient pip fallback.
#
# Usage:
#   curl -fsSL https://gpu-action.com/install.sh | bash
# ==============================================================================

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
echo -e "Version: ${GREEN}v3.4.2${RESET}\n"

INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

# 1. Detect OS and Hardware Architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

BIN_TARGET=""
if [ "$OS" = "linux" ] && [ "$ARCH" = "x86_64" ]; then
    BIN_TARGET="spotwarp-linux-x86_64"
elif [ "$OS" = "darwin" ] && [ "$ARCH" = "arm64" ]; then
    BIN_TARGET="spotwarp-darwin-arm64"
elif [ "$OS" = "darwin" ] && [ "$ARCH" = "x86_64" ]; then
    BIN_TARGET="spotwarp-darwin-x86_64"
fi

BINARY_INSTALLED=0

# 2. Attempt Standalone Binary Download (C-Compiled, Python-Free, Fast)
if [ -n "$BIN_TARGET" ]; then
    RELEASE_URL="https://github.com/enplabs/spotwarp/releases/latest/download/${BIN_TARGET}"
    echo -e "${CYAN}[*] Downloading pre-compiled standalone binary (${BIN_TARGET})...${RESET}"
    
    TMP_BIN="/tmp/${BIN_TARGET}_$$"
    if curl -fsSL --connect-timeout 8 --retry 2 "$RELEASE_URL" -o "$TMP_BIN" 2>/dev/null; then
        chmod +x "$TMP_BIN"
        if "$TMP_BIN" --version &>/dev/null; then
            mv "$TMP_BIN" "$INSTALL_DIR/spotwarp"
            chmod +x "$INSTALL_DIR/spotwarp"
            BINARY_INSTALLED=1
            echo -e "${GREEN}[+] Successfully installed standalone binary to ${INSTALL_DIR}/spotwarp!${RESET}"
        else
            rm -f "$TMP_BIN"
        fi
    fi
fi

# 3. Resilient Fallback to Python Multi-Tier Installation if binary unavailable
if [ $BINARY_INSTALLED -eq 0 ]; then
    echo -e "${YELLOW}[*] Standalone binary skipped or unavailable for current platform. Proceeding with pip...${RESET}"
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}[!] Python 3 not found. Please install Python 3.8+ to proceed.${RESET}"
        exit 1
    fi

    INSTALL_SUCCESS=0
    # Tier 1: Standard pip install
    if python3 -m pip install --upgrade --quiet "spotwarp>=3.4.2" 2>/dev/null; then
        INSTALL_SUCCESS=1
    fi

    # Tier 2: PEP 668 bypass (--break-system-packages)
    if [ $INSTALL_SUCCESS -eq 0 ]; then
        if python3 -m pip install --upgrade --break-system-packages --quiet "spotwarp>=3.4.2" 2>/dev/null; then
            INSTALL_SUCCESS=1
        fi
    fi

    # Tier 3: User mode
    if [ $INSTALL_SUCCESS -eq 0 ]; then
        if python3 -m pip install --user --upgrade --break-system-packages --quiet "spotwarp>=3.4.2" 2>/dev/null; then
            INSTALL_SUCCESS=1
        fi
    fi

    # Tier 4: pipx
    if [ $INSTALL_SUCCESS -eq 0 ] && command -v pipx &> /dev/null; then
        if pipx install --upgrade spotwarp 2>/dev/null || pipx install spotwarp 2>/dev/null; then
            INSTALL_SUCCESS=1
        fi
    fi

    # Tier 5: Isolated venv
    if [ $INSTALL_SUCCESS -eq 0 ]; then
        echo -e "${YELLOW}[*] Setting up isolated venv at ~/.spotwarp/venv...${RESET}"
        mkdir -p "$HOME/.spotwarp"
        if python3 -m venv "$HOME/.spotwarp/venv" 2>/dev/null; then
            if "$HOME/.spotwarp/venv/bin/pip" install --upgrade --quiet "spotwarp>=3.4.2" 2>/dev/null; then
                ln -sf "$HOME/.spotwarp/venv/bin/spotwarp" "$INSTALL_DIR/spotwarp"
                INSTALL_SUCCESS=1
            fi
        fi
    fi

    if [ $INSTALL_SUCCESS -eq 0 ]; then
        echo -e "${YELLOW}[!] Installation failed. Run manually: pip install --user spotwarp${RESET}"
        exit 1
    fi
fi

# 4. PATH Configuration (Idempotent)
case ":$PATH:" in
    *":$INSTALL_DIR:"*) ;;
    *)
        export PATH="$INSTALL_DIR:$PATH"
        for RC in "$HOME/.bashrc" "$HOME/.zshrc"; do
            if [ -f "$RC" ]; then
                if ! grep -qs '\.local/bin' "$RC"; then
                    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
                fi
            fi
        done
        ;;
esac

# 5. Smart Sniffing for Existing Cloud Keys
SNIFFED_VAST=""
if [ -f "$HOME/.vast_api_key" ]; then
    SNIFFED_VAST="$HOME/.vast_api_key"
elif [ -n "$VAST_API_KEY" ]; then
    SNIFFED_VAST="env:VAST_API_KEY"
fi

SNIFFED_RUNPOD=""
if [ -n "$RUNPOD_API_KEY" ]; then
    SNIFFED_RUNPOD="env:RUNPOD_API_KEY"
elif [ -f "$HOME/.runpod/config.toml" ]; then
    SNIFFED_RUNPOD="$HOME/.runpod/config.toml"
elif [ -f "$HOME/.runpod_api_key" ]; then
    SNIFFED_RUNPOD="$HOME/.runpod_api_key"
fi

echo -e "\n${BOLD}================================================================${RESET}"
echo -e "${GREEN}[+] SpotWarp v3.4.2 is READY!${RESET}"
if [ -n "$SNIFFED_VAST" ]; then
    echo -e "${GREEN}    ? Auto-detected Vast.ai API Key (${SNIFFED_VAST})${RESET}"
fi
if [ -n "$SNIFFED_RUNPOD" ]; then
    echo -e "${GREEN}    ? Auto-detected RunPod API Key (${SNIFFED_RUNPOD})${RESET}"
fi

echo -e "\n${BOLD}Next Steps:${RESET}"
echo -e "  1. Complete setup with your license key:"
echo -e "     ${CYAN}${BOLD}spotwarp init${RESET}"
echo -e "     (Or start directly: ${CYAN}spotwarp start --license-key <YOUR_KEY> -d${RESET})"
echo -e "  2. Don't have a license key? Get one at:"
echo -e "     ${CYAN}https://gpu-action.com/pricing${RESET}"
echo -e "${BOLD}================================================================${RESET}\n"
