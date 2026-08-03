#!/usr/bin/env bash
# Copy Android release artifacts with stable download names.
#
# Usage: scripts/package_android_release.sh <version>
# Expects:
#   wrappers/android/dist/apex-mobile.apk
#   wrappers/android/standalone/app/build/outputs/bundle/release/app-release.aab (optional)
set -euo pipefail

VERSION="${1:?version required (e.g. 0.4.1)}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/release-staging/android"
rm -rf "$OUT"
mkdir -p "$OUT"

APK_SRC="$ROOT/wrappers/android/dist/apex-mobile.apk"
AAB_SRC="$ROOT/wrappers/android/standalone/app/build/outputs/bundle/release/app-release.aab"

if [[ ! -f "$APK_SRC" ]]; then
  echo "Missing APK: $APK_SRC" >&2
  exit 1
fi

cp "$APK_SRC" "$OUT/APEX-Mobile-${VERSION}.apk"
cp scripts/release/INSTALL.txt "$OUT/INSTALL.txt"

if [[ -f "$AAB_SRC" ]]; then
  cp "$AAB_SRC" "$OUT/APEX-Mobile-${VERSION}.aab"
  echo "Included AAB bundle"
else
  echo "AAB not found (optional): $AAB_SRC"
fi

ZIP_FILES=("APEX-Mobile-${VERSION}.apk" "INSTALL.txt")
if [[ -f "$OUT/APEX-Mobile-${VERSION}.aab" ]]; then
  ZIP_FILES+=("APEX-Mobile-${VERSION}.aab")
fi
(
  cd "$OUT"
  zip -j "APEX-Mobile-${VERSION}-android.zip" "${ZIP_FILES[@]}"
)

ls -la "$OUT"
