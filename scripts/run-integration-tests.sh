#!/usr/bin/env bash
# End-to-end integration smoke: version → gate → audit → compliance → rollback dry-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export APEX_AUDIT_CONTEXT=integration-test
TMP_AUDIT="${TMPDIR:-/tmp}/apex-audit-$$"
mkdir -p "$TMP_AUDIT"
export APEX_AUDIT_DIR="$TMP_AUDIT"

echo "==> 1. Version sync check"
bash scripts/release/check_version_sync.sh

echo "==> 2. Generate sample APK"
python scripts/generate_test_apk.py tests/fixtures/sample_test.apk

echo "==> 3. Hard gate"
apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate -o /tmp/apex-integration-gate.json

echo "==> 4. Audit integrity"
python -c "
import os
os.environ['APEX_AUDIT_DIR'] = '${TMP_AUDIT}'
from apex.gate.audit_log import AuditLogger
from apex.gate import run_hard_gate
from pathlib import Path
run_hard_gate(Path('tests/fixtures/sample_test.apk'), msv=21, stage='candidate')
logger = AuditLogger()
ok, msg = logger.verify_integrity()
print('audit:', msg)
assert ok
"

echo "==> 5. Compliance report"
python -c "from apex.gate.compliance_report import generate_compliance_report; r=generate_compliance_report(); print('failure_rate', r['metrics']['failure_rate'])"

echo "==> 6. Golden baseline check"
bash scripts/create-golden-apk.sh tests/fixtures/sample_test.apk /tmp/golden-integration.json

echo "==> 7. Rollback dry-run"
bash scripts/runbooks/rollback.sh 0.4.10 --dry-run

echo "==> Integration tests passed"
rm -rf "$TMP_AUDIT"
