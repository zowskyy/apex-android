# ═══════════════════════════════════════════════════════════════════════════════
# APEX — MASTER NOTES (scratch → finish)
# Copy everything below into your notes app. Repo: zowskyy/apex-android
# Canonical version: 0.4.11 · Branch: cursor/complete-apex-app-5bc2 · PR #4
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
   apex doctor && pytest -q && ruff check apex tests

2. RUN THE APP (desktop)
   apex inspect tests/fixtures/sample_test.apk
   apex gui                    # http://127.0.0.1:8765
   apex mobile                 # LAN for phone browser

3. SECURITY + GATE (CI policy)
   python scripts/generate_test_apk.py tests/fixtures/sample_test.apk
   apex security-scan tests/fixtures/sample_test.apk
   apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate --ci

4. BUILD APEX MOBILE APK
   export ANDROID_HOME="$HOME/Android/Sdk"
   bash wrappers/android/build_standalone.sh
   adb install -r wrappers/android/dist/apex-mobile.apk

5. PACKAGE RELEASES (local)
   bash scripts/release/sync_version.sh 0.4.11
   bash wrappers/android/build_standalone.sh
   cd wrappers/android/standalone && ./gradlew bundleRelease
   bash scripts/package_android_release.sh 0.4.11
   bash scripts/package_desktop_release.sh 0.4.11 linux

6. SHIP (GitHub)
   git tag v0.4.11 && git push origin v0.4.11
   → triggers .github/workflows/release.yml (wheels + android + desktop + publish)

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

NOT IN SCOPE (v0.4.11):
  iOS Mach-O scanning · live CVE/OSV API · dynamic malware execution · MobSF dynamic parity

────────────────────────────────────────────────────────────────────────────────
§2  REPOSITORY MAP (every important path)
────────────────────────────────────────────────────────────────────────────────

apex-android/
├── apex/                          # PYTHON ENGINE (heart of everything)
│   ├── __init__.py                # Public API exports
│   ├── __main__.py                # python -m apex
│   ├── cli.py                     # All CLI subcommands
│   ├── version.py                 # __version__ single source (also pyproject)
│   ├── analysis.py                # inspect_apk, dex_metadata, manifest, ZIP safety
│   ├── workflows.py               # analyze, decompile, decode, build, security_scan
│   ├── web.py                     # Local HTTP UI
│   ├── web_security.py            # Workspace path containment (LAN safety)
│   ├── secrets_scan.py            # SECRETS-2: DEX strings + resource files
│   ├── native_scan.py             # ELF .so hardening (PIE, RELRO, 16K, symbols)
│   ├── api_watch.py               # DEX xref + string watchlists
│   ├── netsec_scan.py             # network_security_config XML
│   ├── lint_scan.py               # YAML regex on decompiled Java
│   ├── lint_rules.yaml            # Default lint rules
│   ├── dependency_scan.py         # Curated CVE fingerprinting
│   ├── data/cve_db.json           # Bundled CVE library DB
│   ├── device_profile.py          # On-device RAM/engine tier limits
│   ├── engine_validate.py         # Parser validation helpers
│   ├── android_boot.py            # Mobile engine bootstrap
│   ├── disclaimer.py              # Required acceptance for GUI/mobile
│   ├── edition.py                 # Community vs Pro gating
│   ├── mcp_server.py              # Pro MCP integration
│   ├── agent/                     # Pro Code Pilot
│   ├── gate/                      # HARD GATE SYSTEM
│   │   ├── runner.py              # run_hard_gate(), write_gate_report()
│   │   ├── models.py              # GateFinding, GateReport, confidence
│   │   ├── weights.toml           # Scanner weights (must sum 1.0)
│   │   ├── weights.py             # Load/validate weights
│   │   ├── budgets.py             # Per-scanner timeouts
│   │   └── scanners/
│   │       ├── static.py          # manifest, dex, security
│   │       ├── secrets.py         # secrets gate wrapper
│   │       ├── native.py          # native gate wrapper
│   │       ├── api_watch.py       # crypto + reflection watchlists
│   │       ├── netsec.py
│   │       ├── lint.py
│   │       ├── obfuscation.py
│   │       ├── dependency.py      # advisory only — never FAIL
│   │       └── watchlists/
│   │           ├── crypto.py
│   │           └── reflection.py
│
├── core/                          # RUST EXTENSIONS
│   ├── zip_reader/                # apex_zip_reader wheel (maturin)
│   ├── dex_reader/                # apex_dex_reader wheel (maturin)
│   └── dex_parser/                # Internal Rust lib for dex_reader
│
├── wrappers/
│   ├── android/
│   │   ├── build_standalone.sh    # BUILD MOBILE APK (symlink apex → Chaquopy)
│   │   ├── dist/apex-mobile.apk   # Output APK
│   │   └── standalone/            # Gradle + Chaquopy project
│   │       ├── app/build.gradle   # Chaquopy pip deps, versionName
│   │       └── app/src/main/python/mutf8/  # Vendored shim for Androguard
│   ├── linux/ macos/ windows/ ios/ docker/
│   └── README.md
│
├── scripts/
│   ├── generate_test_apk.py       # Fixture APK for tests/gate
│   ├── hard_gate.sh               # 9-slice local gate script
│   ├── package_android_release.sh
│   ├── package_desktop_release.sh
│   ├── smoke_android_engine_imports.sh
│   └── release/
│       ├── sync_version.sh        # Sync version → pyproject, version.py, Gradle
│       ├── install-linux.sh       # Offline desktop install from wheels
│       ├── install-macos.sh
│       ├── install-windows.ps1
│       ├── INSTALL.txt
│       └── RELEASE_NOTES.md
│
├── .github/
│   ├── actions/build-core/action.yml   # Build 3 wheels on CI
│   └── workflows/
│       ├── ci.yml                 # ruff, pytest, gate, cargo
│       ├── pr-checks.yml          # wheel smoke + core tests
│       ├── hard-gate.yml
│       ├── android-standalone.yml # PR APK artifact
│       └── release.yml            # Full release DAG
│
├── tests/                         # pytest suites
├── docs/                          # All blueprint docs (see §16)
├── pyproject.toml                 # apex-android setuptools package
├── Cargo.toml                     # Rust workspace
└── README.md

