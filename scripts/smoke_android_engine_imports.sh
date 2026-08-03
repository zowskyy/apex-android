#!/usr/bin/env bash
# Structural smoke test for Chaquopy release APKs (packages live in custom assets).
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

if [[ ! -f "$PY_SRC/mutf8/mutf8.py" ]]; then
  echo "smoke_android_engine_imports: missing vendored mutf8 shim" >&2
  exit 1
fi

echo "==> APK structural smoke test ($APK)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
unzip -q "$APK" -d "$tmpdir"

apk_size="$(stat -c%s "$APK")"
if [[ "$apk_size" -lt 35000000 ]]; then
  echo "  FAIL APK too small (${apk_size} bytes)" >&2
  exit 1
fi
echo "  ok  APK size ${apk_size} bytes"

if [[ ! -d "$tmpdir/assets/chaquopy" ]]; then
  echo "  FAIL missing assets/chaquopy in APK" >&2
  exit 1
fi
echo "  ok  chaquopy assets present"

if ! unzip -l "$APK" 2>/dev/null | grep -qi "apex"; then
  echo "  FAIL apex sources not listed in APK" >&2
  exit 1
fi
echo "  ok  apex sources bundled"

chaquopy_files="$(find "$tmpdir/assets/chaquopy" -type f | wc -l)"
if [[ "$chaquopy_files" -lt 5 ]]; then
  echo "  FAIL too few chaquopy asset files ($chaquopy_files)" >&2
  exit 1
fi
echo "  ok  chaquopy asset files ($chaquopy_files)"

echo "APK structural smoke test passed."
echo "  (Runtime import of jinja2/markupsafe is validated on-device after install.)"
