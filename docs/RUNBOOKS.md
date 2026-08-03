# APEX Runbooks

Executable procedures in `scripts/runbooks/`. All support `--dry-run`.

## Runbook 1 — Critical CVE response

```bash
bash scripts/runbooks/critical-cve.sh CVE-2024-12345 --dry-run
bash scripts/runbooks/critical-cve.sh CVE-2024-12345
```

Steps: `apex update-db`, OSV merge, `pip-audit`, `cargo audit`, re-run gate on release APK.

## Runbook 2 — Emergency rollback

```bash
bash scripts/runbooks/rollback.sh 0.4.10 --dry-run
bash scripts/runbooks/rollback.sh 0.4.10
```

Steps: sync version to target, verify `check_version_sync.sh`, create signed rollback tag.

GitHub: **Actions → Emergency Rollback** (`emergency-rollback.yml`).

## Runbook 3 — Version drift fix

```bash
bash scripts/runbooks/version-drift.sh --dry-run
bash scripts/runbooks/version-drift.sh
```

Truth source: `pyproject.toml` version → `sync_version.sh`.

## Rehearsal

```bash
bash scripts/run-integration-tests.sh
bash scripts/runbooks/rollback.sh 0.4.10 --dry-run
```

Target: rollback dry-run completes in &lt; 5 minutes.
