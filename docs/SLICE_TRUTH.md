# Slice truth table

Repo-grounded status for hard-gate and security scanners.

| ID | File(s) | In runner | Tests | Notes |
|----|---------|-----------|-------|-------|
| manifest | `gate/scanners/static.py` | ✅ | `test_gate.py` | MSV, permissions |
| dex | `gate/scanners/static.py` | ✅ | `test_gate.py` | Structure / metadata |
| security | `gate/scanners/static.py` | ✅ | `test_gate.py` | Archive safety |
| secrets | `gate/scanners/secrets.py`, `secrets_scan.py` | ✅ | `test_blueprint_slices.py` | SECRETS-2 |
| native | `native_scan.py`, `gate/scanners/native.py` | ✅ | `test_blueprint_slices.py`, `test_cve_slices.py` | ELF hardening |
| api_watch | `api_watch.py`, `gate/scanners/api_watch.py` | ✅ | `test_cve_slices.py` | Replaces dex_watch |
| netsec | `netsec_scan.py`, `gate/scanners/netsec.py` | ✅ | `test_cve_slices.py` | user CA, cleartext |
| lint | `lint_scan.py`, `lint_rules.yaml` | ✅ | `test_cve_slices.py` | Decompile capped |
| obfuscation | `gate/scanners/obfuscation.py` | ✅ | `test_cve_slices.py` | Mapping file check |
| dependency | `dependency_scan.py`, `data/cve_db.json` | ✅ | `test_cve_slices.py` | Advisory CVE |
| dex_watch | `gate/scanners/dex_watch.py` | ⬜ removed | — | Redundant with api_watch |
| budgets | `gate/budgets.py` | ✅ | indirect | Timeouts |
| models | `gate/models.py` | ✅ | `test_cve_slices.py` | confidence/remediation |

Legend: ✅ done · 🟡 partial · ⬜ not wired

## Version

- **0.4.11** — full gate through CVE advisory slice
- **0.4.10** — SECRETS-2, native prelude, dex_watch, weights v1
