# Hard Gate Slices — what applies to APEX

APEX is an **APK analysis tool**, not a single shipped consumer app. The 9-slice
roadmap applies selectively:

| Slice | Topic | APEX status |
|-------|--------|-------------|
| **0** | Modular gate models + CI exit codes | **Implemented** — `apex/gate/`, `apex gate --ci` |
| **1** | Manifest MSV, DEX rigor, permissions, **secret patterns** | **Implemented** — static scanners + `secrets` gate weight |
| **2** | Firebase Test Lab | **N/A** — analyze third-party APKs; optional future for APEX Mobile QA |
| **3** | Perfetto / TTI on device | **N/A** — same; use for APEX app RC only if added later |
| **4** | MobSF Docker SAST | **Partial** — built-in `security_scan`; MobSF optional external |
| **5** | A11y / L10n layout scans | **Future** — needs decoded `res/layout` pipeline |
| **6** | Monkey / chaos | **N/A** for analyzer; optional for APEX Mobile soak |
| **7** | Weighted scorecard + stages | **Implemented** — `--stage candidate|rc|beta|production` |
| **8** | AI UI exploration | **Future** — Code Pilot is heuristic, not Appium RL |
| **9** | Crashlytics + TLA+ | **N/A** for offline analyzer |

## Commands

```bash
apex gate app.apk --msv 28 --stage candidate --ci -o gate.json
bash scripts/audit_mobile_hard_gate.sh v0.4.7   # APEX Mobile release
```

## CI

- `CI` workflow runs `apex gate` on `tests/fixtures/sample_test.apk`
- Mobile handoff still requires `scripts/check_github_ci.sh --apk`
