#!/usr/bin/env bash
# Shared helpers for APEX wrapper launchers.
set -euo pipefail

apex_repo_root() {
  local lib_dir
  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$lib_dir/../../" && pwd
}

apex_ensure_venv() {
  local root="$1"
  local venv="$root/.venv"
  if [[ ! -x "$venv/bin/python" ]]; then
    echo "Creating Python virtual environment in $venv"
    python3 -m venv "$venv"
    "$venv/bin/pip" install -q --upgrade pip wheel
    "$venv/bin/pip" install -q -e "$root"
  fi
}

apex_python() {
  local root
  root="$(apex_repo_root)"
  apex_ensure_venv "$root"
  export APEX_WRAPPER_ROOT="$root"
  exec "$root/.venv/bin/python" -m apex "$@"
}
