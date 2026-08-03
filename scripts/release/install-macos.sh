#!/usr/bin/env bash
# Offline install for APEX desktop release bundles (macOS).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.10+ required." >&2
  exit 1
fi

echo "==> Creating virtual environment"
"$PY" -m venv "$ROOT/.venv"
# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
pip install -q --upgrade pip wheel
pip install --no-index --find-links="$ROOT/wheels" "apex-android[mcp]"

echo "==> macOS app bundles"
chmod +x wrappers/macos/*.command wrappers/macos/create-apps.sh wrappers/lib/common.sh
wrappers/macos/create-apps.sh

echo ""
echo "APEX installed."
echo "  open $ROOT/wrappers/macos/dist/APEX.app"
echo "  open $ROOT/wrappers/macos/dist/APEX\ Mobile.app"
echo "  $ROOT/.venv/bin/apex doctor"