────────────────────────────────────────────────────────────────────────────────
§3  DEPENDENCIES & TOOLCHAIN
────────────────────────────────────────────────────────────────────────────────

REQUIRED (dev):
  Python 3.10+ (3.12 for desktop CI; 3.10 for Chaquopy mobile)
  Rust stable + maturin
  pip packages: androguard>=4.1.4, jinja2>=3.1.0

OPTIONAL (apex doctor reports):
  apktool          — resource/XML rebuild backend
  apksigner        — signing rebuilt APKs
  aapt2, adb, Java 17 — Android tooling
  Gradle 8.10.x    — mobile APK build
  Android SDK 34   — platforms;android-34, build-tools;34.0.0

ENV VARS:
  ANDROID_HOME / ANDROID_SDK_ROOT     — Android SDK path
  APEX_GRADLE=gradle                  — Gradle binary name
  APEX_GRADLE_VERSION=8.10.2
  APEX_APKTOOL_JAR=...                — apktool path
  APEX_APKSIGNER=...                  — apksigner path
  APEX_LICENSE_KEY / APEX_ENTITLEMENT — Pro edition
  APEX_AGENT_PROVIDER                 — Code Pilot provider
  CORE_WHEEL_DIR=dist                 — CI desktop packaging (pre-built wheels)
  PYTHON=python3                      — install scripts

────────────────────────────────────────────────────────────────────────────────
§4  pyproject.toml (apex-android package)
────────────────────────────────────────────────────────────────────────────────

