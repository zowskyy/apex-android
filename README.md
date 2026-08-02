# APEX — Android Package EXaminer

APEX v1.0 is a security-first Android reverse-engineering workstation with a CLI
and a private, local web interface. It inspects APK metadata, decodes binary
Android formats, decompiles DEX bytecode, builds editable projects, verifies
round trips, compares packages, and reports static security signals.

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
apex security-scan app.apk
apex diff old.apk new.apk
apex framework-check app.apk
apex doctor
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

See `docs/PRINCIPLES.md` and the global agent skills in `.cursor/skills/`
(`complete-suite-delivery`, `end-to-end-wiring`, `marketplace-ready-release`).
These govern how APEX is built and released: the full suite ships now, every
layer is wired before merge, and public descriptions must match reality.

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
