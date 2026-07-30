#!/usr/bin/env bash
# Independent verification of Slice 1.1 (Rust ZIP reader / path-traversal
# sanitization). Run this yourself — it doesn't trust anything Claude said,
# it re-derives every claim from scratch:
#   - recompiles the Rust crate and runs its unit tests
#   - runs `cargo clippy` (an external, independently-maintained linter —
#     not written by Claude) against the security-critical crate
#   - rebuilds the Python extension wheel from source and reinstalls it
#   - runs the full pytest suite
#   - runs a *new*, minimal traversal check written inline below, not
#     reused from tests/test_zip_reader.py, so a bug hidden in that test
#     file can't hide a bug in the code
#
# Exit code is 0 only if everything below passed.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PASS=0
FAIL=0
say() { printf '\n=== %s ===\n' "$1"; }
ok()  { PASS=$((PASS+1)); printf '[PASS] %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '[FAIL] %s\n' "$1"; }

say "1. Rust unit tests (cargo test -p apex_zip_reader --lib)"
if cargo test -p apex_zip_reader --lib 2>&1 | tee /tmp/apex_audit_cargo_test.log | tail -20; then
  N=$(grep -c "^test .* ok$" /tmp/apex_audit_cargo_test.log || true)
  if grep -q "test result: ok" /tmp/apex_audit_cargo_test.log; then
    ok "cargo test passed ($N tests ok — read /tmp/apex_audit_cargo_test.log for full output)"
  else
    bad "cargo test did not report 'test result: ok'"
  fi
else
  bad "cargo test failed to run"
fi

say "2. cargo clippy (independent static-analysis linter, not authored by Claude)"
if cargo clippy -p apex_zip_reader --all-targets -- -D warnings 2>&1 | tee /tmp/apex_audit_clippy.log | tail -30; then
  ok "clippy: zero warnings on -D warnings"
else
  bad "clippy reported warnings/errors — see /tmp/apex_audit_clippy.log"
fi

say "3. Rebuild the Python extension wheel from source (not reusing a cached build)"
rm -rf core/zip_reader/target/wheels 2>/dev/null
if (cd core/zip_reader && python -m maturin build --release 2>&1 | tee /tmp/apex_audit_maturin.log | tail -15); then
  WHEEL=$(find target/wheels -name "apex_zip_reader-*.whl" | head -1)
  if [ -n "$WHEEL" ]; then
    python -m pip install --force-reinstall --quiet "$WHEEL"
    ok "wheel rebuilt and reinstalled: $WHEEL"
  else
    bad "maturin build succeeded but no wheel found"
  fi
else
  bad "maturin build failed — see /tmp/apex_audit_maturin.log"
fi

say "4. Full pytest suite"
if python -m pytest tests/ -v 2>&1 | tee /tmp/apex_audit_pytest.log | tail -25; then
  ok "pytest suite passed"
else
  bad "pytest suite failed — see /tmp/apex_audit_pytest.log"
fi

say "5. Independent inline traversal check (written here, not reused from tests/)"
python3 - <<'PYEOF'
import sys, zipfile, tempfile, shutil
from pathlib import Path

sys.path.insert(0, ".")
import apex

tmp = Path(tempfile.mkdtemp())
apk = tmp / "audit_malicious.apk"

# Independent set of traversal patterns, deliberately not copy-pasted from
# tests/test_zip_reader.py's fixture, to catch a bug that test might share.
attacks = {
    r"../../../../../windows/system32/audit_marker.dll": "unix-style traversal",
    r"..\..\..\..\..\windows\system32\audit_marker2.dll": "windows-style traversal (raw backslash)",
    r"/etc/audit_marker_abs": "unix absolute path",
    r"C:\Windows\audit_marker_abs.dll": "windows absolute path (raw backslash)",
    r"normal/nested/traversal/../../../audit_marker_mixed": "mixed traversal after clean prefix",
    r"legit/file.txt": "control: should extract cleanly",
}

# zipfile.ZipInfo's constructor auto-normalizes os.sep ('\' on Windows) to
# '/' in the filename, which would silently turn the two raw-backslash
# attack names above into the forward-slash cases and defeat the point of
# testing them. Set .filename *after* construction to bypass that
# normalization and actually exercise the raw-backslash path end-to-end.
with zipfile.ZipFile(apk, "w") as zf:
    for name in attacks:
        info = zipfile.ZipInfo("placeholder")
        info.filename = name
        zf.writestr(info, b"AUDIT_PROBE")

extract_dir, report = apex.extract_apk(apk, tmp / "work")

failures = []
for name, desc in attacks.items():
    is_control = (name == "legit/file.txt")
    entry = next((e for e in report["entries"] if e["name"] == name), None)
    if entry is None:
        failures.append(f"MISSING entry for {name!r} ({desc})")
        continue
    if is_control:
        if entry["verdict"] != "CLEAN":
            failures.append(f"control file wrongly blocked: {name!r} -> {entry}")
    else:
        if entry["verdict"] != "WARN":
            failures.append(f"ATTACK NOT BLOCKED: {name!r} ({desc}) -> verdict={entry['verdict']!r}")

# Filesystem-level check: walk everything under tmp's PARENT and confirm no
# audit_marker* file exists anywhere outside extract_dir.
escaped = [p for p in tmp.parent.rglob("audit_marker*") if extract_dir not in p.parents and p != extract_dir]
if escaped:
    failures.append(f"FILES ESCAPED extract_dir: {escaped}")

shutil.rmtree(tmp, ignore_errors=True)

if failures:
    print("INLINE TRAVERSAL CHECK: FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
else:
    print(f"INLINE TRAVERSAL CHECK: PASS ({len(attacks)-1} attacks blocked, 1 control file extracted clean, nothing escaped extract_dir)")
    sys.exit(0)
PYEOF
if [ $? -eq 0 ]; then
  ok "inline traversal check passed"
else
  bad "inline traversal check failed"
fi

say "SUMMARY"
echo "PASS: $PASS   FAIL: $FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "All independent checks passed."
  exit 0
else
  echo "One or more checks failed — see logs in /tmp/apex_audit_*.log"
  exit 1
fi
