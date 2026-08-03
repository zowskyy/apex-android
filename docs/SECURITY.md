# APEX Security — Signing & Secrets

## GPG signing

**Tags:** `git tag -s v0.4.11 -m "APEX v0.4.11"`

**Release checksums:** `release.yml` publish job signs `SHA256SUMS` when secrets exist:

| Secret | Purpose |
|--------|---------|
| `GPG_PRIVATE_KEY` | Armored private key |
| `GPG_KEY_ID` | Signing key id |
| `GPG_PASSPHRASE` | Optional |

Setup guide: `bash scripts/setup-ci-gpg.sh`

## CVE data

- Bundled: `apex/data/cve_db.json`
- User cache: `~/.apex/cve_db.json`
- Refresh: `apex update-db` / `apex update-db --osv`

Dependency gate findings are **advisory (WARN)** — no auto-FAIL on HIGH CVE in v0.4.11.

## Key rotation

Rotate GPG keys quarterly. Document old key revocation on GitHub Releases page.

## Compromise response

1. Revoke compromised key
2. Run `emergency-rollback.yml` to last known-good tag
3. Re-sign artifacts with new key
4. Review audit log integrity: `AuditLogger().verify_integrity()`

## Future: AWS KMS / Secrets Manager

Enterprise deployments should store signing material in KMS rather than GitHub secrets (`docs/IMPLEMENTATION_ROADMAP.md` Phase 4).
