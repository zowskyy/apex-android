# Audit response — APEX 0.4.11

Response to external audit review (operational coherence + security posture).  
**Repo:** `zowskyy/apex-android` · **Version:** 0.4.11 · **Date:** 2026-08-03

---

## Executive summary

The audit correctly identifies APEX as operationally coherent for a new lead engineer **when using `docs/MASTER_NOTES_COPYPASTE.md` + `docs/BLUEPRINT_GUIDE.md`**. Several recommendations are **accepted** and implemented in this response. A few items **differ from repo policy by design** (not bugs).

| Verdict | Area |
|---------|------|
| ✅ Accept | Docs index, version-sync CI, SHA256SUMS on release, Dependabot |
| ✅ Accept (documented) | Release smoke-test, gate.json archival, benchmark suite usage |
| 🟡 Defer | GPG wheel signing, reproducible-build flags, mkdocstrings CI |
| ❌ Decline (policy) | Auto-FAIL gate on HIGH CVE; Mach-O iOS scanner in 0.4.11 |
| 🔧 Correct | Finding model is **dataclass**, not Pydantic (optional future) |

---

## 1. Repository health

| Finding | Response | Action |
|---------|----------|--------|
| Modular layout | **Agree** — `apex/`, `core/`, `wrappers/`, `scripts/` | Added `docs/README.md` index |
| Version sync | **Agree** — three sources must match | `scripts/release/check_version_sync.sh` + CI step |
| CI pipeline | **Agree** — matrix, ruff, pytest, gate, release DAG | Dependabot added |
| MASTER NOTES as SOT | **Agree** | Keep; link from docs index |
| Branch protection | **Agree** (process) | Recommend: require `ci.yml` + `hard-gate.yml` on `master` (GitHub settings) |

---

## 2. Build & packaging

| Finding | Response | Action |
|---------|----------|--------|
| Rust wheels signing | **Defer** — no GPG release key in Community edition | SHA256SUMS on publish (implemented); GPG optional later |
| Android `ANDROID_HOME` | **Already implemented** — `build_standalone.sh` exits early if SDK missing | No change |
| Desktop reproducible archives | **Defer** — tar/zip timestamps vary by platform | Document in release notes |
| Release SHA256SUMS | **Accept** | `release.yml` publish job generates `SHA256SUMS` |

---

## 3. Security — hard gate & scanners

### Finding model correction

Audit references a **Pydantic** finding model. **Repo truth (v0.4.11):**

- `apex/gate/models.py` — `dataclass` `GateFinding` + `GateReport`
- Fields: `scanner`, `status`, `category`, `message`, `evidence`, `weight`, `confidence`, `remediation`
- `gate.json` schema_version on report is `1` in `GateReport.to_dict()`
- Pydantic export listed as **optional future** in `COMPLETION_ROADMAP.md`

Unit tests: `tests/test_cve_slices.py` (confidence, normalize_status), `tests/test_gate.py`.

### Scanner recommendations

| Scanner | Audit suggestion | Response |
|---------|------------------|----------|
| Manifest | Permission-usage audit | **Defer** — partial coverage in static scanner; expand in slice |
| Dex | New bytecode versions | **Monitor** — Androguard + dex_reader updates via Dependabot |
| Security | Entropy on resources | **Defer** — zip bomb + traversal already covered |
| Native | Mach-O for iOS | **Out of scope v0.4.11** — documented; ELF only |
| API watch | `SecureRandom` misuse | **Accept backlog** — add to `watchlists/crypto.py` |
| NetSec | OkHttp/TLS version | **Partial** — dependency/CVE covers OkHttp prefix |
| Lint | `StrictMode` rule | **Accept backlog** — add to `lint_rules.yaml` |
| Dependency | Auto-FAIL on HIGH CVE | **Decline** — **advisory policy**: dependency scanner never FAILs gate by default; HIGH + version-confirmed → WARN. Rationale: prefix-only false positives; human review required |
| Obfuscation | Monitor FN rate | **Agree** — heuristic only; weight 0.05 |

Scoring/budgets: budgets in `apex/gate/budgets.py`; remediation strings on native/api_watch/dependency findings. Budget exceedance → timeout + lightweight fallback (api_watch).

---

## 4. Dependency management

| Finding | Response |
|---------|----------|
| Pin androguard minor | **Partial accept** — mobile Gradle pins `androguard==4.1.4`; desktop uses `>=4.1.4` |
| Periodic outdated audit | **Accept** — Dependabot weekly for pip + cargo + actions |
| `pip list --outdated` script | **Defer** — Dependabot covers PR workflow |

---

## 5. Release checklist validation

Audit additions:

| Item | Response | Action |
|------|----------|--------|
| Smoke-test APK on device | **Accept** — manual step in checklist | Added to `AUDIT_RESPONSE` + MASTER NOTES §20 |
| GPG verify wheels | **Defer** — Community edition |
| Security-scan on tag + archive report | **Partial** — `ci.yml` runs gate on PR; tag release runs full pipeline | Optional: upload `gate.json` as release asset (backlog) |

---

## 6. Outstanding / future work

| Item | Priority | Notes |
|------|----------|-------|
| Mach-O scanner (iOS) | P2 | Mirror ELF checks when iOS native scope opens |
| OSV/NVD sync for `cve_db.json` | P1 | `apex update-db` today is bundle-only |
| Immutable gate.json storage (S3) | P2 | Enterprise/compliance slice |
| `pytest-benchmark` on Rust readers | P1 | Already in dev deps; add benchmark tests |
| mkdocstrings API docs | P3 | Optional |

---

## 7. Operational coherence score

**Question:** Can a new lead engineer run the project without asking questions?

| With… | Score |
|-------|-------|
| README only | Partial — install OK, release factory incomplete |
| README + `BLUEPRINT_GUIDE.md` | Good — daily ops covered |
| `MASTER_NOTES_COPYPASTE.md` | **Excellent** — scratch → ship path complete |
| + this audit response | **Excellent** — policy exceptions explicit |

**Recommended onboarding path:**

1. `docs/README.md` → `docs/BLUEPRINT_GUIDE.md`
2. `docs/MASTER_NOTES_COPYPASTE.md` §0 (ordered checklist)
3. `apex doctor` + `pytest -q`
4. `docs/CI_RELEASE_BLUEPRINT.md` before first tag

---

## Implemented from this audit (commit reference)

- `docs/README.md` — documentation index
- `scripts/release/check_version_sync.sh` — CI version guard
- `.github/dependabot.yml` — weekly pip/cargo/actions updates
- `.github/workflows/ci.yml` — version sync check step
- `.github/workflows/release.yml` — `SHA256SUMS` on publish

---

## Branch protection (manual GitHub settings)

Recommended for `master`:

- Require status checks: `python` (ci.yml), `hard-gate` (hard-gate.yml)
- Require PR before merge
- Do not allow bypass for administrators (optional)
