#!/usr/bin/env bash
# Bootstrap cursor gate + completion policy on every cloud agent VM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pip_install_gate() {
  if python3 -m pip install -q -r requirements-gate.txt 2>/dev/null; then
    return 0
  fi
  python3 -m pip install -q --break-system-packages -r requirements-gate.txt
}

pip_install_gate

mkdir -p ~/.cursor/gate-logs ~/.cursor/gate-cache ~/.cursor/rules

cp -f "$ROOT/cursor_gate.py" "$ROOT/cursor_gate_fastest.py" ~/.cursor/
chmod +x ~/.cursor/cursor_gate.py ~/.cursor/cursor_gate_fastest.py

if [ -d "$ROOT/.cursor/rules" ]; then
  shopt -s nullglob
  for rule in "$ROOT/.cursor/rules/"*.mdc; do
    cp -f "$rule" ~/.cursor/rules/
  done
  shopt -u nullglob
fi

if [ -f "$ROOT/.cursorrules" ]; then
  cp -f "$ROOT/.cursorrules" ~/.cursor/.cursorrules.project
fi

SMOKE_FILE="$ROOT/samples/hello_passing.py"
if [ ! -f "$SMOKE_FILE" ]; then
  SMOKE_FILE="$ROOT/samples/hello.py"
fi

echo "Smoke testing gate reviewers on $SMOKE_FILE ..."
if ! bash "$ROOT/scripts/gate-file.sh" --file "$SMOKE_FILE"; then
  echo "Gate smoke test FAILED" >&2
  exit 1
fi

date -u +%Y-%m-%dT%H:%M:%SZ > ~/.cursor/.agent-policy-installed
echo "Agent policy installed at ~/.cursor/ ($(cat ~/.cursor/.agent-policy-installed))"
