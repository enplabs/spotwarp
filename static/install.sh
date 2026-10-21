#!/usr/bin/env bash
# ==============================================================================
# 🚀 SpotWarp Official Universal Installer for SaladCloud (Linux / macOS)
# ==============================================================================
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
echo -e "${BOLD}SpotWarp: Zero-Loss Checkpoint Backup & Same-Cloud Failover for SaladCloud${RESET}"
echo -e "Version: ${GREEN}v3.5.2${RESET}\n"

INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

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

if [ $BINARY_INSTALLED -eq 0 ]; then
    echo -e "${YELLOW}[*] Proceeding with Python pip installation...${RESET}"
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}[!] Python 3 not found. Please install Python 3.8+ to proceed.${RESET}"
        exit 1
    fi

    INSTALL_SUCCESS=0
    if python3 -m pip install --upgrade --quiet "spotwarp" 2>/dev/null; then
        INSTALL_SUCCESS=1
    elif python3 -m pip install --upgrade --break-system-packages --quiet "spotwarp" 2>/dev/null; then
        INSTALL_SUCCESS=1
    elif python3 -m pip install --user --upgrade --break-system-packages --quiet "spotwarp" 2>/dev/null; then
        INSTALL_SUCCESS=1
    fi

    if [ $INSTALL_SUCCESS -eq 0 ]; then
        echo -e "${YELLOW}[!] Installation failed. Run manually: pip install --user spotwarp${RESET}"
        exit 1
    fi
fi

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

echo -e "\n${BOLD}================================================================${RESET}"
echo -e "${GREEN}[+] SpotWarp v3.5.2 (SaladCloud Edition) is READY!${RESET}"
echo -e "\n${BOLD}Next Steps:${RESET}"
echo -e "  1. Configure your SaladCloud API key & Organization:"
echo -e "     ${CYAN}${BOLD}spotwarp init${RESET}"
echo -e "  2. Start protecting your SaladCloud containers in the background:"
echo -e "     ${CYAN}${BOLD}spotwarp start -d${RESET}"
echo -e "${BOLD}================================================================${RESET}\n"
