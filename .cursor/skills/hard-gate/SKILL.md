---
name: hard-gate
description: Zero-failure hard gate for APEX — 9 automated slices spanning Phase 1 read-only analysis, Phase 2 decode/rebuild, Phase 3 security/diff/wiring/mobile/ship. Run scripts/hard_gate.sh before releases. Use with finished-product-delivery and mobile-hard-gate.
---

# SKILL: Hard Gate — Phases 1, 2, 3 (9 slices)

> **One rule:** No slice is “done” until **its gate passes** locally and on GitHub.

This unifies static file-inventory safety, workflow tests, mobile wiring, and CI
proof into one runnable gate. It does **not** replace domain implementation —
it **proves** what you claim works.

Run:

```bash
bash scripts/hard_gate.sh              # G1–G8 local
bash scripts/hard_gate.sh --ship       # + GitHub CI + Android APK green on HEAD
bash scripts/hard_gate.sh --release v0.4.6   # + mobile marketplace audit on tag
```

---

## The 9 slices

| Slice | Phase | Goal | Gate |
|-------|-------|------|------|
| **G1** | 1 | ZIP extraction safety (no traversal escape) | `tests/test_zip_reader.py` |
| **G2** | 1 | Static inventory / scan primitives | `tests/test_core.py` |
| **G3** | 1 | Inspect + decompile read-only path | `test_workflows` inspect/decompile |
| **G4** | 2 | Decode APK → editable project | `test_workflows` decode |
| **G5** | 2 | Verify + build + roundtrip | `test_workflows` verify/roundtrip/build |
| **G6** | 3 | Security scan + semantic diff | `test_workflows` security/diff |
| **G7** | 3 | Doctor + web UI + ZIP container resolve | import smoke + `test_package_resolve` |
| **G8** | Mobile | Chaquopy manifest + WebView file picker | `test_android_chaquopy_deps` + Java grep |
| **G9** | Ship | CI mirror + remote proof | `ruff` + `cargo test` + optional `--ship` / `--release` |

Slices **G1–G8** run in every gate. **G9** adds `ruff` + `cargo test` (CI parity); `--ship`
requires `check_github_ci.sh --apk`; `--release TAG` runs `audit_mobile_hard_gate.sh`.

---

## When to run

| Event | Command |
|-------|---------|
| Before push | `bash scripts/hard_gate.sh` |
| Before mobile handoff | `bash scripts/hard_gate.sh --ship` |
| Before declaring a release good | `bash scripts/hard_gate.sh --ship --release vX.Y.Z` |
| GitHub (automatic) | workflow `Hard Gate` on push/PR |

---

## What this does not cover (manual)

- Real device: Choose APK, engine boot, release ZIP pick (see `mobile-hard-gate`)
- Performance vs jadx/apktool 10× (blueprint benchmark slices)
- F-Droid/NewPipe corpus (optional external APKs)

Skip or extend gates when a slice genuinely does not apply — never skip because
“we’ll test on device later” for items automatable above.

---

## Definition of done (gate-level)

1. **G1–G8** PASS locally
2. **G9** `ruff` + `cargo test` PASS (or run `scripts/validate_slice.sh` for full CI mirror)
3. **Ship:** `--ship` PASS (CI + Android APK on HEAD)
4. **Release:** `--release TAG` PASS (mobile audit on tag)
5. **Device:** manual checklist from `mobile-hard-gate` skill

**Do not ship a release tag because Gradle finished. Ship because the gate finished.**
