#!/usr/bin/env bash
# Stage a desktop release folder with pre-built wheels and offline install scripts.
#
# Usage: scripts/package_desktop_release.sh <version> <platform>
#   platform: linux | windows | macos
#
# CI sets CORE_WHEEL_DIR to a folder of pre-built wheels from the core-build matrix.
# Local dev omits CORE_WHEEL_DIR and builds from source.
set -euo pipefail

VERSION="${1:?version required (e.g. 0.4.1)}"
PLATFORM="${2:?platform required: linux|windows|macos}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

case "$PLATFORM" in
  linux) SUFFIX="linux-x64" ;;
  windows) SUFFIX="windows-x64" ;;
  macos) SUFFIX="macos" ;;
  *)
    echo "Unknown platform: $PLATFORM" >&2
    exit 1
    ;;
esac

STAGE_NAME="APEX-${VERSION}-${SUFFIX}"
STAGE="$ROOT/release-staging/${STAGE_NAME}"
rm -rf "$STAGE"
mkdir -p "$STAGE/wheels"

if [[ -n "${CORE_WHEEL_DIR:-}" && -d "$CORE_WHEEL_DIR" ]] && compgen -G "$CORE_WHEEL_DIR/*.whl" > /dev/null; then
  echo "==> Using pre-built wheels from $CORE_WHEEL_DIR"
  cp "$CORE_WHEEL_DIR"/*.whl "$STAGE/wheels/"
elif [[ -n "${CORE_WHEEL:-}" ]]; then
  first_wheel=$(echo "$CORE_WHEEL" | awk '{print $1}')
  if [[ -f "$first_wheel" ]]; then
    echo "==> Using CORE_WHEEL: $CORE_WHEEL"
    # shellcheck disable=SC2086
    cp $CORE_WHEEL "$STAGE/wheels/"
  else
    echo "CORE_WHEEL set but file missing: $first_wheel" >&2
    exit 1
  fi
else
  echo "==> CORE_WHEEL_DIR not set — building from source (local dev mode)"
  python -m pip install -q --upgrade pip wheel maturin
  python -m maturin build --release -m core/zip_reader/Cargo.toml -o "$STAGE/wheels"
  python -m maturin build --release -m core/dex_reader/Cargo.toml -o "$STAGE/wheels"
  python -m pip wheel . --no-deps -w "$STAGE/wheels"
fi

echo "==> Downloading dependency wheels"
python -m pip download -d "$STAGE/wheels" \
  "androguard>=4.1.4" "jinja2>=3.1.0" "fastmcp>=2.0"

echo "==> Copying wrappers and metadata"
cp LICENSE README.md pyproject.toml "$STAGE/"
cp -R wrappers "$STAGE/"
cp scripts/release/INSTALL.txt "$STAGE/"

case "$PLATFORM" in
  linux)
    cp scripts/release/install-linux.sh "$STAGE/install.sh"
    chmod +x "$STAGE/install.sh"
  ;;
  macos)
    cp scripts/release/install-macos.sh "$STAGE/install.sh"
    chmod +x "$STAGE/install.sh"
  ;;
  windows)
    cp scripts/release/install-windows.ps1 "$STAGE/install.ps1"
  ;;
esac

ARCHIVE_DIR="$ROOT/release-staging"
case "$PLATFORM" in
  linux)
    tar -czf "$ARCHIVE_DIR/${STAGE_NAME}.tar.gz" -C "$ARCHIVE_DIR" "$STAGE_NAME"
    ls -la "$ARCHIVE_DIR/${STAGE_NAME}.tar.gz"
  ;;
  macos)
    (cd "$ARCHIVE_DIR" && zip -qr "${STAGE_NAME}.zip" "$STAGE_NAME")
    ls -la "$ARCHIVE_DIR/${STAGE_NAME}.zip"
  ;;
  windows)
    if command -v powershell.exe >/dev/null 2>&1; then
      powershell.exe -Command "Compress-Archive -Path '$STAGE' -DestinationPath '$ARCHIVE_DIR/${STAGE_NAME}.zip' -Force"
    else
      powershell -Command "Compress-Archive -Path '$STAGE' -DestinationPath '$ARCHIVE_DIR/${STAGE_NAME}.zip' -Force"
    fi
    ls -la "$ARCHIVE_DIR/${STAGE_NAME}.zip"
  ;;
esac

echo "Staged: $STAGE"
echo "Archive ready in $ARCHIVE_DIR"
