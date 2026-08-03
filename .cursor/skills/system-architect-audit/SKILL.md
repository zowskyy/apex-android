---
name: system-architect-audit
description: Comprehensive software project audit methodology — version integrity, build reproducibility, security gates, CI/CD automation, operational readiness. Produces findings tables, risk matrices, runbooks, and go/no-go readiness. Use when audit reviewing releases, PRs, or architecture before ship.
---

# SKILL: System Architect Audit (APEX methodology)

> **One rule:** A new lead engineer must be able to follow the blueprint without
> asking questions. Every gap gets a concrete remediation command or patch.

Use this skill when **audit reviewing** any codebase, release commit, CI change,
or operational blueprint. Pair with `finished-product-delivery`, `hard-gate`,
and `mobile-hard-gate` for APEX-specific projects.

**Version:** 1.0 · Derived from APEX v0.4.11 audit cycle

---

## Core philosophy

| Principle | Meaning |
|-----------|---------|
| Operational coherence | Map every critical path; no hidden manual steps |
| Zero-trust automation | Components self-validate; overrides need audit trail |
| Actionable recommendations | Every finding → command, patch, or workflow change |
| Iterative hardening | Audit → Blueprint → Integration test → Self-review → Output |

---

## The factory cycle (5 phases)

### Phase 1 — Ingest

1. Receive artifacts: code, workflows, scripts, docs, commit/PR diff.
2. Identify project type, deployment targets, constraints.
3. List primary artifacts: source, binaries, CI DAG, version sources.

**APEX ingest checklist:**

```text
apex/version.py · pyproject.toml · build.gradle versionName
.github/workflows/*.yml · apex/gate/* · scripts/release/*
docs/MASTER_NOTES_COPYPASTE.md · docs/SLICE_TRUTH.md
```

### Phase 2 — Deep audit

For each domain, produce a table: **Control | Implementation | Why it matters | Residual risk | Mitigation**.

| Domain | Key questions |
|--------|----------------|
| Version management | Three-point sync? Atomic updates? Signed tags? Drift detection? |
| Build & reproducibility | Deterministic builds? Pinned toolchains? SBOM archived? |
| Security gates | Weights sum to 1.0? Advisory vs blocking policy? API fallbacks? |
| CI/CD pipeline | DAG blocks on gate failure? Signed artifacts? Rollback path? |
| Operational readiness | Runbooks? Monitoring? Audit logs? Compliance reports? |

### Phase 3 — Blueprint generation

Synthesize into Master Notes (or audit report):

- One-page “do this in order”
- CI workflow DAG
- Troubleshooting table
- Script/config references (repo-truth only — mark `[NEW]` for additions)

### Phase 4 — Integration test (mental simulation)

Walk scratch → ship. Simulate:

- Version mismatch
- CVE/OSV API downtime
- Sync race conditions
- Non-deterministic builds
- Gate false positives/negatives

Verify every critical failure produces an actionable message.

### Phase 5 — Self-review & output

1. Compare final state vs initial audit — list delta improvements.
2. Readiness score: **Green / Yellow / Red**
3. Go / no-go for release tag

---

## Specialised audit domains

### 1. Version integrity

- **Check:** Python + pyproject + Gradle (or equivalent) agree.
- **Hardening:** `flock` in sync script, pre-commit/pre-push hooks, signed tags, CI tag↔version assertion.
- **APEX commands:**

```bash
bash scripts/release/check_version_sync.sh
bash scripts/release/sync_version.sh X.Y.Z
pre-commit run version-sync-check --all-files
```

### 2. Build reproducibility

- **Check:** Python/Rust/Gradle versions pinned; wheel paths documented.
- **Hardening:** Rust release flags, Docker base SHA, SBOM generation, golden baseline.
- **APEX commands:**

```bash
python scripts/release/generate_sbom.py sbom.json
bash scripts/create-golden-apk.sh
pytest tests/test_reproducibility.py -q
```

### 3. Security gate

- **Check:** `weights.toml` sums to 1.0; dependency scanner policy (APEX: advisory WARN only).
- **Hardening:** Scanner metadata, baseline regression, audit logging on every run.
- **APEX commands:**

