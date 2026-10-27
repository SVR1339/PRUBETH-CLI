#!/usr/bin/env bash
# ==============================================================================
# PRUBETH Autonomous Developer CLI — Global Installer for macOS & Linux
# ==============================================================================
# One-line automated installation for PRUBETH CLI directly from GitHub.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/SVR1339/PRUBETH-CLI/main/install.sh | bash
# ==============================================================================

set -eo pipefail

VERSION="v1.3.1"
REPO_OWNER="SVR1339"
REPO_NAME="PRUBETH-CLI"
INSTALL_DIR="${HOME}/.prubeth/bin"

# Luxury Beach Theme ANSI Palette
CORAL='\033[38;2;255;107;107m'
GOLD='\033[38;2;255;190;118m'
TURQUOISE='\033[38;2;78;205;196m'
AZURE='\033[38;2;30;144;255m'
WHITE='\033[38;2;255;255;255m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${CORAL}${BOLD}"
cat << 'EOF'
 ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
 █████████████                                                ▀█████████
 █████████████                                                 █████████
 █████████████   PRUBETH CLI — ONE-LINE INSTALLER    █████████
 █████████████   Luxury Beach Theme Edition (v1.3.1)           █████████
 █████████████                                                 █████████
 ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
EOF
echo -e "${RESET}"

echo -e "${TURQUOISE}${BOLD}==>${RESET} ${WHITE}${BOLD}Checking operating system and environment...${RESET}"
OS="$(uname -s)"
ARCH="$(uname -m)"
echo -e "  ${DIM}Detected OS: ${OS} (${ARCH})${RESET}"
echo -e "  ${DIM}Installation Directory: ${INSTALL_DIR}${RESET}"

mkdir -p "${INSTALL_DIR}"

INSTALLED=false
TARGET="${INSTALL_DIR}/prubeth"

# Strategy A: Universal ZipApp from GitHub
echo -e "${TURQUOISE}${BOLD}==>${RESET} ${WHITE}${BOLD}Downloading PRUBETH Standalone Distribution from GitHub...${RESET}"
PYZ_URL="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main/dist/prubeth.pyz"
RELEASE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${VERSION}/prubeth.pyz"

if curl -fsSL "${RELEASE_URL}" -o "${TARGET}" 2>/dev/null || curl -fsSL "${PYZ_URL}" -o "${TARGET}"; then
    chmod +x "${TARGET}"
    INSTALLED=true
    echo -e "${GOLD}${BOLD}✔${RESET} Standalone Universal Executable deployed to ${TARGET}"
fi

# Strategy B: uv tool install / pipx / pip fallback
if [ "$INSTALLED" = false ]; then
    echo -e "${TURQUOISE}${BOLD}==>${RESET} ${WHITE}${BOLD}Attempting Python package installation via git...${RESET}"
    GIT_URL="git+https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
    if command -v uv >/dev/null 2>&1; then
        uv tool install "${GIT_URL}" --force
        INSTALLED=true
    elif command -v pipx >/dev/null 2>&1; then
        pipx install "${GIT_URL}" --force
        INSTALLED=true
    elif command -v pip3 >/dev/null 2>&1; then
        pip3 install --user --upgrade "${GIT_URL}"
        INSTALLED=true
    fi
fi

if [ "$INSTALLED" = false ]; then
    echo -e "${CORAL}${BOLD}[ERROR]${RESET} Failed to install PRUBETH CLI automatically."
    exit 1
fi

# Configure Shell Profile PATH
echo -e "${TURQUOISE}${BOLD}==>${RESET} ${WHITE}${BOLD}Configuring Environment PATH...${RESET}"
PATH_LINE="export PATH=\"${INSTALL_DIR}:\$PATH\""

for PROFILE_FILE in "${HOME}/.bashrc" "${HOME}/.zshrc" "${HOME}/.profile"; do
    if [ -f "${PROFILE_FILE}" ]; then
        if ! grep -q "${INSTALL_DIR}" "${PROFILE_FILE}"; then
            echo "" >> "${PROFILE_FILE}"
            echo "# PRUBETH CLI PATH" >> "${PROFILE_FILE}"
            echo "${PATH_LINE}" >> "${PROFILE_FILE}"
            echo -e "  ${DIM}Updated ${PROFILE_FILE}${RESET}"
        fi
    fi
done

export PATH="${INSTALL_DIR}:${PATH}"

# Verification
echo -e "${TURQUOISE}${BOLD}==>${RESET} ${WHITE}${BOLD}Verifying installation integrity...${RESET}"
if [ -x "${TARGET}" ]; then
    "${TARGET}" --version || true
elif command -v prubeth >/dev/null 2>&1; then
    prubeth --version || true
fi

echo ""
echo -e "${GOLD}${BOLD}╭─────────────────────────────────────────────────────────────────────────────╮${RESET}"
echo -e "${GOLD}${BOLD}│  ✔ PRUBETH CLI v1.3.1 Installation Completed Successfully!                  │${RESET}"
echo -e "${GOLD}${BOLD}├─────────────────────────────────────────────────────────────────────────────┤${RESET}"
echo -e "${GOLD}${BOLD}│${RESET}  ${WHITE}${BOLD}Command:${RESET}      ${TURQUOISE}prubeth${RESET} (Available globally in your terminal)${RESET}"
echo -e "${GOLD}${BOLD}│${RESET}  ${WHITE}${BOLD}Location:${RESET}     ${DIM}${INSTALL_DIR}${RESET}"
echo -e "${GOLD}${BOLD}│${RESET}  ${WHITE}${BOLD}Personal Hub:${RESET} ${AZURE}prubeth personal${RESET} (Configure keys & local models)${RESET}"
echo -e "${GOLD}${BOLD}│${RESET}  ${WHITE}${BOLD}Integrity:${RESET}    ${AZURE}prubeth integrity${RESET} (Cryptographic attestation pass)${RESET}"
echo -e "${GOLD}${BOLD}│${RESET}  ${WHITE}${BOLD}Diagnostic:${RESET}   ${AZURE}prubeth doctor${RESET} (9-Pillar qualification check)${RESET}"
echo -e "${GOLD}${BOLD}╰─────────────────────────────────────────────────────────────────────────────╯${RESET}"
echo ""
