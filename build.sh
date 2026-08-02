#!/usr/bin/env bash
# Build APEX — Python package, Rust extensions, optional wrappers.
#
# Usage:
#   ./build.sh                 # dev install + native extensions + tests
#   ./build.sh --release       # same, optimized Rust builds
#   ./build.sh --android       # also build Android client APK (needs SDK)
#   ./build.sh --macos-apps    # also build macOS .app bundles (macOS only)
#   ./build.sh --docker        # also build Docker image
#   ./build.sh --skip-tests    # skip pytest / cargo test
#   ./build.sh --help
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
MATURIN="$VENV/bin/maturin"
RUST_PROFILE="dev"
DO_ANDROID=0
DO_MACOS_APPS=0
DO_DOCKER=0
SKIP_TESTS=0

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release) RUST_PROFILE="release" ;;
    --android) DO_ANDROID=1 ;;
    --macos-apps) DO_MACOS_APPS=1 ;;
    --docker) DO_DOCKER=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

step() { echo ""; echo "==> $*"; }

step "Python virtual environment"
if [[ ! -x "$PY" ]]; then
  python3 -m venv "$VENV"
fi
"$PIP" install -q --upgrade pip wheel
"$PIP" install -q -e ".[dev,mcp]"

step "Rust toolchain check"
if ! command -v rustc >/dev/null 2>&1; then
  echo "Rust not found. Install: https://rustup.rs" >&2
  exit 1
fi

if [[ ! -x "$MATURIN" ]]; then
  "$PIP" install -q maturin
fi

step "Native extensions (apex_zip_reader, apex_dex_reader)"
Maturin_ARGS=()
if [[ "$RUST_PROFILE" == "release" ]]; then
  Maturin_ARGS+=(--release)
fi
"$MATURIN" develop "${Maturin_ARGS[@]}" -m core/zip_reader/Cargo.toml
"$MATURIN" develop "${Maturin_ARGS[@]}" -m core/dex_reader/Cargo.toml

step "Rust workspace tests"
cargo test --workspace

if [[ "$SKIP_TESTS" -eq 0 ]]; then
  step "Python lint (ruff)"
  "$VENV/bin/ruff" check apex tests

  step "Python tests (pytest)"
  "$PY" -m pytest -q
fi

if [[ "$DO_MACOS_APPS" -eq 1 ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    step "macOS .app bundles"
    chmod +x wrappers/macos/*.command wrappers/macos/create-apps.sh
    wrappers/macos/create-apps.sh
  else
    echo "Skipping macOS apps (not on macOS)" >&2
  fi
fi

if [[ "$DO_ANDROID" -eq 1 ]]; then
  step "Android client APK"
  bash wrappers/android/build.sh
fi

if [[ "$DO_DOCKER" -eq 1 ]]; then
  step "Docker image"
  if command -v docker >/dev/null 2>&1; then
    docker build -f wrappers/docker/Dockerfile -t apex-android:local "$ROOT"
  else
    echo "Docker not found — skip image build" >&2
  fi
fi

step "Done"
echo ""
echo "APEX is ready."
echo "  $VENV/bin/apex doctor"
echo "  $VENV/bin/apex gui"
echo "  $VENV/bin/apex mobile          # phone browser on LAN"
echo "  wrappers/README.md             # platform app wrappers"
if [[ -f wrappers/android/dist/apex-client.apk ]]; then
  echo "  wrappers/android/dist/apex-client.apk"
fi
if [[ -d wrappers/macos/dist ]]; then
  echo "  wrappers/macos/dist/APEX.app"
fi
