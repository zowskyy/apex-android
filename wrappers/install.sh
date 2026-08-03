#!/usr/bin/env bash
# Install APEX wrappers for the current platform (Linux or macOS).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Installing APEX Python package"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip wheel
.venv/bin/pip install -q -e ".[mcp]"

if command -v maturin >/dev/null 2>&1 || .venv/bin/pip install -q maturin; then
  echo "==> Building native extensions"
  .venv/bin/maturin develop --release -m core/zip_reader/Cargo.toml
  .venv/bin/maturin develop --release -m core/dex_reader/Cargo.toml
fi

OS="$(uname -s)"
case "$OS" in
  Linux)
    echo "==> Linux desktop entries"
    chmod +x wrappers/linux/*.sh
    mkdir -p "$HOME/.local/share/applications"
    sed "s|%k|$ROOT|g" wrappers/linux/apex.desktop > "$HOME/.local/share/applications/apex.desktop"
    sed "s|%k|$ROOT|g" wrappers/linux/apex-mobile.desktop > "$HOME/.local/share/applications/apex-mobile.desktop"
    echo "Installed: APEX and APEX Mobile in application menu"
    ;;
  Darwin)
    echo "==> macOS app bundles"
    chmod +x wrappers/macos/*.command wrappers/macos/create-apps.sh
    wrappers/macos/create-apps.sh
    echo "Built: wrappers/macos/dist/APEX.app and APEX Mobile.app"
    ;;
  *)
    echo "Desktop shortcuts skipped on $OS — use wrappers/linux/*.sh manually"
    ;;
esac

echo ""
echo "Done. Run:"
echo "  $ROOT/wrappers/linux/apex-gui.sh     # or apex gui"
echo "  $ROOT/wrappers/linux/apex-mobile.sh # or apex mobile"
