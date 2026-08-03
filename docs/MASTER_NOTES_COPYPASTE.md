# ═══════════════════════════════════════════════════════════════════════════════
# APEX — MASTER NOTES (scratch → finish)
# Copy everything below into your notes app. Repo: zowskyy/apex-android
# Canonical version: 0.4.11 · Branch: cursor/complete-apex-app-5bc2 · PR #4
# Patched: 2026-08-03 (Zero-Touch audit + repo-truth corrections)
# ═══════════════════════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────────────────────────
§0  ONE-PAGE “DO THIS IN ORDER” (scratch → shippable)
────────────────────────────────────────────────────────────────────────────────

1. CLONE + DEV ENV
   git clone https://github.com/zowskyy/apex-android
   cd apex-android
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -U pip wheel maturin
   pip install -e ".[dev,mcp]"
   maturin develop --release -m core/zip_reader/Cargo.toml
   maturin develop --release -m core/dex_reader/Cargo.toml
   bash scripts/release/check_version_sync.sh
   apex doctor && pytest -q && ruff check apex tests

2. RUN THE APP (desktop)
   apex inspect tests/fixtures/sample_test.apk
   apex gui                    # http://127.0.0.1:8765
   apex mobile                 # LAN for phone browser

3. SECURITY + GATE (CI policy)
   python scripts/generate_test_apk.py tests/fixtures/sample_test.apk
   apex security-scan tests/fixtures/sample_test.apk
   apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate --ci

4. BUILD APEX MOBILE APK (symlink path — repo default)
   export ANDROID_HOME="$HOME/Android/Sdk"
   bash wrappers/android/build_standalone.sh
   adb install -r wrappers/android/dist/apex-mobile.apk
   # Note: Android uses Chaquopy + symlinked apex/ (Groovy build.gradle).
   # Gradle wheel injection (core-wheel.whl) is NOT wired in v0.4.11.

5. PACKAGE RELEASES (local)
   bash scripts/release/sync_version.sh 0.4.11
   # Desktop — CI-style pre-built wheels (either env works):
   maturin build --release -m core/zip_reader/Cargo.toml -o dist/
   maturin build --release -m core/dex_reader/Cargo.toml -o dist/
   pip wheel . --no-deps -w dist/
   export CORE_WHEEL_DIR=dist
   # or: export CORE_WHEEL="dist/*.whl"
   bash scripts/package_desktop_release.sh 0.4.11 linux
   # Android packaging (after build_standalone + optional bundleRelease):
   bash scripts/package_android_release.sh 0.4.11

6. SHIP (GitHub)
   git tag v0.4.11 && git push origin v0.4.11
   → triggers release.yml: wheels → android + desktop → release-verify (gate APK) → publish + SHA256SUMS

7. OPTIONAL DRY-RUN (no tag)
   GitHub Actions → Release → workflow_dispatch → version 0.4.11-test

────────────────────────────────────────────────────────────────────────────────
§1  WHAT APEX IS (3 products, 1 engine)
────────────────────────────────────────────────────────────────────────────────

PRODUCT A — CLI (`apex` command)
  Fast inspect, deep analyze, decompile, decode/build, verify, diff, security-scan, gate

PRODUCT B — Desktop web UI
  apex gui (localhost) · apex mobile (LAN thin client for phone browser)

PRODUCT C — APEX Mobile APK
  Full Python engine on phone (Chaquopy). Package io.apex.standalone. Menu: Settings.

ENGINE — Python package `apex/` + optional Rust:
  apex_zip_reader (ZIP) · apex_dex_reader (DEX) · Androguard (AXML/ARSC/Java)

FINDING MODEL — dataclass in apex/gate/models.py (NOT Pydantic in v0.4.11)

NOT IN SCOPE (v0.4.11):
  iOS Mach-O scanning · live CVE/OSV API · dynamic malware execution · MobSF dynamic parity
  Kotlin DSL Gradle wheel inject (Groovy + symlink is the shipped mobile path)