[build-system]
requires = ["setuptools>=77", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "apex-android"
version = "0.4.11"
description = "Secure Android package inspection, decompilation, and rebuilding"
requires-python = ">=3.10"
dependencies = ["androguard>=4.1.4", "jinja2>=3.1.0"]

[project.optional-dependencies]
mcp = ["fastmcp>=2.0"]
postgres = ["psycopg[binary]>=3.0"]
dev = ["pytest>=8.0", "pytest-benchmark>=4.0", "ruff>=0.16.1", "fastmcp>=2.0"]

[project.scripts]
apex = "apex:main"

[tool.setuptools.packages.find]
include = ["apex*"]

────────────────────────────────────────────────────────────────────────────────
§5  apex/version.py (keep in sync on release)
────────────────────────────────────────────────────────────────────────────────

__version__ = "0.4.11"
PRODUCT_NAME = "APEX"
PRODUCT_SLUG = "apex-android"

Sync all version files:
  bash scripts/release/sync_version.sh 0.4.11
  # Updates: pyproject.toml, apex/version.py, Gradle versionName + versionCode
  # versionCode formula: major*10000 + minor*100 + patch  (0.4.11 → 411)

────────────────────────────────────────────────────────────────────────────────
§6  FULL CLI REFERENCE
────────────────────────────────────────────────────────────────────────────────

CORE ANALYSIS:
  apex inspect <apk> [--files] [-o out.json]
  apex analyze <apk> [--out dir] [--abi abis] [--db sqlite] [--pg dsn]
  apex decompile <apk> [--out dir] [--mapping map.txt] [--no-smali]
  apex decode <apk> [--out dir] [--backend auto|raw|apktool]
  apex build <project> [--out apk] [--keystore ...]
  apex verify <apk> [-o out.json]
  apex roundtrip <apk> [--work dir] [-o out.json]
  apex diff <left> <right> [-o out.json]
  apex framework-check <apk>

SECURITY:
  apex security-scan <apk> [-o out.json]
  apex gate <apk> [--msv 28] [--stage candidate|rc|beta|production] [--ci] [-o gate.json]
  apex update-db                    # ~/.apex/cve_db.json from bundle

UI / MOBILE COMPANION:
  apex gui [--host 127.0.0.1] [--port 8765] [--workspace .apex-web]
  apex mobile [--port 8765]         # 0.0.0.0 LAN
  apex standalone [--port 8765]       # inside phone APK engine mode

META:
  apex doctor
  apex wrapper [list|install]
  apex mcp [show-key]               # Pro
  apex agent <prompt> [--apk path]  # Pro Code Pilot

CLI EXIT CODES:
  verify invalid → 2 · roundtrip fail → 3 · security high risk → 4 · gate fail --ci → 5

────────────────────────────────────────────────────────────────────────────────
§7  HARD GATE (complete reference)
────────────────────────────────────────────────────────────────────────────────

RUN:
  apex gate sample.apk --msv 28 --stage candidate --ci -o gate.json

STAGE MIN SCORES:
  candidate=60 · rc=85 · beta=95 · production=100

WEIGHTS (apex/gate/weights.toml — must sum 1.0):
  manifest=0.15   dex=0.10   security=0.15   secrets=0.15   native=0.15
  api_watch=0.10  netsec=0.05 lint=0.05       dependency=0.05 obfuscation=0.05

SCANNERS (what each checks):
  manifest    — minSdk vs MSV, sensitive permissions, parse errors
  dex         — DEX structure/metadata
  security    — ZIP traversal, zip bombs, archive safety
  secrets     — DEX string pool + resource files (SECRETS-2)
  native      — ELF: PIE, exec stack, RELRO, 16K align (FAIL if minSdk≥35),
                stack protector signal, dangerous symbols (system, strcpy…)
  api_watch   — Cipher/MD5/DexClassLoader/Method.invoke xref + string hints
  netsec      — user CA trust, cleartext in network_security_config
  lint        — decompile (capped) + lint_rules.yaml regex
  obfuscation — ProGuard mapping present vs short class names
  dependency  — prefix + version-confirmed CVE from cve_db.json (WARN only)

FINDING MODEL (gate.json):
  scanner, status (PASS|FAIL|WARN), category, message, evidence,
  confidence (HIGH|MEDIUM|LOW), remediation
  Policy: LOW-confidence FAIL → WARN; dependency never FAIL

RUNNER FLOW (apex/gate/runner.py):
  resolve_android_package() → run scanners with budgets → weighted score → gate_passed

BUDGETS (apex/gate/budgets.py timeouts in seconds):
  manifest=15 dex=30 security=20 secrets=45 native=30 api_watch=60
  netsec=15 lint=180 obfuscation=30 dependency=45
  api_watch timeout → lightweight string-pool fallback

────────────────────────────────────────────────────────────────────────────────
§8  SECURITY-SCAN vs GATE
────────────────────────────────────────────────────────────────────────────────

security-scan (workflows.security_scan):
  Archive safety, manifest flags, secrets, native, netsec, api_watch, dependency
  Verdict: CLEAN | REVIEW | HIGH_RISK | INVALID
  No weighted score — flat finding list

gate (run_hard_gate):
  All gate scanners + lint + obfuscation
  Weighted score + blocking FAIL list + stage threshold

────────────────────────────────────────────────────────────────────────────────
§9  RUST BUILD (local + CI)
────────────────────────────────────────────────────────────────────────────────

LOCAL DEV:
  maturin develop --release -m core/zip_reader/Cargo.toml
  maturin develop --release -m core/dex_reader/Cargo.toml

BUILD WHEELS:
  maturin build --release -m core/zip_reader/Cargo.toml -o dist/
  maturin build --release -m core/dex_reader/Cargo.toml -o dist/
  pip wheel . --no-deps -w dist/
  # → dist/apex_zip_reader-*.whl, apex_dex_reader-*.whl, apex_android-*.whl

CARGO WORKSPACE (Cargo.toml):
  members: core/zip_reader, core/dex_parser, core/dex_reader

CI COMPOSITE (.github/actions/build-core/action.yml):
  Patches version → builds 3 wheels → uploads core-wheels-{Linux|Windows|macOS}

────────────────────────────────────────────────────────────────────────────────
§10  ANDROID MOBILE — build from scratch
────────────────────────────────────────────────────────────────────────────────

PREREQS:
  Android SDK (API 34), Java 17, Gradle 8.10, Python 3.10 (Chaquopy)

HOW IT WORKS:
  1. build_standalone.sh symlinks repo apex/ → standalone/app/src/main/python/apex
  2. Chaquopy pip installs androguard + transitive deps (explicit list in build.gradle)
  3. gradlew assembleRelease → app-release.apk → copied to dist/apex-mobile.apk
  4. smoke_android_engine_imports.sh checks APK size, chaquopy assets, apex bundled

BUILD:
  export ANDROID_HOME="$HOME/Android/Sdk"
  bash wrappers/android/build_standalone.sh

APP IDENTITY:
  namespace / applicationId: io.apex.standalone
  App label on phone: APEX
  Settings menu (not "Server URL")

CHAQUOPY PIP (build.gradle — must list transients explicitly):
  cryptography, cffi, pycparser, lxml, asn1crypto, networkx, click, colorama,
  pyyaml, markupsafe, jinja2, pygments, apkInspector, typing_extensions,
  loguru, androguard==4.1.4
  options("--no-deps") on pip block

ON-DEVICE USAGE:
  1. Install apex-mobile.apk
  2. Accept disclaimer
  3. Wait 2-3 min first launch
  4. Pick APK to analyze
  5. Optional PC: apex mobile on PC → phone Settings → Desktop computer

TROUBLESHOOTING:
  0 DEX / generic ZIP → use real APK; on-device uses lightweight DEX (not full androguard xref)
  OOM on device → dex_lightweight tier in device_profile.py
  markupsafe missing → Chaquopy pip list must include markupsafe

────────────────────────────────────────────────────────────────────────────────
§11  wrappers/android/build_standalone.sh (FULL)
────────────────────────────────────────────────────────────────────────────────

#!/usr/bin/env bash
# Build the full on-device APEX APK (embedded Python engine via Chaquopy).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../" && pwd)"
STANDALONE="$HERE/standalone"
OUT_APK="$HERE/dist/apex-mobile.apk"
GRADLE="${APEX_GRADLE:-gradle}"

if ! command -v "$GRADLE" >/dev/null 2>&1; then
  echo "Gradle not found. Install Gradle 8.x or set APEX_GRADLE." >&2
  exit 1
fi

if ! command -v python3.10 >/dev/null 2>&1; then
  echo "python3.10 is required for Chaquopy pip installs." >&2
  exit 1
fi

export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"

mkdir -p "$HERE/dist"
PY_SRC="$STANDALONE/app/src/main/python"
mkdir -p "$PY_SRC"
rm -f "$PY_SRC/apex"
ln -sfn "$ROOT/apex" "$PY_SRC/apex"

export GRADLE_VERSION="${APEX_GRADLE_VERSION:-8.10.2}"
cd "$STANDALONE"

if [[ ! -x ./gradlew ]]; then
  gradle wrapper --gradle-version "$GRADLE_VERSION" --no-daemon
fi

./gradlew clean assembleRelease --no-daemon
bash "$ROOT/scripts/smoke_android_engine_imports.sh"

cp -f "$STANDALONE/app/build/outputs/apk/release/app-release.apk" "$OUT_APK"
echo "Built: $OUT_APK"

────────────────────────────────────────────────────────────────────────────────
§12  scripts/package_android_release.sh (FULL)
────────────────────────────────────────────────────────────────────────────────

#!/usr/bin/env bash
# Usage: scripts/package_android_release.sh <version>
set -euo pipefail
VERSION="${1:?}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/release-staging/android"
APK_SRC="$ROOT/wrappers/android/dist/apex-mobile.apk"
AAB_SRC="$ROOT/wrappers/android/standalone/app/build/outputs/bundle/release/app-release.aab"

rm -rf "$OUT" && mkdir -p "$OUT"
cp "$APK_SRC" "$OUT/APEX-Mobile-${VERSION}.apk"
cp scripts/release/INSTALL.txt "$OUT/INSTALL.txt"
[[ -f "$AAB_SRC" ]] && cp "$AAB_SRC" "$OUT/APEX-Mobile-${VERSION}.aab"

ZIP_FILES=("APEX-Mobile-${VERSION}.apk" "INSTALL.txt")
[[ -f "$OUT/APEX-Mobile-${VERSION}.aab" ]] && ZIP_FILES+=("APEX-Mobile-${VERSION}.aab")
( cd "$OUT" && zip -j "APEX-Mobile-${VERSION}-android.zip" "${ZIP_FILES[@]}" )

────────────────────────────────────────────────────────────────────────────────
§13  scripts/package_desktop_release.sh (logic)
────────────────────────────────────────────────────────────────────────────────

Usage: scripts/package_desktop_release.sh <version> <linux|windows|macos>

IF CORE_WHEEL_DIR set and contains *.whl → copy pre-built wheels (CI mode)
ELSE → maturin build zip_reader + dex_reader + pip wheel apex-android (local dev)

Then: pip download androguard, jinja2, fastmcp into wheels/
Copy LICENSE, README, pyproject, wrappers/, INSTALL.txt
Platform install script → install.sh or install.ps1
Archive: linux=.tar.gz · macos=.zip · windows=.zip (Compress-Archive)

CI usage:
  CORE_WHEEL_DIR=dist bash scripts/package_desktop_release.sh 0.4.11 linux

────────────────────────────────────────────────────────────────────────────────
§14  scripts/release/sync_version.sh (FULL)
────────────────────────────────────────────────────────────────────────────────

#!/usr/bin/env bash
# Usage: scripts/release/sync_version.sh <version>
set -euo pipefail
VERSION="${1:?}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python <<PY
import pathlib, re
version = "${VERSION}"
numeric = version.split("-", 1)[0]
parts = numeric.split(".")
while len(parts) < 3: parts.append("0")
major, minor, patch = (int(p) for p in parts[:3])
version_code = major * 10000 + minor * 100 + patch
root = pathlib.Path("${ROOT}")
# pyproject.toml, apex/version.py, build.gradle versionName + versionCode
PY

────────────────────────────────────────────────────────────────────────────────
§15  apex/gate/weights.toml (FULL)
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
§16  apex/lint_rules.yaml (FULL)
────────────────────────────────────────────────────────────────────────────────

rules:
  - id: trust-all-trustmanager
    pattern: 'checkServerTrusted\\([^)]*\\)\\s*\\{[^}]*return\\s*;'
    severity: high
    message: "TrustManager may accept all certificates — MITM risk"
    applies_to: "**/*.java"
  - id: trust-all-hostname
    pattern: 'verify\\([^)]*\\)\\s*\\{[^}]*return\\s+true'
    severity: high
    message: "HostnameVerifier may accept all hostnames — MITM risk"
    applies_to: "**/*.java"
  - id: webview-js-interface
    pattern: 'addJavascriptInterface\\('
    severity: medium
    message: "WebView addJavascriptInterface — review for RCE on older APIs"
    applies_to: "**/*.java"
  - id: webview-js-enabled
    pattern: 'setJavaScriptEnabled\\(\\s*true\\s*\\)'
    severity: low
    message: "WebView JavaScript enabled — review exposure surface"
    applies_to: "**/*.java"
  - id: world-readable
    pattern: 'MODE_WORLD_READABLE|MODE_WORLD_WRITEABLE'
    severity: medium
    message: "Legacy world-readable/writable file mode"
    applies_to: "**/*.java"
  - id: log-secrets
    pattern: 'Log\\.[dv]\\([^)]*(password|token|secret|apikey|api_key)'
    severity: low
    message: "Logging may leak credential-like variable names"
    applies_to: "**/*.java"

────────────────────────────────────────────────────────────────────────────────
§17  apex/data/cve_db.json (schema + example)
────────────────────────────────────────────────────────────────────────────────

{
  "schema_version": 1,
  "libraries": [
    {
      "package_prefix": "okhttp3",
      "name": "OkHttp",
      "version_regex": "okhttp/(\\d+\\.\\d+(?:\\.\\d+)?)",
      "vulnerabilities": [
        { "below": "4.9.2", "cve": "CVE-2021-0341", "severity": "high" }
      ]
    }
  ]
}
confidence: "prefix-only" | "version-confirmed"
Update user cache: apex update-db → ~/.apex/cve_db.json

────────────────────────────────────────────────────────────────────────────────
§18  API WATCH WATCHLISTS (apex/gate/scanners/watchlists/)
────────────────────────────────────────────────────────────────────────────────

CRYPTO (crypto.py):
  Cipher.getInstance + string hint ECB|DES|RC4
  MessageDigest.getInstance + MD5|SHA-1
  SecretKeySpec, IvParameterSpec constructors

REFLECTION (reflection.py):
  DexClassLoader, PathClassLoader, Class.forName, Method.invoke

Engine: apex/api_watch.py — collect_apk_dex_index → scan_watchlist (edges + strings)

────────────────────────────────────────────────────────────────────────────────
§19  CI / GITHUB ACTIONS MAP
────────────────────────────────────────────────────────────────────────────────

ci.yml          — push/PR: venv, ruff, pytest, gate on sample APK, cargo test
pr-checks.yml   — build-core wheels + import smoke + core pytest
hard-gate.yml   — scripts/hard_gate.sh (9 slices)
android-standalone.yml — build_standalone → apex-mobile-apk artifact
release.yml     — TAG v* or workflow_dispatch:

  DAG:
    prepare (resolve version)
      → core-build matrix [ubuntu, windows, macos] → core-wheels-{OS}
      → android (build_standalone + bundleRelease + package_android)
      → desktop-linux / desktop-windows / desktop-macos (CORE_WHEEL_DIR=dist)
      → publish (tag only) → GitHub Release with all artifacts

RELEASE ARTIFACTS:
  APEX-Mobile-{ver}.apk / .aab / .zip
  APEX-{ver}-linux-x64.tar.gz
  APEX-{ver}-windows-x64.zip
  APEX-{ver}-macos.zip

MANUAL DRY-RUN:
  Actions → Release → Run workflow → version 0.4.11-test

LOCAL GATE SCRIPT:
  bash scripts/hard_gate.sh           # G1-G8
  bash scripts/hard_gate.sh --ship    # + GitHub CI check
  bash scripts/hard_gate.sh --release v0.4.11

────────────────────────────────────────────────────────────────────────────────
§20  RELEASE CHECKLIST (tag vX.Y.Z)
────────────────────────────────────────────────────────────────────────────────

[ ] bash scripts/release/sync_version.sh X.Y.Z
[ ] pytest -q && ruff check apex tests && cargo test --workspace
[ ] apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate --ci
[ ] git commit -am "Release vX.Y.Z" && git tag vX.Y.Z && git push && git push --tags
[ ] Wait release.yml → verify GitHub Release assets
[ ] Smoke: install desktop bundle + apex-mobile.apk on device (physical or emulator)
[ ] Verify SHA256SUMS on GitHub Release matches downloaded assets

────────────────────────────────────────────────────────────────────────────────
§21  BUILD FROM SCRATCH (phases if recreating repo)
────────────────────────────────────────────────────────────────────────────────

PHASE 1 — Skeleton
  pyproject.toml (setuptools apex-android)
  apex/__init__.py, cli.py, version.py
  apex/analysis.py — ZIP inventory, manifest via Androguard, dex_metadata

PHASE 2 — Rust
  core/zip_reader (pyo3 ZIP) · core/dex_parser · core/dex_reader
  maturin develop in CI and local dev

PHASE 3 — Workflows
  workflows.py: inspect, analyze, decompile, decode, build, verify, roundtrip,
                security_scan, diff

PHASE 4 — Web UI
  web.py loopback server · web_security.py path containment · disclaimer

PHASE 5 — Hard gate
  gate/models.py · gate/runner.py · gate/weights.toml
  scanners/static, secrets, security
  Add incrementally: native_scan, secrets_scan SECRETS-2, api_watch, netsec,
  lint, obfuscation, dependency_scan + cve_db.json

PHASE 6 — Mobile
  wrappers/android/standalone Gradle + Chaquopy
  build_standalone.sh symlink · mutf8 shim · device_profile.py · android_boot.py
  smoke_android_engine_imports.sh

PHASE 7 — CI
  ci.yml → hard-gate.yml → android-standalone.yml
  build-core composite → release.yml DAG

PHASE 8 — Packaging
  package_android_release.sh · package_desktop_release.sh · sync_version.sh
  install-linux.sh / macos / windows.ps1

PHASE 9 — Pro (optional)
  edition.py · mcp_server.py · agent/ Code Pilot

────────────────────────────────────────────────────────────────────────────────
§22  TEST COMMANDS
────────────────────────────────────────────────────────────────────────────────

python scripts/generate_test_apk.py tests/fixtures/sample_test.apk
pytest -q
pytest tests/test_gate.py tests/test_cve_slices.py tests/test_blueprint_slices.py -q
ruff check apex tests
cargo test --workspace
apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate --ci
bash scripts/hard_gate.sh

────────────────────────────────────────────────────────────────────────────────
§23  TROUBLESHOOTING QUICK TABLE
────────────────────────────────────────────────────────────────────────────────

| Problem | Fix |
|---------|-----|
| Gate weights error "sum not 1.0" | Edit apex/gate/weights.toml |
| Gradle not found | Install Gradle 8.x or APEX_GRADLE |
| python3.10 missing (mobile) | Install Python 3.10 for Chaquopy |
| ANDROID_HOME | export ANDROID_HOME=$HOME/Android/Sdk |
| 0 DEX on phone | Real APK; lightweight parser; not OOM xref |
| Gate FAIL dependency | Should only WARN — check scanner policy |
| Desktop wheel mismatch | Use CORE_WHEEL_DIR=dist on same OS wheels |
| apktool rebuild fails | apex decode --backend apktool; install apktool |
| Web LAN file read | web_security workspace containment |
| Chaquopy import fail | Add missing pip package to build.gradle |

────────────────────────────────────────────────────────────────────────────────
§24  DOCS INDEX (in repo)
────────────────────────────────────────────────────────────────────────────────

docs/BLUEPRINT_GUIDE.md       — Operations how-to (v0.4.11)
docs/MASTER_NOTES_COPYPASTE.md — This file
docs/COMPLETION_ROADMAP.md    — Capability matrix
docs/SLICE_TRUTH.md           — Implementation status table
docs/CI_RELEASE_BLUEPRINT.md  — Release DAG audited
docs/BUILD_STANDALONE_APK.md  — Mobile build + VS Code tasks
docs/HARD_GATE_SLICES.md      — Original 9-slice design
docs/PROJECT_BLUEPRINT.md     — Long-term vision
docs/PRINCIPLES.md            — Design principles
docs/ACCEPTABLE_USE.md        — Legal / ethical use
README.md                     — User-facing install + CLI

────────────────────────────────────────────────────────────────────────────────
§25  LINKS
────────────────────────────────────────────────────────────────────────────────

Repo:     https://github.com/zowskyy/apex-android
Releases: https://github.com/zowskyy/apex-android/releases
Actions:  https://github.com/zowskyy/apex-android/actions
PR #4:    https://github.com/zowskyy/apex-android/pull/4

════════════════════════════════════════════════════════════════════════════════
END OF MASTER NOTES — save this file; re-copy after major releases
════════════════════════════════════════════════════════════════════════════════
