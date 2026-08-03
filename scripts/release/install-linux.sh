#!/usr/bin/env bash
# Offline install for APEX desktop release bundles (Linux).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.10+ required. Install python3 and re-run install.sh" >&2
  exit 1
fi

echo "==> Creating virtual environment"
"$PY" -m venv "$ROOT/.venv"
# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
pip install -q --upgrade pip wheel
pip install --no-index --find-links="$ROOT/wheels" "apex-android[mcp]"

echo "==> Linux menu entries"
chmod +x wrappers/linux/*.sh wrappers/lib/common.sh
mkdir -p "$HOME/.local/share/applications"
sed "s|%k|$ROOT|g" wrappers/linux/apex.desktop > "$HOME/.local/share/applications/apex.desktop"
sed "s|%k|$ROOT|g" wrappers/linux/apex-mobile.desktop > \
  "$HOME/.local/share/applications/apex-mobile.desktop"

echo ""
echo "APEX installed."
echo "  $ROOT/wrappers/linux/apex-gui.sh"
echo "  $ROOT/wrappers/linux/apex-mobile.sh"
echo "  $ROOT/.venv/bin/apex doctor"