────────────────────────────────────────────────────────────────────────────────
§2  REPOSITORY MAP (every important path)
────────────────────────────────────────────────────────────────────────────────

apex-android/
├── apex/                          # PYTHON ENGINE
│   ├── cli.py, workflows.py, analysis.py, web.py, web_security.py
│   ├── secrets_scan.py, native_scan.py, api_watch.py, netsec_scan.py
│   ├── lint_scan.py, lint_rules.yaml, dependency_scan.py, data/cve_db.json
│   ├── gate/                      # HARD GATE (runner, weights.toml, scanners/, budgets.py)
│   └── agent/, edition.py, mcp_server.py (Pro)
├── core/zip_reader, core/dex_reader, core/dex_parser  # Rust
├── wrappers/android/build_standalone.sh, dist/apex-mobile.apk
├── scripts/package_*_release.sh, release/sync_version.sh, check_version_sync.sh
├── .github/actions/build-core/, workflows/ci.yml, release.yml, dependabot.yml
├── tests/, docs/, pyproject.toml, Cargo.toml

────────────────────────────────────────────────────────────────────────────────
§3  DEPENDENCIES & TOOLCHAIN
────────────────────────────────────────────────────────────────────────────────

REQUIRED: Python 3.10+ · Rust + maturin · androguard, jinja2
MOBILE BUILD: Python 3.10 · Java 17 · Gradle 8.10 · Android SDK 34
OPTIONAL: apktool, apksigner, aapt2, adb

ENV VARS:
  ANDROID_HOME / ANDROID_SDK_ROOT
  APEX_GRADLE, APEX_GRADLE_VERSION=8.10.2
  CORE_WHEEL_DIR=dist          # CI desktop (folder of *.whl)
  CORE_WHEEL="dist/*.whl"       # local glob (quoted — see §23)
  APEX_LICENSE_KEY, APEX_ENTITLEMENT, APEX_AGENT_PROVIDER

────────────────────────────────────────────────────────────────────────────────
§4  pyproject.toml (apex-android package)
────────────────────────────────────────────────────────────────────────────────

