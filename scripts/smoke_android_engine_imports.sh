#!/usr/bin/env bash
# Smoke-test the exact Chaquopy release Python env used inside the APK.
# Run after assembleRelease — catches missing pip deps before users install.
#
# Usage: scripts/smoke_android_engine_imports.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STANDALONE="$ROOT/wrappers/android/standalone"
PY="$STANDALONE/app/build/python/env/release/bin/python"
PY_SRC="$STANDALONE/app/src/main/python"

if [[ ! -x "$PY" ]]; then
  echo "smoke_android_engine_imports: Chaquopy release Python not found." >&2
  echo "Build first: bash wrappers/android/build_standalone.sh" >&2
  exit 1
fi

if [[ ! -d "$PY_SRC/apex" ]]; then
  echo "smoke_android_engine_imports: missing $PY_SRC/apex (run build_standalone.sh)" >&2
  exit 1
fi

export PYTHONPATH="$PY_SRC${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Chaquopy import smoke test ($PY)"
"$PY" - <<'PY'
import sys

checks = [
    ("markupsafe", "import markupsafe"),
    ("jinja2", "from jinja2 import Template"),
    ("mutf8", "from mutf8 import decode_modified_utf8"),
    ("loguru", "from loguru import logger"),
    ("androguard", "import androguard"),
    ("apex", "import apex"),
    ("apex.android_boot", "from apex.android_boot import prepare_engine"),
]

failed = []
for name, stmt in checks:
    try:
        exec(stmt, {})
        print(f"  ok  {name}")
    except Exception as exc:
        print(f"  FAIL {name}: {exc}")
        failed.append((name, exc))

if failed:
    print()
    print("Chaquopy engine import smoke test FAILED.")
    print("Add missing packages to app/build.gradle chaquopy.pip or vendor pure-Python shims.")
    sys.exit(1)

print("Chaquopy engine import smoke test passed.")
PY
