# ARC Review — APEX Android v0.4.11 (master)

**Skill:** `universal-arc-engine`  
**Date:** 2026-08-03  
**Golden Triad confirmed below**

---

## Golden Triad

| Pillar | APEX mapping |
|--------|----------------|
| **Core material** | Python `apex/` + Rust `zip_reader`/`dex_reader` + Chaquopy Android (`wrappers/android/`) |
| **Critical interfaces** | CLI/Web/MCP · `release.yml` DAG · gate scanners · Chaquopy pip · GitHub Releases |
| **Operating envelope** | v0.4.11 · gate candidate ≥60 · APK+AAB+3 desktop OS · audit trail · MTTR &lt;24h target |

---

## Phase 0 — Asset integrity & manifest

| Finding | Severity | CoF |
|---------|----------|-----|
| `SLICE_TRUTH.md` / `CI_RELEASE_BLUEPRINT.md` lag behind shipped DAG | [MEDIUM] | Fix now: 2h docs vs 1d confusion on-call |
| `tests/fixtures/` gitignored — golden baseline not in repo | [MEDIUM] | Fix now: 1h policy vs flaky regression |
| Core wheels version `0.1.0` vs app `0.4.11` | [LOW / ADVISORY] | Align when cutting core semver |

---

## Phase 1 — Topology & structural logic

| Finding | Severity | CoF |
|---------|----------|-----|
| `release-verify` blocks publish on gate fail (`scan_apk` exit 5) | ✅ | — |
| Single Chaquopy build path for mobile engine | [MEDIUM] | Wheel mode added; symlink still dev default |
| `publish` needs all desktop jobs — one OS fail blocks release | [HIGH RISK] | Windows path fixed in `d132895`; monitor per tag |

---

## Phase 2 — Partitioning & placement

| Finding | Severity | CoF |
|---------|----------|-----|
| Dependency/CVE scanner advisory only (WARN) — intentional | ✅ policy | — |
| Desktop bundles exclude `android/standalone` from wheel copy | ✅ | — |
| Pro features (MCP, Code Pilot) gated by edition | ✅ | — |

---

## Phase 3 — Connectivity & return paths

| Finding | Severity | CoF |
|---------|----------|-----|
| `security_scan` WARN severity normalized (`e9cbc50`) | ✅ fixed | — |
| `release-verify` requires venv for maturin (`3f13534`) | ✅ fixed | — |
| Audit log hash chain separate `chain_head.json` | [MEDIUM] | Backup both files; 30m ops doc |

---

## Phase 4 — Energy / resource delivery

| Finding | Severity | CoF |
|---------|----------|-----|
| Lint scanner budget 180s — full pytest suite slow on sample APK | [MEDIUM] | CI uses targeted tests; 4h to split lint job |
| `monitor-gates.yml` read empty `~/.apex/audit` on CI runner | **[HIGH RISK]** | Fix now: 1h vs false green monitoring |
| GPG optional — unsigned SHA256SUMS if secrets missing | [MEDIUM] | Set secrets before prod KPI claim |

---

## Phase 5 — Emissions & compliance

| Finding | Severity | CoF |
|---------|----------|-----|
| SBOM + pip-audit weekly (`supply-chain.yml`) | ✅ | — |
| Compliance report + audit trail | ✅ | S3 archival Phase 4 |
| Static scan disclaimer in security-scan output | ✅ | — |

---

## Phase 6 — Manufacturing & assembly

| Finding | Severity | CoF |
|---------|----------|-----|
| `bundle_release.sh` + `build-core` action for reproducible wheels | ✅ | — |
| Windows `Compress-Archive` paths (`pwd -W`) | ✅ fixed | — |
| Android requires SDK + python3.10 locally | [LOW / ADVISORY] | Documented in MASTER_NOTES |

---

## Phase 7 — Output & documentation

| Finding | Severity | CoF |
|---------|----------|-----|
| GitHub Release v0.4.11 published with 16 assets + SHA256SUMS | ✅ | — |
| PR #4 merged to `master` (`46546cf`) | ✅ | — |
| Demo video must be **terminal-first** (user feedback) | **[HIGH RISK]** | Record CLI proof each review cycle |

---

## Countermeasures implemented (this cycle)

1. **`monitor-gates.yml`** — run gate on sample APK + optional audit rate when log exists
2. **`scripts/arc_demo_terminal.sh`** — standardized terminal demo for video capture
3. **`universal-arc-engine`** skill added to global skills
4. **Terminal demo video** re-recorded (not browser)

---

## Readiness

| Score | **Yellow → Green** after monitor fix + video |
| Go | Ship downloads from Releases; ops KPIs need GPG + monitor fix verified |
