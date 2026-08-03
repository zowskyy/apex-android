# APEX — Android Package EXaminer

APEX is a security-first Android reverse-engineering application with a CLI
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
for production AXML, ARSC, and Java decompilation. The included
`apex_zip_reader` and `apex_dex_reader` Rust extensions are used automatically
when installed; otherwise bounded Python/Androguard fallbacks apply.

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
```

To open the local interface:

```bash
apex gui
```

### Use on your phone (same Wi-Fi)

APEX runs on your computer; your phone uses it through the browser:

```bash
apex mobile
```

Open the printed URL (e.g. `http://192.168.1.42:8765`) on your phone, tap
**Choose APK**, and pick any APK from your device. Analysis stays on your PC.

The server binds to `127.0.0.1:8765` by default for local-only use. Uploaded
APKs and generated source remain in the configured local workspace.

### App wrappers (all platforms)

| System | Launcher |
|--------|----------|
| Windows | `wrappers\windows\apex-gui.bat` · `apex-mobile.bat` |
| macOS | `wrappers/macos/apex-gui.command` · build `.app` with `create-apps.sh` |
| Linux | `wrappers/linux/apex-gui.sh` · desktop entries via `install.sh` |
| Android | WebView client APK: `wrappers/android/build.sh` |
| iOS | Safari + Add to Home Screen ([wrappers/ios/README.md](wrappers/ios/README.md)) |
| Docker | `wrappers/docker/run.sh` |

```bash
apex wrapper list      # paths for your OS
apex wrapper install   # venv + desktop shortcuts / .app bundles
```

Full matrix: [wrappers/README.md](wrappers/README.md)

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

APEX Community edition is MIT licensed. Third-party parsers and tools retain
their own licenses; see `NOTICE`. Androguard is used under Apache License 2.0.

## Editions

| Capability | Community | Pro |
|------------|-----------|-----|
| CLI inspect / analyze / decompile / decode / build | Yes | Yes |
| Local web UI (`apex gui`) | Yes | Yes |
| Security scan & roundtrip verification | Yes | Yes |
| MCP server for AI assistants | — | Yes |
| Code Pilot (in-app prompt agent) | — | Yes |
| PostgreSQL report storage | — | Yes |
| Batch automation workflows | — | Yes |

Activate Pro with a license key:

```bash
export APEX_LICENSE_KEY="$(apex mcp show-key | python -c 'import sys,json; print(json.load(sys.stdin)["license_key"])')"
export APEX_ENTITLEMENT=demo
apex doctor
```

Or write `~/.apex/license.json`:

```json
{
  "edition": "pro",
  "entitlement": "demo",
  "key": "APEX-PRO-..."
}
```

Run `apex mcp show-key` to print the evaluation key. Production keys are derived
from your customer entitlement ID via `apex.edition.generate_license_key()`.

## MCP integration (Pro)

APEX exposes reverse-engineering tools to Cursor, Claude Desktop, and other
MCP hosts:

```bash
pip install "apex-android[mcp]"
apex mcp
```

Add to your MCP client config (see `mcp-config.example.json`):

```json
{
  "mcpServers": {
    "apex": {
      "command": "apex",
      "args": ["mcp"],
      "env": {
        "APEX_LICENSE_KEY": "APEX-PRO-...",
        "APEX_ENTITLEMENT": "demo"
      }
    }
  }
}
```

Available tools: `apex_doctor`, `apex_inspect`, `apex_security_scan`,
`apex_analyze`, `apex_decompile`, `apex_decode`, `apex_verify`, `apex_diff`,
`apex_roundtrip`, `apex_framework_check`.

## Code Pilot (Pro)

In-app agent that turns natural-language prompts into APEX tool calls:

```bash
export APEX_LICENSE_KEY="$(apex mcp show-key | python -c 'import sys,json; print(json.load(sys.stdin)["license_key"])')"
export APEX_ENTITLEMENT=demo

# Offline planner (no API key) — good for demos / CI
apex agent "security-scan this package" --apk app.apk --provider heuristic

# Production / App Store builds: set APEX_AGENT_PROVIDER=openai and inject API key
export APEX_AGENT_API_KEY=sk-...
apex agent "triage this APK and summarize risks" --apk app.apk --playbook triage
```

Also available in the web UI **Code Pilot** panel after opening an APK
(`apex gui`). AI cost can be bundled into the paid app price; users do not need
a separate Copilot subscription to use APEX Code Pilot when the app supplies the key.

