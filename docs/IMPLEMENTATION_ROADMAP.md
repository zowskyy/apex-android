# APEX Implementation Roadmap (v0.4.11)

Phased rollout for audit automation, supply chain, and release hardening.

## Phase 1 (Weeks 1–2) — Foundation

| Item | Status | Acceptance |
|------|--------|------------|
| `apex/gate/audit_log.py` hash-chain JSONL | ✅ Shipped | `tests/test_audit_system.py` |
| Version sync flock (`sync_version.sh`) | ✅ Shipped | `check_version_sync.sh` in CI |
| pre-commit hooks | ✅ Shipped | `.pre-commit-config.yaml` |
| Golden APK baseline | ✅ Shipped | `scripts/create-golden-apk.sh` |

## Phase 2 (Weeks 3–4) — Supply chain + signing

| Item | Status | Acceptance |
|------|--------|------------|
| `supply-chain.yml` weekly scan | ✅ Shipped | SBOM artifact + pip-audit |
| GPG SHA256SUMS signing | ✅ Optional | `GPG_*` secrets in publish job |
| `apex update-db --osv` | ✅ Shipped | merges OSV into `~/.apex/cve_db.json` |
| CVSS hard-fail at ≥9.0 | ⏳ Deferred | dependency scanner stays advisory |

## Phase 3 (Weeks 5–6) — Operations

| Item | Status | Acceptance |
|------|--------|------------|
| Runbooks (`scripts/runbooks/`) | ✅ Shipped | all support `--dry-run` |
| `emergency-rollback.yml` | ✅ Shipped | workflow_dispatch |
| `monitor-gates.yml` | ✅ Shipped | hourly failure-rate check |
| Integration test script | ✅ Shipped | `scripts/run-integration-tests.sh` |

## Phase 4 (Weeks 7+) — Hardening

| Item | Status | Notes |
|------|--------|-------|
| Signed git tags enforced in CI | ⏳ Partial | use `git tag -s`; verify in org settings |
| Immutable S3 gate archival | 📋 Planned | requires AWS infra |
| AWS KMS for GPG | 📋 Planned | see `docs/SECURITY.md` |
| Docker reproducibility | 📋 Planned | see `docs/REPRODUCIBILITY.md` |

Track progress in PR #4 and `docs/SLICE_TRUTH.md`.
