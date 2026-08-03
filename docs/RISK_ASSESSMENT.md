# APEX Risk Assessment Matrix

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| GPG key compromise | CRITICAL | MEDIUM | AWS KMS / quarterly rotation (`docs/SECURITY.md`) |
| NVD/OSV API downtime | HIGH | LOW | Bundled `cve_db.json`; `apex update-db --osv` |
| Version sync race | HIGH | MEDIUM | `flock` in `sync_version.sh` |
| Non-deterministic builds | MEDIUM | MEDIUM | Pin tool versions; golden baseline |
| False-positive gate | MEDIUM | HIGH | LOW-confidence FAIL→WARN; scanner metadata in `weights.toml` |
| Audit log exhaustion | MEDIUM | LOW | `AuditLogger.rotate_logs(keep_days=30)` |

## Gate blast radius (metadata)

See `[meta.*]` sections in `apex/gate/weights.toml` for historical false-positive rates and MTTR hints per scanner.

## Override policy

Manual gate overrides require audit trail entry and maintainer approval — do not disable scanners in CI without incident ticket.
