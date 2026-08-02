# APEX — Android Package EXaminer

APEX is a security-first, cross-platform mobile app intelligence workstation with
a CLI and a private, local web interface. It inspects Android (APK/AAB) and iOS
(IPA) applications: metadata, binary formats, DEX/Java, Mach-O hardening, trackers
and third-party libraries, embedded secrets, signing, privacy posture, and static
security signals — with a CycloneDX SBOM and SARIF for automation. Everything runs
locally with no telemetry.

## Cross-platform intelligence

- **Tracker & library detection** — offline signature set matches known SDKs in
  Android DEX classes and iOS frameworks/dylibs (`apex trackers app.apk|app.ipa`).
- **Privacy posture** — one grade that correlates declared intent (permissions,
  Apple `PrivacyInfo.xcprivacy`) against observed content (trackers, cleartext),
  flagging declared-vs-actual discrepancies (`apex privacy app.apk|app.ipa`).
- **iOS analysis** — Mach-O hardening (PIE, encryption, stack canary, ARC,
  dylibs), `Info.plist`, and privacy manifest (`apex ios app.ipa`).
- **SBOM** — CycloneDX 1.5 export (`apex sbom app.apk|app.ipa`).
- **Secrets & MASVS** — embedded credential detection (redacted) and security
  findings mapped to CWE and OWASP MASVS, emitted as SARIF.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

The Python package uses [Androguard](https://github.com/androguard/androguard)
for production AXML, ARSC, DEX, and Java decompilation. The included
`apex_zip_reader` Rust extension is used automatically when installed;
otherwise the bounded Python extractor enforces the same path policy.

Optional tools expand rebuild support:

- `apktool`, or `APEX_APKTOOL_JAR=/path/to/apktool.jar`, recompiles edited XML
  and resources.
- `apksigner`, or `APEX_APKSIGNER=/path/to/apksigner`, signs build output.
- `aapt2`, `adb`, and Java are reported by `apex doctor`.

APEX never labels a missing optional capability as successful. The raw backend
is a lossless archive project; readable files under `decoded/` are views, and
edited compiled resources require the apktool backend.

## Use

```bash
apex inspect app.apk
apex analyze app.apk --out report
apex decompile app.apk --out source
apex decode app.apk --out project
apex build project --out rebuilt.apk
apex verify rebuilt.apk
apex roundtrip app.apk --work roundtrip
apex security-scan app.apk --format sarif
apex diff old.apk new.apk
apex framework-check app.apk
apex doctor
apex trackers app.apk
apex privacy app.apk
apex sbom app.apk --out app.cdx.json
apex ios app.ipa
apex device list
apex device sync --serial SERIAL
apex bundle inspect app.aab
apex icon app.apk -o icon.png
apex export app.apk --out export/
```

To open the local interface:

```bash
apex gui
```

The server binds to `127.0.0.1:8765` by default. Uploaded APKs and generated
source remain in the configured local workspace.

## Decode and build backends

### Raw backend

`apex decode --backend raw` creates:

```text
project/
├── apex-project.json
├── raw/                 # authoritative, buildable package files
└── decoded/             # readable manifest/resource XML views
```

Edit `raw/` entries such as DEX, assets, and native libraries, then run
`apex build`. Entry payloads are preserved, unsafe paths are refused, and
original compression methods are retained.

### Apktool backend

`apex decode --backend apktool` produces a conventional decoded-resource and
smali project. `apex build` routes that project back through apktool. This
backend is required when source XML or resource definitions are modified.

## Security model

- ZIP names are normalized and checked for traversal, absolute paths, NUL
  bytes, and excessive length.
- Entry count, individual expansion, and cumulative expansion are bounded.
- ARSC string pools are scanned with allocation and chunk bounds.
- Security output distinguishes evidence from conclusions; static findings
  are not presented as a malware verdict.
- The web interface is loopback-only by default and does not execute APK code.
- Core analysis is local-first and telemetry-free. Future connected-device
  workflows will favor user-owned-device ADB/pairing flows over broad
  installed-app visibility.

## Competitive strategy

APEX is not trying to become a phone-only metadata browser clone. The audited
product strategy (second-pass confirmed against Apktool 3.x, jadx/OWASP MASTG
guidance, Play package-visibility policy, SDK `apkanalyzer`, and wrapper-style
peers such as APKLab) is a local analysis workstation that:

- matches consumer report completeness
- prefers jadx for Java quality, apktool 3.x for compiled-resource rebuild,
  apksigner for signing truth, and bundletool for AAB
- keeps Androguard as the metadata/DEX backbone and fallback
- uses ADB for user-owned device sync rather than casual full inventory scanning

Execution documents:

- `docs/PRINCIPLES.md` — what APEX ships and why nothing essential is withheld
- `docs/COMPETITIVE_STRATEGY.md` — product position and benchmark targets
- `docs/IMPLEMENTATION_GUIDE.md` — architecture, contracts and test gates
- `docs/ROADMAP.md` — delivery status and engineering detail

## Product principle

**Everything essential ships in the core product.**

APEX does not withhold capability to create the appearance of future
improvement, and does not push setup work onto the user. Certificate
fingerprints, DEX and Java analysis, rebuild, verification, diffing, security
scanning, device sync, and reporting all work without installing any external
Android tool.

Optional tools (`jadx`, `apktool`, `apksigner`, `apkanalyzer`, `bundletool`)
serve two roles only: better output quality where they genuinely excel, and
independent cross-checks of APEX's own results. Every report records which
engine produced which output. When you want those tools, APEX installs them
for you:

```bash
apex tools list
apex tools install jadx
```

See `docs/PRINCIPLES.md` and the global agent skill
`.cursor/skills/finished-product-delivery/SKILL.md` (`finished-product-delivery`).
It governs how APEX is built and released: complete suite, full wiring, and
description-faithful marketplace readiness in one standard.

## Development

```bash
pytest -q
cargo test --workspace
```

The genuine DEX fixture under `core/dex_parser/tests/fixtures/` exercises class,
method, instruction, CFG, Java-decompilation, and cross-reference paths.
`scripts/generate_test_apk.py --clean` produces large and malicious APK-shaped
fixtures for extraction and traversal regression tests.

## License

APEX is MIT licensed. Third-party parsers and tools retain their own licenses;
Androguard is used under Apache License 2.0.
