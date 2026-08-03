# APEX Completion Roadmap

Status as of **v0.4.11** (branch `cursor/complete-apex-app-5bc2`).

## Capability matrix

| Slice | Capability | Gate | security-scan | Status |
|-------|------------|------|---------------|--------|
| SECRETS-2 | DEX string pool + resource files | ✅ | ✅ | Shipped |
| NATIVE | ELF PIE, RELRO, 16K, stack protector, symbol watch | ✅ | ✅ | Shipped |
| API-1 | Xref + string watch (crypto, reflection) | ✅ | ✅ | Shipped |
| NETSEC-1 | network_security_config + cleartext | ✅ | ✅ | Shipped |
| LINT-1 | YAML regex on decompiled Java | ✅ | — | Shipped |
| XS-5 | Obfuscation / mapping detection | ✅ | — | Shipped |
| CVE-2 | Curated dependency/CVE advisory | ✅ (advisory) | ✅ | Shipped |
| Budgets | Per-scanner timeouts + lightweight fallback | ✅ | — | Shipped |
| Finding model | confidence + remediation | ✅ | — | Shipped |

## Gate weights (§5)

| Scanner | Weight |
|---------|--------|
| manifest | 0.15 |
| dex | 0.10 |
| security | 0.15 |
| secrets | 0.15 |
| native | 0.15 |
| api_watch | 0.10 |
| netsec | 0.05 |
| lint | 0.05 |
| dependency | 0.05 |
| obfuscation | 0.05 |

**Policy:** `dependency` never FAILs the gate by default (advisory WARN only).

## External validations

- **16 KB page size:** Google Play requirement **in force** for apps targeting API 35+ with native code (Nov 2025). Native scanner FAILs 16K misalignment when `minSdk ≥ 35`.
- **MobSF comparison:** Fair bar is APK-only static analysis (no dynamic analyzer, no Gradle upload).

## CLI

```bash
apex gate sample.apk --msv 28 --stage candidate --ci
apex update-db          # refresh ~/.apex/cve_db.json from bundle
apex security-scan sample.apk
```

## Out of scope

- iOS Mach-O native scanning
- Live CVE feed / OSV API (bundled DB + `update-db` only)

## Next slices (post-CVE)

- DEX xref at scale with native dex_reader backend
- Expanded CVE DB + optional online refresh
- Gate stage promotion in CI matrix
- Pydantic optional schema export for gate.json
