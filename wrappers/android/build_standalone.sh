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

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for Chaquopy pip installs during the Gradle build." >&2
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

echo "==> Gradle assembleRelease (Chaquopy + embedded APEX)"
cd "$STANDALONE"
"$GRADLE" assembleRelease --no-daemon

BUILT="$STANDALONE/app/build/outputs/apk/release/app-release.apk"
if [[ ! -f "$BUILT" ]]; then
  echo "Expected APK missing: $BUILT" >&2
  exit 1
fi

cp -f "$BUILT" "$OUT_APK"
echo "Built: $OUT_APK"
ls -la "$OUT_APK"
