#!/usr/bin/env bash
# Build APEX — Python package, Rust extensions, optional wrappers.
#
# Usage:
#   ./build.sh                 # dev install + native extensions + tests
#   ./build.sh --release       # same, optimized Rust builds
#   ./build.sh --android       # also build Android client APK (needs SDK)
  ./build.sh --android-standalone  # full on-device phone APK (Gradle + Chaquopy)
#   ./build.sh --macos-apps    # also build macOS .app bundles (macOS only)
#   ./build.sh --docker        # also build Docker image
#   ./build.sh --skip-tests    # skip cargo test, ruff, and pytest
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
DO_ANDROID_STANDALONE=0
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
    --android-standalone) DO_ANDROID_STANDALONE=1 ;;
    --macos-apps) DO_MACOS_APPS=1 ;;
    --docker) DO_DOCKER=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

step() { echo ""; echo "==> $*"; }

ensure_android_sdk() {
  local sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
  if [[ ! -d "$sdk" ]]; then
    echo "Android SDK not found at: $sdk" >&2
    echo "Export ANDROID_HOME or ANDROID_SDK_ROOT before --android." >&2
    echo "Example: export ANDROID_HOME=\"\$HOME/Android/Sdk\"" >&2
    exit 1
  fi
  export ANDROID_HOME="$sdk"
  export ANDROID_SDK_ROOT="$sdk"
  echo "ANDROID_HOME=$ANDROID_HOME"
  if [[ -n "${ANDROID_NDK_HOME:-}" ]]; then
    echo "ANDROID_NDK_HOME=$ANDROID_NDK_HOME (not required for apex-client WebView APK)"
  fi
}

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
MATURIN_ARGS=()
if [[ "$RUST_PROFILE" == "release" ]]; then
  MATURIN_ARGS+=(--release)
fi
"$MATURIN" develop "${MATURIN_ARGS[@]}" -m core/zip_reader/Cargo.toml
"$MATURIN" develop "${MATURIN_ARGS[@]}" -m core/dex_reader/Cargo.toml

if [[ "$SKIP_TESTS" -eq 0 ]]; then
  step "Rust workspace tests"
  cargo test --workspace

  step "Python lint (ruff)"
  "$VENV/bin/ruff" check apex tests

  step "Python tests (pytest)"
  "$PY" -m pytest -q
else
  echo "Skipping cargo test, ruff, and pytest (--skip-tests)"
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

ANDROID_APK="$ROOT/wrappers/android/dist/apex-client.apk"
MOBILE_APK="$ROOT/wrappers/android/dist/apex-mobile.apk"
if [[ "$DO_ANDROID" -eq 1 ]]; then
  step "Android client APK"
  ensure_android_sdk
  bash wrappers/android/build.sh
  if [[ ! -f "$ANDROID_APK" ]]; then
    echo "Android build finished but APK missing: $ANDROID_APK" >&2
    exit 1
  fi
  ls -la "$ANDROID_APK"
fi

if [[ "$DO_ANDROID_STANDALONE" -eq 1 ]]; then
  step "Android standalone APK (on-device engine)"
  ensure_android_sdk
  chmod +x wrappers/android/build_standalone.sh
  bash wrappers/android/build_standalone.sh
  if [[ ! -f "$MOBILE_APK" ]]; then
    echo "Standalone build finished but APK missing: $MOBILE_APK" >&2
    exit 1
  fi
  ls -la "$MOBILE_APK"
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
if [[ -f "$ANDROID_APK" ]]; then
  echo "  $ANDROID_APK                 # thin companion client"
  echo "  adb install -r $ANDROID_APK"
fi
if [[ -f "$MOBILE_APK" ]]; then
  echo "  $MOBILE_APK                  # full on-device engine"
  echo "  adb install -r $MOBILE_APK"
fi
if [[ -d wrappers/macos/dist ]]; then
  echo "  wrappers/macos/dist/APEX.app"
fi
echo ""
echo "Before push: scripts/hard_gate.sh  (or scripts/validate_slice.sh)"
echo "After push:  scripts/hard_gate.sh --ship"
