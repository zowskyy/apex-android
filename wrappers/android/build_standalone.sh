#!/usr/bin/env bash
# Build the full on-device APEX APK (embedded Python engine via Chaquopy).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../" && pwd)"
STANDALONE="$HERE/standalone"
OUT_APK="$HERE/dist/apex-mobile.apk"
GRADLE="${APEX_GRADLE:-gradle}"

if ! command -v "$GRADLE" >/dev/null 2>&1; then
  echo "Gradle not found. Install Gradle 8.x or set APEX_GRADLE." >&2
  echo "  https://gradle.org/install/" >&2
  exit 1
fi

if ! command -v python3.10 >/dev/null 2>&1; then
  echo "python3.10 is required for Chaquopy pip installs (must match app Python 3.10)." >&2
  exit 1
fi

export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"

if [[ ! -d "$ANDROID_HOME" ]]; then
  echo "Android SDK not found at: $ANDROID_HOME" >&2
  echo "Set ANDROID_HOME before building the standalone APK." >&2
  exit 1
fi

mkdir -p "$HERE/dist"

# Chaquopy reads src/main/python — symlink apex package only (not whole repo).
PY_SRC="$STANDALONE/app/src/main/python"
mkdir -p "$PY_SRC"
rm -f "$PY_SRC/apex"
ln -sfn "$ROOT/apex" "$PY_SRC/apex"

if ! command -v python3.10 >/dev/null 2>&1; then
  echo "python3.10 is required for Chaquopy (must match app Python 3.10)." >&2
  echo "Install Python 3.10 or set buildPython in app/build.gradle." >&2
  exit 1
fi

export GRADLE_VERSION="${APEX_GRADLE_VERSION:-8.10.2}"

echo "==> Gradle assembleRelease (Chaquopy 17 + embedded APEX)"
cd "$STANDALONE"

if [[ ! -x ./gradlew ]]; then
  echo "Generating Gradle wrapper ($GRADLE_VERSION)"
  gradle wrapper --gradle-version "$GRADLE_VERSION" --no-daemon
fi

./gradlew clean assembleRelease --no-daemon

echo "==> Chaquopy import smoke test (same env as on-device engine)"
chmod +x "$ROOT/scripts/smoke_android_engine_imports.sh"
bash "$ROOT/scripts/smoke_android_engine_imports.sh"

BUILT="$STANDALONE/app/build/outputs/apk/release/app-release.apk"
if [[ ! -f "$BUILT" ]]; then
  echo "Expected APK missing: $BUILT" >&2
  exit 1
fi

cp -f "$BUILT" "$OUT_APK"
echo "Built: $OUT_APK"
ls -la "$OUT_APK"
