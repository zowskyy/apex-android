#!/usr/bin/env bash
# Zero-failure hard gate — 9 slices across Phase 1 (analysis), Phase 2 (decode/build),
# Phase 3 (security/diff/mobile/ship). Skips slices when tools/fixtures are unavailable.
#
# Usage:
#   scripts/hard_gate.sh              # local gates G1–G8
#   scripts/hard_gate.sh --ship       # G1–G8 + GitHub CI green on HEAD
#   scripts/hard_gate.sh --release v0.4.6   # G1–G8 + mobile audit on tag
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SHIP=0
RELEASE_TAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ship) SHIP=1 ;;
    --release) RELEASE_TAG="${2:-}"; shift ;;
    -h|--help)
      sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

PASS=0
FAIL=0
SKIP=0

ok() { echo "  PASS  $*"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $*" >&2; FAIL=$((FAIL + 1)); }
skip() { echo "  SKIP  $*"; SKIP=$((SKIP + 1)); }

run() {
  if "$@"; then
    return 0
  fi
  return 1
}

ensure_venv() {
  if [[ ! -x .venv/bin/python ]]; then
    echo "==> Creating .venv (hard gate bootstrap)"
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -q --upgrade pip wheel
    pip install -q -e ".[dev,mcp]"
    pip install -q maturin
    if command -v rustc >/dev/null 2>&1; then
      maturin develop -q --release -m core/zip_reader/Cargo.toml
      maturin develop -q --release -m core/dex_reader/Cargo.toml
    else
      skip "Rust not installed — native extensions skipped"
    fi
  else
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
}

echo "==> APEX Hard Gate (9 slices)"
ensure_venv

echo ""
echo "## G1 Phase 1 — extraction safety (static inventory / ZIP hardening)"
if run .venv/bin/pytest -q tests/test_zip_reader.py; then
  ok "ZIP traversal + realistic extract tests"
else
  bad "tests/test_zip_reader.py"
fi

echo ""
echo "## G2 Phase 1 — file inventory & core static primitives"
if run .venv/bin/pytest -q tests/test_core.py; then
  ok "inventory, crossrefs, scan_* primitives"
else
  bad "tests/test_core.py"
fi

echo ""
echo "## G3 Phase 1 — inspect + decompile (read-only analysis)"
if run .venv/bin/pytest -q tests/test_workflows.py -k "inspect or decompile or dex_metadata"; then
  ok "inspect_apk + decompile workflow"
else
  bad "Phase 1 inspect/decompile tests"
fi

echo ""
echo "## G4 Phase 2 — decode to project (raw backend)"
if run .venv/bin/pytest -q tests/test_workflows.py -k "decode"; then
  ok "decode_apk raw/apktool paths"
else
  bad "Phase 2 decode tests"
fi

echo ""
echo "## G5 Phase 2 — verify + roundtrip"
if run .venv/bin/pytest -q tests/test_workflows.py -k "verify or roundtrip or build"; then
  ok "verify / build / roundtrip workflow"
else
  bad "Phase 2 verify/roundtrip tests"
fi

echo ""
echo "## G6 Phase 3 — security scan + semantic diff"
if run .venv/bin/pytest -q tests/test_workflows.py -k "security or diff"; then
  ok "security_scan + diff_apks"
else
  bad "Phase 3 security/diff tests"
fi

echo ""
echo "## G7 Phase 3 — wiring (doctor, web UI, container resolve)"
if .venv/bin/python - <<'PY'
from apex.workflows import doctor
from apex.web import ApexWebHandler
from apex.analysis import resolve_android_package

d = doctor()
assert d.get("ready") or d.get("androguard"), d
print("doctor ok")
PY
then
  ok "doctor() + web handler import"
else
  bad "doctor/web import smoke"
fi
if run .venv/bin/pytest -q tests/test_package_resolve.py; then
  ok "ZIP/XAPK container resolution"
else
  bad "tests/test_package_resolve.py"
fi

echo ""
echo "## G8 Mobile — Chaquopy manifest + WebView file picker"
if run .venv/bin/pytest -q tests/test_android_chaquopy_deps.py; then
  ok "Chaquopy pip manifest tests"
else
  bad "tests/test_android_chaquopy_deps.py"
fi
if grep -q onShowFileChooser wrappers/android/standalone/app/src/main/java/io/apex/standalone/MainActivity.java \
  && grep -q buildPackagePickerIntent wrappers/android/standalone/app/src/main/java/io/apex/standalone/MainActivity.java; then
  ok "Android WebView package picker wired"
else
  bad "MainActivity missing file picker hooks"
fi

echo ""
echo "## G9 Ship — CI mirror (ruff + Rust) + optional remote proof"
if run .venv/bin/ruff check apex tests; then
  ok "ruff (matches CI job)"
else
  bad "ruff check"
fi
if command -v cargo >/dev/null 2>&1; then
  if run cargo test --workspace; then
    ok "cargo test --workspace"
  else
    bad "cargo test --workspace"
  fi
else
  skip "cargo not installed"
fi
if [[ "$SHIP" -eq 1 ]]; then
  if run bash scripts/check_github_ci.sh --apk; then
    ok "GitHub CI + Android standalone APK on HEAD"
  else
    bad "check_github_ci.sh --apk"
  fi
else
  skip "remote CI proof (pass --ship to require gh green on HEAD)"
fi
if [[ -n "$RELEASE_TAG" ]]; then
  if run bash scripts/audit_mobile_hard_gate.sh "$RELEASE_TAG"; then
    ok "mobile hard gate audit for $RELEASE_TAG"
  else
    bad "audit_mobile_hard_gate.sh $RELEASE_TAG"
  fi
else
  skip "release tag audit (pass --release vX.Y.Z)"
fi

echo ""
echo "==> Hard Gate summary: PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
if [[ "$FAIL" -gt 0 ]]; then
  echo "HARD GATE: FAILED" >&2
  exit 1
fi
echo "HARD GATE: PASS (automated slices). Device smoke remains manual — see mobile-hard-gate skill."
exit 0
