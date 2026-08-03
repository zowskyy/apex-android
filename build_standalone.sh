#!/usr/bin/env bash
# Build the full on-device APEX Mobile APK (apex-mobile.apk).
# Guide: docs/BUILD_STANDALONE_APK.md
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$ROOT/wrappers/android/build_standalone.sh"