[build-system]
requires = ["setuptools>=77", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "apex-android"
version = "0.4.11"
requires-python = ">=3.10"
dependencies = ["androguard>=4.1.4", "jinja2>=3.1.0"]

[project.optional-dependencies]
mcp = ["fastmcp>=2.0"]
dev = ["pytest>=8.0", "pytest-benchmark>=4.0", "ruff>=0.16.1", "fastmcp>=2.0"]

[project.scripts]
apex = "apex:main"

────────────────────────────────────────────────────────────────────────────────
§5  VERSION SYNC (three sources must match)
────────────────────────────────────────────────────────────────────────────────

__version__ in apex/version.py · version in pyproject.toml · Gradle versionName

  bash scripts/release/sync_version.sh 0.4.11
  bash scripts/release/check_version_sync.sh   # CI guard

versionCode = major*10000 + minor*100 + patch  (0.4.11 → 411)

────────────────────────────────────────────────────────────────────────────────
§6  FULL CLI REFERENCE
────────────────────────────────────────────────────────────────────────────────

apex inspect|analyze|decompile|decode|build|verify|roundtrip|diff|framework-check
apex security-scan <apk> · apex gate <apk> [--msv N] [--stage candidate] [--ci]
apex update-db · apex gui · apex mobile · apex standalone · apex doctor
apex wrapper · apex mcp · apex agent (Pro)

Exit codes: verify=2 · roundtrip=3 · security HIGH_RISK=4 · gate --ci fail=5

────────────────────────────────────────────────────────────────────────────────
§7  HARD GATE
────────────────────────────────────────────────────────────────────────────────

Weights (sum 1.0): manifest 0.15 · dex 0.10 · security 0.15 · secrets 0.15 · native 0.15
  api_watch 0.10 · netsec 0.05 · lint 0.05 · dependency 0.05 · obfuscation 0.05

Stages: candidate≥60 · rc≥85 · beta≥95 · production=100

dependency scanner: ADVISORY ONLY — never FAIL gate by default (HIGH CVE → WARN)

Finding fields: scanner, status, category, message, evidence, confidence, remediation

Config: apex/gate/weights.toml · Budgets: apex/gate/budgets.py

────────────────────────────────────────────────────────────────────────────────
§8  SECURITY-SCAN vs GATE
────────────────────────────────────────────────────────────────────────────────

security-scan — flat findings, verdict CLEAN|REVIEW|HIGH_RISK
gate — weighted score + blocking FAILs + lint + obfuscation

────────────────────────────────────────────────────────────────────────────────
§9  RUST BUILD
────────────────────────────────────────────────────────────────────────────────

maturin develop --release -m core/zip_reader/Cargo.toml
maturin develop --release -m core/dex_reader/Cargo.toml

maturin build --release -m core/zip_reader/Cargo.toml -o dist/
maturin build --release -m core/dex_reader/Cargo.toml -o dist/
pip wheel . --no-deps -w dist/

CI: .github/actions/build-core → core-wheels-{Linux|Windows|macOS}

────────────────────────────────────────────────────────────────────────────────
§10  ANDROID MOBILE
────────────────────────────────────────────────────────────────────────────────

DEFAULT BUILD (shipped):
  export ANDROID_HOME="$HOME/Android/Sdk"
  bash wrappers/android/build_standalone.sh
  → symlink apex/ into Chaquopy · Groovy build.gradle · assembleRelease

Package: io.apex.standalone · App name: APEX · Settings menu

First launch: wait 2–3 min · Optional PC: apex mobile → phone Settings → Desktop computer

Chaquopy pip (explicit, --no-deps): cryptography, cffi, lxml, androguard==4.1.4, jinja2, markupsafe, …

────────────────────────────────────────────────────────────────────────────────
§11  wrappers/android/build_standalone.sh (FULL)
────────────────────────────────────────────────────────────────────────────────

#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../" && pwd)"
STANDALONE="$HERE/standalone"
OUT_APK="$HERE/dist/apex-mobile.apk"
GRADLE="${APEX_GRADLE:-gradle}"

command -v "$GRADLE" && command -v python3.10
export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
[[ -d "$ANDROID_HOME" ]] || { echo "Android SDK missing" >&2; exit 1; }

mkdir -p "$HERE/dist"
PY_SRC="$STANDALONE/app/src/main/python"
mkdir -p "$PY_SRC" && rm -f "$PY_SRC/apex" && ln -sfn "$ROOT/apex" "$PY_SRC/apex"

export GRADLE_VERSION="${APEX_GRADLE_VERSION:-8.10.2}"
cd "$STANDALONE"
[[ -x ./gradlew ]] || gradle wrapper --gradle-version "$GRADLE_VERSION" --no-daemon
./gradlew clean assembleRelease --no-daemon
bash "$ROOT/scripts/smoke_android_engine_imports.sh"
cp -f "$STANDALONE/app/build/outputs/apk/release/app-release.apk" "$OUT_APK"

────────────────────────────────────────────────────────────────────────────────
§12  scripts/package_android_release.sh (FULL)
────────────────────────────────────────────────────────────────────────────────

#!/usr/bin/env bash
VERSION="${1:?}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/release-staging/android"
APK_SRC="$ROOT/wrappers/android/dist/apex-mobile.apk"
AAB_SRC="$ROOT/wrappers/android/standalone/app/build/outputs/bundle/release/app-release.aab"
rm -rf "$OUT" && mkdir -p "$OUT"
cp "$APK_SRC" "$OUT/APEX-Mobile-${VERSION}.apk"
cp scripts/release/INSTALL.txt "$OUT/INSTALL.txt"
[[ -f "$AAB_SRC" ]] && cp "$AAB_SRC" "$OUT/APEX-Mobile-${VERSION}.aab"
( cd "$OUT" && zip -j "APEX-Mobile-${VERSION}-android.zip" APEX-Mobile-${VERSION}.apk INSTALL.txt )

────────────────────────────────────────────────────────────────────────────────
§13  scripts/package_desktop_release.sh (logic)
────────────────────────────────────────────────────────────────────────────────

Usage: scripts/package_desktop_release.sh <version> <linux|windows|macos>

MODES (first match wins):
  1. CORE_WHEEL_DIR=dist     — copy dist/*.whl (CI)
  2. CORE_WHEEL="dist/*.whl" — glob expand in bash (quoted pattern)
  3. else                    — maturin + pip wheel from source

Then: pip download androguard, jinja2, fastmcp
Copy LICENSE, README, pyproject, INSTALL.txt
Copy wrappers/ EXCLUDING android/standalone (saves ~200MB in desktop bundles)
Platform install script + tar.gz / zip archive

CI:
  CORE_WHEEL_DIR=dist bash scripts/package_desktop_release.sh 0.4.11 linux

Local:
  export CORE_WHEEL="dist/*.whl"
  bash scripts/package_desktop_release.sh 0.4.11 linux

────────────────────────────────────────────────────────────────────────────────
§14  scripts/release/sync_version.sh
────────────────────────────────────────────────────────────────────────────────

bash scripts/release/sync_version.sh <version>
Updates pyproject.toml, apex/version.py, build.gradle versionName + versionCode

bash scripts/release/check_version_sync.sh
Verifies all three match (runs in ci.yml)

────────────────────────────────────────────────────────────────────────────────
§15  apex/gate/weights.toml
────────────────────────────────────────────────────────────────────────────────

[weights]
manifest = 0.15
dex = 0.10
security = 0.15
secrets = 0.15
native = 0.15
api_watch = 0.10
netsec = 0.05
lint = 0.05
dependency = 0.05
obfuscation = 0.05

────────────────────────────────────────────────────────────────────────────────
§16  apex/lint_rules.yaml
────────────────────────────────────────────────────────────────────────────────

trust-all-trustmanager · trust-all-hostname · webview-js-interface
webview-js-enabled · world-readable · log-secrets
(See repo file for full regex patterns)

────────────────────────────────────────────────────────────────────────────────
§17  apex/data/cve_db.json
────────────────────────────────────────────────────────────────────────────────

package_prefix + version_regex + vulnerabilities[{below, cve, severity}]
confidence: prefix-only | version-confirmed
apex update-db → ~/.apex/cve_db.json

────────────────────────────────────────────────────────────────────────────────
§18  API WATCH WATCHLISTS
────────────────────────────────────────────────────────────────────────────────

crypto.py: Cipher, MessageDigest, SecretKeySpec, IvParameterSpec
reflection.py: DexClassLoader, PathClassLoader, Class.forName, Method.invoke

────────────────────────────────────────────────────────────────────────────────
§19  CI / GITHUB ACTIONS MAP
────────────────────────────────────────────────────────────────────────────────

ci.yml           — ruff, pytest, check_version_sync, gate sample APK, cargo test
pr-checks.yml    — build-core wheels + import smoke
hard-gate.yml    — scripts/hard_gate.sh
android-standalone.yml — PR apex-mobile-apk artifact
dependabot.yml   — weekly pip, cargo, github-actions
release.yml      — full DAG:

  prepare
    → core-build [linux, windows, macos] → core-wheels-{OS}
    → android (build_standalone + bundleRelease + package_android)
    → desktop-linux / desktop-windows / desktop-macos (CORE_WHEEL_DIR=dist)
    → release-verify (tag only) — apex gate on APEX-Mobile-*.apk → gate-release.json
    → publish (tag only) — all artifacts + SHA256SUMS

RELEASE ARTIFACTS:
  APEX-Mobile-{ver}.apk / .aab / .zip
  APEX-{ver}-linux-x64.tar.gz · windows-x64.zip · macos.zip
  gate-release.json (tag releases)
  SHA256SUMS (in publish bundle)

DRY-RUN: Actions → Release → workflow_dispatch → 0.4.11-test

────────────────────────────────────────────────────────────────────────────────
§20  RELEASE CHECKLIST (tag vX.Y.Z)
────────────────────────────────────────────────────────────────────────────────

[ ] bash scripts/release/sync_version.sh X.Y.Z
[ ] bash scripts/release/check_version_sync.sh
[ ] pytest -q && ruff check apex tests && cargo test --workspace
[ ] apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate --ci
[ ] Test local packaging: CORE_WHEEL_DIR=dist or CORE_WHEEL="dist/*.whl"
[ ] git commit && git tag vX.Y.Z && git push && git push --tags
[ ] Verify release.yml: release-verify green + SHA256SUMS on GitHub Release
[ ] Smoke: desktop bundle + apex-mobile.apk on device/emulator

────────────────────────────────────────────────────────────────────────────────
§21  BUILD FROM SCRATCH (9 phases)
────────────────────────────────────────────────────────────────────────────────

1 Skeleton (pyproject, cli, analysis) · 2 Rust cores · 3 workflows
4 Web UI + disclaimer · 5 Hard gate scanners · 6 Mobile Chaquopy
7 CI workflows · 8 Packaging scripts · 9 Pro (MCP, Code Pilot)

────────────────────────────────────────────────────────────────────────────────
§22  TEST COMMANDS
────────────────────────────────────────────────────────────────────────────────

python scripts/generate_test_apk.py tests/fixtures/sample_test.apk
bash scripts/release/check_version_sync.sh
pytest -q
ruff check apex tests
cargo test --workspace
apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate --ci
bash scripts/hard_gate.sh

────────────────────────────────────────────────────────────────────────────────
§23  TROUBLESHOOTING
────────────────────────────────────────────────────────────────────────────────

| Problem | Fix |
|---------|-----|
| Version mismatch | bash scripts/release/sync_version.sh X.Y.Z |
| CORE_WHEEL no match | Use export CORE_WHEEL="dist/*.whl" (quoted) |
| Gradle not found | APEX_GRADLE=gradle, install Gradle 8.x |
| python3.10 missing | Required for Chaquopy mobile build |
| ANDROID_HOME | export ANDROID_HOME=$HOME/Android/Sdk |
| 0 DEX on phone | Real APK; lightweight on-device DEX tier |
| dependency FAIL in gate | Should WARN only — advisory policy |
| Gate weights sum | Edit apex/gate/weights.toml (must = 1.0) |
| Chaquopy import fail | Add pip package to build.gradle |

────────────────────────────────────────────────────────────────────────────────
§24  DOCS INDEX
────────────────────────────────────────────────────────────────────────────────

docs/README.md                — Start here (index)
docs/MASTER_NOTES_COPYPASTE.md — This file
docs/BLUEPRINT_GUIDE.md       — Operations how-to
docs/AUDIT_RESPONSE_0.4.11.md — External audit + policy
docs/COMPLETION_ROADMAP.md    — Capability matrix
docs/SLICE_TRUTH.md           — Implementation status
docs/CI_RELEASE_BLUEPRINT.md  — Release DAG
docs/BUILD_STANDALONE_APK.md  — Mobile build
README.md                     — User install + CLI

────────────────────────────────────────────────────────────────────────────────
§25  LINKS
────────────────────────────────────────────────────────────────────────────────

Repo:     https://github.com/zowskyy/apex-android
Releases: https://github.com/zowskyy/apex-android/releases
Actions:  https://github.com/zowskyy/apex-android/actions
PR #4:    https://github.com/zowskyy/apex-android/pull/4

════════════════════════════════════════════════════════════════════════════════
END OF MASTER NOTES — repo-truth patched 2026-08-03
════════════════════════════════════════════════════════════════════════════════
