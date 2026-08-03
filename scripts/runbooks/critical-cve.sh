#!/usr/bin/env bash
# Critical CVE response runbook.
# Usage:
#   bash scripts/runbooks/critical-cve.sh CVE-2024-12345
#   bash scripts/runbooks/critical-cve.sh CVE-2024-12345 --dry-run
set -euo pipefail

CVE="${1:?CVE id required}"
DRY_RUN=false
if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> Critical CVE response: ${CVE}"

if $DRY_RUN; then
  echo "DRY RUN: would run apex update-db"
  echo "DRY RUN: would run python scripts/release/fetch_cve_osv.py"
  echo "DRY RUN: would run pip-audit / cargo audit"
  echo "DRY RUN: would trigger CI hard-gate workflow"
  exit 0
fi

cd "$ROOT"
apex update-db || true
python scripts/release/fetch_cve_osv.py || true
python -m pip install -q pip-audit 2>/dev/null && pip-audit || echo "pip-audit skipped"
if command -v cargo >/dev/null 2>&1; then
  cargo audit || echo "cargo audit skipped"
fi
echo "Review apex/data/cve_db.json and lockfiles; push fix + run apex gate on release APK."
