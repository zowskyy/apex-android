#!/usr/bin/env bash
# Prepare Chaquopy engine: symlink (dev default) or wheel (CI/reproducible).
#
# Usage:
#   APEX_ENGINE_MODE=symlink  — symlink repo apex/ into src/main/python (default)
#   APEX_ENGINE_MODE=wheel    — build apex-android wheel → standalone/core-wheel.whl
#
# Called by wrappers/android/build_standalone.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../" && pwd)"
STANDALONE="$HERE/standalone"
PY_SRC="$STANDALONE/app/src/main/python"
ENGINE_MODE="${APEX_ENGINE_MODE:-symlink}"

mkdir -p "$PY_SRC"
rm -f "$STANDALONE/.engine-mode" "$STANDALONE/core-wheel.whl"

if [[ "$ENGINE_MODE" == "wheel" ]]; then
  echo "==> APEX_ENGINE_MODE=wheel — building apex-android wheel for Chaquopy"
  mkdir -p "$ROOT/dist"
  python3.10 -m pip install -q --upgrade pip wheel
  python3.10 -m pip wheel "$ROOT" --no-deps -w "$ROOT/dist"
  WHEEL="$(ls "$ROOT/dist"/apex_android-*.whl 2>/dev/null | head -n1)"
  if [[ -z "$WHEEL" || ! -f "$WHEEL" ]]; then
    echo "prepare_chaquopy_engine: apex_android wheel missing in $ROOT/dist" >&2
    exit 1
  fi
  cp -f "$WHEEL" "$STANDALONE/core-wheel.whl"
  echo "wheel" > "$STANDALONE/.engine-mode"
  rm -f "$PY_SRC/apex"
  echo "Injected: $STANDALONE/core-wheel.whl"
else
  echo "==> APEX_ENGINE_MODE=symlink — linking repo apex/ into Chaquopy"
  rm -f "$PY_SRC/apex"
  ln -sfn "$ROOT/apex" "$PY_SRC/apex"
  rm -f "$STANDALONE/core-wheel.whl"
fi
