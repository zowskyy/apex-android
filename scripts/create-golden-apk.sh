#!/usr/bin/env bash
# Generate golden gate baseline for regression comparison.
# Output: tests/fixtures/golden-apk-baseline.json (immutable reference scores)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APK="${1:-tests/fixtures/sample_test.apk}"
OUT="${2:-tests/fixtures/golden-apk-baseline.json}"
STAGE="${3:-candidate}"

if [[ ! -f "$APK" ]]; then
  python scripts/generate_test_apk.py "$APK"
fi

export APEX_AUDIT_CONTEXT=golden-baseline
apex gate "$APK" --msv 21 --stage "$STAGE" -o "$OUT"
echo "Golden baseline: $OUT"
python -c "import json; g=json.load(open('$OUT')); print('score', g['score'], 'passed', g['gate_passed'])"
