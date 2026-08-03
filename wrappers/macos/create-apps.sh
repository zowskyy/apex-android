#!/usr/bin/env bash
# Build double-clickable macOS .app bundles for APEX.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
OUT="$ROOT/wrappers/macos/dist"

build_app() {
  local name="$1"
  local script="$2"
  local app_dir="$OUT/$name.app"
  rm -rf "$app_dir"
  mkdir -p "$app_dir/Contents/MacOS" "$app_dir/Contents/Resources"
  cp "$script" "$app_dir/Contents/MacOS/run"
  chmod +x "$app_dir/Contents/MacOS/run"
  cat > "$app_dir/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleExecutable</key><string>run</string>
  <key>CFBundleIdentifier</key><string>io.apex.${name}</string>
  <key>CFBundleName</key><string>${name}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.4.1</string>
  <key>CFBundleVersion</key><string>0.4.1</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
EOF
  echo "Built $app_dir"
}

build_app "APEX" "$ROOT/wrappers/macos/apex-gui.command"
build_app "APEX Mobile" "$ROOT/wrappers/macos/apex-mobile.command"
echo "Open wrappers/macos/dist/APEX.app or APEX Mobile.app"
