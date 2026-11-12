#!/usr/bin/env bash
# CodeGraph One-Command Installer for AI Coding Agents
# Installs CodeGraph Engine and automatically configures Claude, Cursor, Antigravity, Cline, and Codex.
set -e

REPO="raghurammrsd/CODEGRAPH_MCP"
INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="codegraph"
BINARY_PATH="${INSTALL_DIR}/${BINARY_NAME}"

echo "=========================================================="
echo "Installing CodeGraph Engine & MCP Server (Production Grade)"
echo "=========================================================="

# Create local bin if not exists
mkdir -p "${INSTALL_DIR}"

# Detect OS and Architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

if [ "$ARCH" = "x86_64" ]; then
    ARCH="amd64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    ARCH="arm64"
fi

echo "-> Detected Platform: ${OS} (${ARCH})"

# Install using uv / python pip if available, or direct binary download
if command -v uv >/dev/null 2>&1; then
    echo "-> Installing via uv tool..."
    uv tool install --force "codegraph-engine>=3.0.3"
elif command -v pip3 >/dev/null 2>&1; then
    echo "-> Installing via pip3..."
    pip3 install --upgrade "codegraph-engine>=3.0.3"
elif command -v python3 >/dev/null 2>&1; then
    echo "-> Installing via python3 -m pip..."
    python3 -m pip install --upgrade "codegraph-engine>=3.0.3"
else
    echo "-> Downloading standalone zero-dependency binary..."
    RELEASE_URL="https://github.com/${REPO}/releases/latest/download/codegraph-${OS}-${ARCH}"
    curl -fsSL "${RELEASE_URL}" -o "${BINARY_PATH}" || {
        echo "Error: Failed to download prebuilt binary from ${RELEASE_URL}"
        exit 1
    }
    chmod +x "${BINARY_PATH}"
fi

# Ensure install dir is in PATH
if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
    export PATH="${INSTALL_DIR}:${PATH}"
fi

echo "-> Verifying CodeGraph installation..."
if command -v codegraph >/dev/null 2>&1; then
    CODEGRAPH_CMD="codegraph"
elif [ -f "${BINARY_PATH}" ]; then
    CODEGRAPH_CMD="${BINARY_PATH}"
else
    CODEGRAPH_CMD="python3 -m codegraph"
fi

${CODEGRAPH_CMD} --version

echo ""
echo "-> Automatically configuring AI Coding Clients (Antigravity, Cursor, Claude Desktop, Cline)..."
${CODEGRAPH_CMD} install -y --target all

echo ""
echo "=========================================================="
echo "CodeGraph successfully installed and configured!"
echo "Run 'codegraph mcp doctor' anytime to verify connection."
echo "=========================================================="
