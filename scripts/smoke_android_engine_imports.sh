#!/usr/bin/env bash
# Verify Chaquopy bundled Python assets into the release APK.
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
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
unzip -q "$APK" -d "$tmpdir"

apk_size="$(stat -c%s "$APK")"
if [[ "$apk_size" -lt 35000000 ]]; then
  echo "  FAIL APK too small (${apk_size} bytes) — engine probably not bundled" >&2
  exit 1
fi
echo "  ok  APK size ${apk_size} bytes"

if [[ ! -d "$tmpdir/assets/chaquopy" ]]; then
  echo "  FAIL missing assets/chaquopy in APK" >&2
  exit 1
fi
echo "  ok  chaquopy assets present"

search_tree() {
  local pattern="$1"
  if find "$tmpdir" -iname "*${pattern}*" 2>/dev/null | grep -q .; then
    return 0
  fi
  if unzip -l "$APK" 2>/dev/null | grep -qi "$pattern"; then
    return 0
  fi
  local archive
  while IFS= read -r archive; do
    if unzip -l "$archive" 2>/dev/null | grep -qi "$pattern"; then
      return 0
    fi
  done < <(find "$tmpdir" -type f \( -name '*.zip' -o -name '*.whl' \) 2>/dev/null)
  return 1
}

check_in_apk() {
  local label="$1"
  local pattern="$2"
  if search_tree "$pattern"; then
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
check_in_apk "apex sources" "apex" || failed=1
check_in_apk "mutf8 shim" "mutf8" || failed=1

if [[ "$failed" -ne 0 ]]; then
  echo ""
  echo "APK Python bundle smoke test FAILED."
  echo "Add missing packages to app/build.gradle chaquopy.pip or vendor pure-Python shims."
  exit 1
fi

echo "APK Python bundle smoke test passed."