```bash
apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate --ci
python -c "from apex.gate.weights import load_scanner_weights, validate_weights; validate_weights(load_scanner_weights())"
python scripts/security/scan_apk.py path/to.apk -o gate-report.json
```

### 4. CI/CD pipeline

- **Check:** `release-verify` blocks publish; SBOM + SHA256SUMS; rollback workflow exists.
- **Hardening:** `supply-chain.yml`, `emergency-rollback.yml`, `monitor-gates.yml`, GPG signing.
- **APEX workflows:** `ci.yml`, `release.yml`, `supply-chain.yml`, `emergency-rollback.yml`, `monitor-gates.yml`

### 5. Operability

- **Check:** `audit_log.py`, `compliance_report.py`, runbooks with `--dry-run`.
- **Hardening:** Alerting on failure rate, log rotation, compliance attestation.
- **APEX commands:**

```bash
bash scripts/runbooks/rollback.sh 0.4.10 --dry-run
bash scripts/run-integration-tests.sh
python -c "from apex.gate.audit_log import AuditLogger; print(AuditLogger().verify_integrity())"
```

---

## Output templates

### A. Findings table

| Control | Implementation | Why it matters | Residual risk | Mitigation |
|---------|----------------|----------------|---------------|------------|

### B. Risk matrix

| Risk | Severity | Likelihood | Mitigation |

### C. Testing checklist

```markdown
☐ Version sync passes check_version_sync.sh
☐ Gate blocks release APK on FAIL (scan_apk exit ≠ 0)
☐ Audit log verify_integrity() passes
☐ SBOM generated
☐ Rollback dry-run completes in < 5 minutes
☐ pre-commit hooks pass
```

### D. Success metrics (monthly KPIs)

- Gate failure rate &lt; 2%
- MTTR &lt; 24h
- Unsigned releases = 0 (when GPG configured)
- Audit integrity = 100%

---

## APEX audit invocation

When auditing an APEX commit or PR:

```text
1. git show <commit> --stat
2. Run Phase 2 domains against changed paths
3. Cross-check docs/SLICE_TRUTH.md and IMPLEMENTATION_ROADMAP.md for fiction
4. Run: pytest tests/test_audit_system.py tests/test_version_sync.py -q
5. Verify release.yml DAG matches docs/CI_RELEASE_BLUEPRINT.md
6. Output findings table + readiness score + remediation commands
```

**Repo-truth policies (do not audit as gaps if intentionally deferred):**

- Dependency CVE scanner: **advisory WARN** — not auto-FAIL on HIGH CVE
- Finding model: **dataclass** in `gate/models.py` — not Pydantic
- Android mobile: **Groovy** Gradle + symlink/wheel — not Kotlin DSL
- AWS KMS/S3: Phase 4 planned — not required in OSS repo

---

## Definition of done (audit-level)

1. All five domains reviewed with findings table
2. Every **Red/Yellow** finding has remediation command
3. Integration simulation notes edge cases
4. Readiness score with go/no-go rationale
5. Delta list vs previous audit (if applicable)
6. **Demo video** when review is complete — record start-to-finish proof (see below)

**Do not mark Green because docs look complete. Mark Green because controls are wired and tested.**

---

## Phase 6 — Demo video (end of review)

When the audit/review is **complete** (bill of work done, release shipped or PR merged),
record a **start-to-finish video** showing the system working as documented.

### What to show (APEX checklist)

1. Version sync: `bash scripts/release/check_version_sync.sh`
2. `apex doctor` — toolchain OK
3. Sample APK: `apex inspect` + `apex security-scan` + `apex gate --ci`
4. Audit trail: `AuditLogger().verify_integrity()` or compliance report
5. Release proof: GitHub Release assets or `gh release view vX.Y.Z`
6. Optional: `apex gui` or mobile path if in scope

### Recording

- Use screen recording (Cursor `RecordScreen` or local capture)
- Save as `apex-demo-vX.Y.Z` — provide MP4 for broad compatibility
- Narrate or subtitle key steps so a new engineer can follow without the doc

### When to skip

- Docs-only PR with no runnable surface
- CI-only change with no local demo path (link green Actions run instead)
