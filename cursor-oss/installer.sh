#!/bin/bash
# installer.sh - Complete setup in one command
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Cursor OSS — Free Coding Agent ║${NC}"
echo -e "${CYAN}║  No subscription. Fully offline.║${NC}"
echo -e "${CYAN}╚══════════════════════════════════╝${NC}"
echo ""

OS="$(uname -s)"
ARCH="$(uname -m)"
echo -e "${YELLOW}System:${NC} $OS | $ARCH"

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js required. Install: https://nodejs.org (v16+)${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Node $(node -v)${NC}"

if ! command -v curl &> /dev/null; then
    echo -e "${RED}❌ curl required for model download${NC}"
    exit 1
fi
echo -e "${GREEN}✅ curl found${NC}"

echo ""
echo "📦 Installing dependencies..."
npm install --production
echo -e "${GREEN}✅ Dependencies installed${NC}"

mkdir -p models projects

if command -v llama-cli &> /dev/null || command -v llama.cpp &> /dev/null; then
    echo -e "${GREEN}✅ llama.cpp found${NC}"
else
    echo -e "${YELLOW}⚠️  llama.cpp not found. Install from: https://github.com/ggerganov/llama.cpp${NC}"
    echo "   macOS: brew install llama.cpp | Linux: build from source"
fi

MODEL="codeqwen-7b-q4.gguf"
MODEL_PATH="models/$MODEL"

if [ ! -f "$MODEL_PATH" ]; then
    echo ""
    echo "📥 Downloading model (one-time, ~4GB)..."
    echo "   Works fully offline after this."
    echo ""

    MODEL_URL="https://huggingface.co/TheBloke/CodeQwen1.5-7B-Chat-GGUF/resolve/main/codeqwen-1_5-7b-chat-q4_k_m.gguf"
    curl -L "$MODEL_URL" -o "$MODEL_PATH" --progress-bar
    echo -e "${GREEN}✅ Model downloaded${NC}"
else
    echo -e "${GREEN}✅ Model already exists${NC}"
fi

echo ""
echo "🧪 Running pipeline tests..."
node tests/benchmark.js

echo ""
echo -e "${GREEN}╔══════════════════════════════════╗${NC}"
echo -e "${GREEN}║      Setup Complete! 🎉          ║${NC}"
echo -e "${GREEN}║                                  ║${NC}"
echo -e "${GREEN}║  Start server + web UI:          ║${NC}"
echo -e "${GREEN}║  node server/inference.js        ║${NC}"
echo -e "${GREEN}║                                  ║${NC}"
echo -e "${GREEN}║  CLI (direct):                   ║${NC}"
echo -e "${GREEN}║  node ui/cli.js \"build a...\"     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════╝${NC}"
