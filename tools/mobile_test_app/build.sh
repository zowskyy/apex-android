#!/usr/bin/env bash
# Builds a real, minimal, installable, debuggable Android APK for testing
# APEX end-to-end — as opposed to tests/fixtures/sample_test.apk, which is a
# ZIP-shaped synthetic fixture (fake DEX/arsc bytes) good for zip_reader
# tests but NOT a valid Android app. This one actually installs and runs.
set -euo pipefail

SDK="${ANDROID_HOME:-$LOCALAPPDATA/Android/Sdk}"
BUILD_TOOLS="$SDK/build-tools/36.0.0"
PLATFORM_JAR="$SDK/platforms/android-36.1/android.jar"
JBR_HOME="/c/Program Files/Android/Android Studio/jbr"
JBR="$JBR_HOME/bin"
export JAVA_HOME="$(cygpath -w "$JBR_HOME")"
export PATH="$JBR:$PATH"

AAPT2="$BUILD_TOOLS/aapt2.exe"
D8="$BUILD_TOOLS/d8.bat"
ZIPALIGN="$BUILD_TOOLS/zipalign.exe"
APKSIGNER="$BUILD_TOOLS/apksigner.bat"
JAVAC="$JBR/javac.exe"
KEYTOOL="$JBR/keytool.exe"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$HERE/build"
OUT_DIR="$HERE/../../tests/fixtures"
OUT_APK="$OUT_DIR/apex_mobile_test.apk"

rm -rf "$BUILD"
mkdir -p "$BUILD/compiled_res" "$BUILD/gen" "$BUILD/obj" "$BUILD/dex" "$BUILD/out"
mkdir -p "$OUT_DIR"

echo "[1/7] aapt2 compile resources"
"$AAPT2" compile --dir "$HERE/res" -o "$BUILD/compiled_res/res.zip"

echo "[2/7] aapt2 link (manifest + resources -> base.apk, generates R.java)"
"$AAPT2" link \
  -o "$BUILD/out/base.apk" \
  -I "$PLATFORM_JAR" \
  --manifest "$HERE/AndroidManifest.xml" \
  -R "$BUILD/compiled_res/res.zip" \
  --java "$BUILD/gen" \
  --auto-add-overlay

echo "[3/7] javac (compile Java sources against android.jar + generated R.java)"
find "$HERE/src" "$BUILD/gen" -name "*.java" | while read -r f; do cygpath -w "$f"; done > "$BUILD/sources.txt"
"$JAVAC" -encoding UTF-8 \
  -classpath "$(cygpath -w "$PLATFORM_JAR")" \
  -d "$(cygpath -w "$BUILD/obj")" \
  @"$(cygpath -w "$BUILD/sources.txt")"

echo "[4/7] d8 (dex compile)"
find "$BUILD/obj" -name "*.class" | while read -r f; do cygpath -w "$f"; done > "$BUILD/classes.txt"
"$D8" --output "$(cygpath -w "$BUILD/dex")" --min-api 24 --lib "$(cygpath -w "$PLATFORM_JAR")" @"$(cygpath -w "$BUILD/classes.txt")"

echo "[5/7] inject classes.dex into base.apk"
python "$HERE/inject_dex.py" "$BUILD/out/base.apk" "$BUILD/dex/classes.dex" "$BUILD/out/unaligned.apk"

echo "[6/7] zipalign"
"$ZIPALIGN" -f -p 4 "$BUILD/out/unaligned.apk" "$BUILD/out/aligned.apk"

echo "[7/7] sign with debug key"
KEYSTORE="$HERE/debug.keystore"
if [ ! -f "$KEYSTORE" ]; then
  "$KEYTOOL" -genkeypair -v -keystore "$KEYSTORE" -storepass android -alias androiddebugkey \
    -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=APEX Debug,O=APEX,C=US"
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --out "$OUT_APK" "$BUILD/out/aligned.apk"

echo ""
echo "Built: $OUT_APK"
ls -la "$OUT_APK"
