#!/usr/bin/env bash
# Build the APEX Android client APK (WebView shell for apex mobile server).
set -euo pipefail

SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
BUILD_TOOLS_VERSION="${APEX_BUILD_TOOLS:-}"
PLATFORM="${APEX_ANDROID_PLATFORM:-android-34}"
MIN_API="${APEX_MIN_API:-24}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../" && pwd)"
BUILD="$HERE/build"
OUT_APK="$HERE/dist/apex-client.apk"
INJECT="$ROOT/tools/mobile_test_app/inject_dex.py"

# Export so aapt2/d8/apksigner resolve consistently (no Gradle/NDK in this script).
export ANDROID_HOME="$SDK"
export ANDROID_SDK_ROOT="$SDK"

if [[ -z "$BUILD_TOOLS_VERSION" ]]; then
  if [[ -d "$SDK/build-tools" ]]; then
    BUILD_TOOLS_VERSION="$(basename "$(ls -d "$SDK"/build-tools/* 2>/dev/null | sort -V | tail -1)")"
  fi
  BUILD_TOOLS_VERSION="${BUILD_TOOLS_VERSION:-34.0.0}"
fi

pick_tool() {
  local name="$1"
  if [[ -n "${JAVA_HOME:-}" && -x "$JAVA_HOME/bin/$name" ]]; then
    echo "$JAVA_HOME/bin/$name"
  elif command -v "$name" >/dev/null 2>&1; then
    echo "$name"
  elif [[ -x "$BUILD_TOOLS/$name" ]]; then
    echo "$BUILD_TOOLS/$name"
  elif [[ -x "$BUILD_TOOLS/${name}.exe" ]]; then
    echo "$BUILD_TOOLS/${name}.exe"
  elif [[ -x "$BUILD_TOOLS/${name}.bat" ]]; then
    echo "$BUILD_TOOLS/${name}.bat"
  else
    echo "Missing Android/JDK tool: $name (set ANDROID_HOME / JAVA_HOME)" >&2
    exit 1
  fi
}

if [[ ! -d "$SDK" ]]; then
  echo "Android SDK not found at: $SDK" >&2
  echo "Set ANDROID_HOME or ANDROID_SDK_ROOT to your SDK root." >&2
  echo "Example: export ANDROID_HOME=\"\$HOME/Android/Sdk\"" >&2
  exit 1
fi

BUILD_TOOLS="$SDK/build-tools/$BUILD_TOOLS_VERSION"
PLATFORM_JAR="$SDK/platforms/$PLATFORM/android.jar"
if [[ ! -f "$PLATFORM_JAR" && -f "$SDK/platforms/android-36.1/android.jar" ]]; then
  PLATFORM="android-36.1"
  PLATFORM_JAR="$SDK/platforms/$PLATFORM/android.jar"
  echo "Using fallback platform: $PLATFORM"
fi

if [[ ! -f "$PLATFORM_JAR" ]]; then
  echo "Platform jar missing. Install platform ${APEX_ANDROID_PLATFORM:-android-34} via sdkmanager." >&2
  echo "SDK root: $SDK" >&2
  exit 1
fi

if [[ ! -d "$BUILD_TOOLS" ]]; then
  echo "Build-tools $BUILD_TOOLS_VERSION not found under $SDK/build-tools" >&2
  echo "Install with: sdkmanager \"build-tools;$BUILD_TOOLS_VERSION\"" >&2
  exit 1
fi

AAPT2="$(pick_tool aapt2)"
D8="$(pick_tool d8)"
ZIPALIGN="$(pick_tool zipalign)"
APKSIGNER="$(pick_tool apksigner)"
JAVAC="$(pick_tool javac)"
KEYTOOL="$(pick_tool keytool)"

rm -rf "$BUILD"
mkdir -p "$BUILD/compiled_res" "$BUILD/gen" "$BUILD/obj" "$BUILD/dex" "$BUILD/out" "$HERE/dist"

echo "[1/7] aapt2 compile"
"$AAPT2" compile --dir "$HERE/res" -o "$BUILD/compiled_res/res.zip"

echo "[2/7] aapt2 link"
"$AAPT2" link \
  -o "$BUILD/out/base.apk" \
  -I "$PLATFORM_JAR" \
  --manifest "$HERE/AndroidManifest.xml" \
  -R "$BUILD/compiled_res/res.zip" \
  --java "$BUILD/gen" \
  --auto-add-overlay \
  --min-sdk-version "$MIN_API"

echo "[3/7] javac"
mapfile -t SOURCES < <(find "$HERE/src" "$BUILD/gen" -name "*.java")
"$JAVAC" -encoding UTF-8 -classpath "$PLATFORM_JAR" -d "$BUILD/obj" "${SOURCES[@]}"

echo "[4/7] d8"
mapfile -t CLASSES < <(find "$BUILD/obj" -name "*.class")
"$D8" --output "$BUILD/dex" --min-api "$MIN_API" --lib "$PLATFORM_JAR" "${CLASSES[@]}"

echo "[5/7] inject dex"
python3 "$INJECT" "$BUILD/out/base.apk" "$BUILD/dex/classes.dex" "$BUILD/out/unaligned.apk"

echo "[6/7] zipalign"
"$ZIPALIGN" -f -p 4 "$BUILD/out/unaligned.apk" "$BUILD/out/aligned.apk"

echo "[7/7] sign"
KEYSTORE="$HERE/debug.keystore"
if [[ ! -f "$KEYSTORE" ]]; then
  "$KEYTOOL" -genkeypair -v -keystore "$KEYSTORE" -storepass android -alias androiddebugkey \
    -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=APEX Client,O=APEX,C=US"
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --out "$OUT_APK" "$BUILD/out/aligned.apk"

echo "Built: $OUT_APK"
ls -la "$OUT_APK"
