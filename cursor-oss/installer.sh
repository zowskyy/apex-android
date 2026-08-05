#!/bin/bash
# installer.sh - Complete offline setup for Cursor OSS
# Works on Linux, macOS, Windows (via Git Bash/WSL), and Raspberry Pi

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Cursor OSS - Free Coding Agent Setup   ║${NC}"
echo -e "${GREEN}║   Zero subscription. Fully offline.      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# Detect OS and architecture
OS="$(uname -s)"
ARCH="$(uname -m)"
RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || echo "4")

echo -e "${YELLOW}System:${NC} $OS | $ARCH | ~${RAM_GB}GB RAM"
echo ""

# Check prerequisites
command -v node >/dev/null 2>&1 || { echo -e "${RED}Node.js required. Install from https://nodejs.org${NC}"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo -e "${RED}npm required.${NC}"; exit 1; }

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 16 ]; then
    echo -e "${RED}Node.js 16+ required. Current: $(node -v)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Node.js $(node -v) detected${NC}"

# Install dependencies
echo ""
echo "📦 Installing npm dependencies..."
npm install

# Create models directory
mkdir -p models

# Select model based on available RAM
MODEL="codeqwen-7b-q4.gguf"
if [ "$RAM_GB" -le 4 ]; then
    MODEL="deepseek-coder-6.7b-q4.gguf"
    echo -e "${YELLOW}⚠️  Low RAM detected. Using smaller model.${NC}"
fi

# Download model
MODEL_PATH="models/$MODEL"
if [ ! -f "$MODEL_PATH" ]; then
    echo ""
    echo "📥 Downloading $MODEL (one-time, works offline after)..."
    echo ""
    
    case $MODEL in
        "codeqwen-7b-q4.gguf")
            URL="https://huggingface.co/TheBloke/CodeQwen1.5-7B-Chat-GGUF/resolve/main/codeqwen-1_5-7b-chat-q4_k_m.gguf"
            ;;
        "deepseek-coder-6.7b-q4.gguf")
            URL="https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
            ;;
        "starcoder2-7b-q4.gguf")
            URL="https://huggingface.co/TheBloke/StarCoder2-7B-GGUF/resolve/main/starcoder2-7b.Q4_K_M.gguf"
            ;;
    esac
    
    curl -L "$URL" -o "$MODEL_PATH" --progress-bar
    echo -e "${GREEN}✅ Model downloaded${NC}"
else
    echo -e "${GREEN}✅ Model already exists${NC}"
fi

# Create VS Code extension symlink (optional)
VSCODE_EXT_DIR=""
if [ -d "$HOME/.vscode/extensions" ]; then
    VSCODE_EXT_DIR="$HOME/.vscode/extensions/cursor-oss"
elif [ -d "$HOME/.vscode-oss/extensions" ]; then
    VSCODE_EXT_DIR="$HOME/.vscode-oss/extensions/cursor-oss"
fi

if [ -n "$VSCODE_EXT_DIR" ]; then
    echo ""
    echo "🔌 Linking VS Code extension..."
    rm -rf "$VSCODE_EXT_DIR"
    ln -s "$(pwd)" "$VSCODE_EXT_DIR"
    echo -e "${GREEN}✅ VS Code extension linked${NC}"
fi

# Run tests
echo ""
echo "🧪 Running benchmark tests..."
node test-agent.js

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Installation Complete! 🎉         ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
echo -e "${GREEN}║  Run: node arc-agent.js                  ║${NC}"
echo -e "${GREEN}║  Test: node test-agent.js                ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
echo -e "${GREEN}║  No subscription. No cloud. All local.   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
