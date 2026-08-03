#!/usr/bin/env bash
# Verify Chaquopy bundled the Python engine into the release APK.
# Host-side import of arm64 wheels is unreliable; inspect APK contents instead.
#
# Usage: scripts/smoke_android_engine_imports.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STANDALONE="$ROOT/wrappers/android/standalone"
APK="$STANDALONE/app/build/outputs/apk/release/app-release.apk"
PY_SRC="$STANDALONE/app/src/main/python"

if [[ ! -f "$APK" ]]; then
  echo "smoke_android_engine_imports: APK missing — build first." >&2
  exit 1
fi

if [[ ! -d "$PY_SRC/apex" ]]; then
  echo "smoke_android_engine_imports: missing $PY_SRC/apex" >&2
  exit 1
fi

echo "==> APK Python bundle smoke test ($APK)"
LIST="$(unzip -l "$APK")"

check_in_apk() {
  local label="$1"
  local pattern="$2"
  if echo "$LIST" | grep -qi "$pattern"; then
    echo "  ok  $label"
  else
    echo "  FAIL $label (pattern: $pattern)"
    return 1
  fi
}

failed=0
check_in_apk "markupsafe" "markupsafe" || failed=1
check_in_apk "jinja2" "jinja2" || failed=1
check_in_apk "androguard" "androguard" || failed=1
check_in_apk "loguru" "loguru" || failed=1
check_in_apk "apex sources" "chaquopy/app/apex" || check_in_apk "apex sources" "apex/" || failed=1
check_in_apk "mutf8 shim" "mutf8" || failed=1

if [[ "$failed" -ne 0 ]]; then
  echo ""
  echo "APK Python bundle smoke test FAILED."
  echo "Add missing packages to app/build.gradle chaquopy.pip or vendor pure-Python shims."
  exit 1
fi

echo "APK Python bundle smoke test passed."
