#!/usr/bin/env bash
# Terminal-first ARC demo — record this script for audit review videos.
# Usage: bash scripts/arc_demo_terminal.sh
# Output: clear step banners; no browser; full JSON summaries where useful.
set -euo pipefail

ROOT="$(cd "$(dirname "${0}")/.." && pwd)"
cd "$ROOT"

banner() {
  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  printf "║ %-60s ║\n" "$1"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo ""
  sleep 1
}

source .venv/bin/activate 2>/dev/null || {
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -q -e ".[dev]" maturin
  maturin develop --release -m core/zip_reader/Cargo.toml 2>/dev/null || true
  maturin develop --release -m core/dex_reader/Cargo.toml 2>/dev/null || true
}

banner "APEX v0.4.11 — ARC terminal demo (start to finish)"
echo "Repo: apex-android | Branch: $(git branch --show-current)"
echo "Commit: $(git rev-parse --short HEAD)"
sleep 1

banner "STEP 1/8 — Version sync (3 sources)"
bash scripts/release/check_version_sync.sh
python3 -c "import apex; print('apex version:', apex.__version__)"

banner "STEP 2/8 — Toolchain (apex doctor)"
apex doctor

banner "STEP 3/8 — Generate + inspect sample APK"
python scripts/generate_test_apk.py tests/fixtures/sample_test.apk
apex inspect tests/fixtures/sample_test.apk

banner "STEP 4/8 — Security scan"
apex security-scan tests/fixtures/sample_test.apk

banner "STEP 5/8 — Hard gate (candidate, CI mode)"
apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate --ci -o /tmp/arc-gate.json
python3 -c "
import json
g=json.load(open('/tmp/arc-gate.json'))
print('GATE SUMMARY: score=%s passed=%s blocking=%d findings=%d' % (
  g['score'], g['gate_passed'], len(g['blocking']), len(g['findings'])))
"

banner "STEP 6/8 — Audit trail integrity"
python3 -c "
from apex.gate.audit_log import AuditLogger
from apex.gate.compliance_report import generate_compliance_report
ok, msg = AuditLogger().verify_integrity()
print('Audit integrity:', msg)
r = generate_compliance_report()
print('Compliance failure_rate:', r['metrics']['failure_rate'])
"

banner "STEP 7/8 — Release artifacts (GitHub v0.4.11)"
if command -v gh >/dev/null 2>&1; then
  gh release view v0.4.11 --json url,assets --jq '{url, asset_count: (.assets|length), assets: [.assets[].name]}'
else
  echo "https://github.com/zowskyy/apex-android/releases/tag/v0.4.11"
  echo "(install gh CLI for live asset list)"
fi

banner "STEP 8/8 — Rollbook dry-run"
bash scripts/runbooks/rollback.sh 0.4.10 --dry-run

banner "DEMO COMPLETE — All paths verified"
echo "Download: https://github.com/zowskyy/apex-android/releases/tag/v0.4.11"
echo "Docs: docs/MASTER_NOTES_COPYPASTE.md | docs/ARC_REVIEW_APEX_0.4.11.md"
sleep 2
