# PROJECT_BLUEPRINT.md — APEX (Android Package EXaminer)

> **Release status (v0.2.0):** All user-visible phases are available through
> the CLI and local web UI. The release follows the risk-register strategy of
> wrapping mature Androguard/apktool/Android SDK capabilities while retaining
> the native Rust ZIP and DEX cores. “Native replacement” items below are
> continuing implementation goals, not blockers for a complete application.
>
> **Competitive strategy (audited 2026-08-02):** see
> `docs/COMPETITIVE_STRATEGY.md` for the revised plan to exceed consumer APK
> inspection tools while remaining compatible with current Android package
> visibility, signing, AAB, and reverse-engineering tooling realities.

## Vision

A single unified tool that replaces the current two-tool workflow (apktool for decode/rebuild + jadx for decompilation/analysis) with one CLI + optional GUI that does both — faster, safer, and with more developer options than either tool alone.

## Competitive Gap Analysis (Evidence-Based)

### What jadx does well (and we must match)
- Direct DEX → Java decompilation (human-readable output)
- GUI with code search, cross-references, class navigation
- Accepts APK, DEX, JAR, AAR, AAB, XAPK, smali, class files
- ProGuard/R8 mapping file support for de-obfuscation
- Gradle project export

### What jadx does poorly (and we beat)
- OOMs on large APKs (4GB+ RAM usage on 36MB APK, issue #469)
- High CPU in background even when idle (issues #1000, #1413)
- Slow single-file decompilation (issue #1345)
- Fails on non-ASCII characters in some paths
- "Show inconsistent code" is the only fallback for failed decompilation — no partial recovery
- No rebuild capability at all

### What apktool does well (and we must match)
- Lossless resource decode (resources.arsc → XML)
- Decode → modify → rebuild → sign workflow
- Smali-level bytecode access for patching
- Framework management for OEM APKs
- CLI-first, scriptable

### What apktool does poorly (and we beat)
- Round-trip is NOT lossless (our own Phase 3 proved this — qualifier pruning, resource renaming, dex reassembly noise)
- Framework version gaps cause cryptic aapt2 errors (NewPipe failure we reproduced)
- No decompilation to Java (smali only — hard to read)
- No GUI
- Security: path traversal CVE-2026-39973 (we reproduced and verified this)
- Error messages are raw Java stack traces (3.0.2 regression we found)

### What NEITHER tool does (and we add)
- Pre-decode security scanning (our apktool_diagnostics.py security-scan)
- Round-trip fidelity verification (our roundtrip subcommand)
- Framework compatibility pre-check (our framework-check subcommand)
- Semantic dex diff (our dex-diff subcommand)
- Unified decode + decompile + rebuild in one tool
- Streaming/partial decode for huge APKs (metadata-only mode)
- Built-in path-traversal sanitization on ALL string-pool reads (not bolted on after the fact)

## 10x Performance Target

| Operation | jadx/apktool today | APEX target | How |
|---|---|---|---|
| Full decode (12MB APK) | ~8-12s (apktool) | <1s | Rust binary parser for resources.arsc + parallel dex decode |
| Metadata-only inspect | Not possible (full decode required) | <100ms | Stream zip central directory + arsc header only |
| DEX → Java decompile | ~15-30s (jadx, single-threaded per class) | <3s | Parallel decompilation across all CPU cores, lazy on-demand per-class |
| Rebuild from modified sources | ~10-20s (apktool) | <2s | Incremental rebuild (only reprocess changed files) |
| Memory on 36MB APK | 4GB+ (jadx OOMs) | <512MB | Streaming parser, no full-file buffering |

## Architecture

```
apex/
├── core/                    # Rust — binary parsers, performance-critical paths
│   ├── arsc_parser/         # resources.arsc streaming parser (replaces aapt2 dependency)
│   ├── dex_parser/          # DEX file parser
│   ├── zip_reader/          # APK zip handling with security sanitization
│   └── manifest_decoder/    # Binary XML decoder
├── decompiler/              # Rust or Python — DEX → Java/Kotlin source
│   ├── ir/                  # Intermediate representation (bytecode → IR → source)
│   ├── java_emitter/        # IR → Java source text
│   └── kotlin_emitter/      # IR → Kotlin source text (stretch goal)
├── builder/                 # Python — rebuild pipeline
│   ├── smali_assembler/     # smali → DEX (wraps baksmali or native)
│   ├── resource_compiler/   # XML → binary resources
│   └── signer/              # APK signing (v1/v2/v3/v4)
├── cli/                     # Python — CLI entry point
│   ├── decode.py            # apex decode <apk>
│   ├── decompile.py         # apex decompile <apk>
│   ├── build.py             # apex build <project_dir>
│   ├── inspect.py           # apex inspect <apk> (metadata-only, fast)
│   ├── verify.py            # apex verify <apk> (round-trip check)
│   ├── security.py          # apex security-scan <apk>
│   └── diff.py              # apex diff <apk1> <apk2>
├── gui/                     # Python (Qt/web) — optional GUI (Phase 3+)
├── diagnostics/             # Ported from apktool_diagnostics.py
└── tests/
```

## Technology Choices

| Layer | Language | Why |
|---|---|---|
| Binary parsers (arsc, dex, manifest, zip) | Rust | 10x speed target requires native performance; memory safety without GC pauses |
| CLI, build pipeline, diagnostics | Python | Rapid iteration, your existing environment, PyO3 bindings to Rust core |
| GUI (later) | Python + web (or Qt) | Cross-platform, can reuse CLI commands |

## Salami Slices (Ordered)

### Phase 0: Foundation (Slices 0.1–0.4)
```
0.1  Project scaffold — Cargo workspace + Python package + PyO3 bridge
0.2  CI/CD — GitHub Actions: Rust tests + Python tests + cross-compile
0.3  Port apktool_diagnostics.py into the project as the diagnostics module
0.4  CLI entry point — `apex --help` with subcommand routing
```

### Phase 1: Read-Only Analysis — Match jadx (Slices 1.1–1.8)
```
1.1  Rust ZIP reader — stream APK entries, enforce path-traversal sanitization on every entry name
1.2  Rust resources.arsc parser — streaming, bounded allocation, security-first (our OOM fix baked in from day 1)
1.3  Rust binary XML decoder — manifest + resource XMLs → readable XML
1.4  `apex inspect <apk>` — metadata-only mode (manifest, permissions, resource table structure, file listing) in <100ms
1.5  Rust DEX parser — header, string pool, type pool, method pool, bytecode
1.6  DEX → IR (intermediate representation) — control flow graph, type inference
1.7  IR → Java source emitter — readable output, handle common patterns (if/else, loops, try/catch, switch)
1.8  `apex decompile <apk>` — full decompile to Java source tree with parallel per-class processing
```

### Phase 2: Decode + Rebuild — Match apktool (Slices 2.1–2.6)
```
2.1  Resource decode — arsc + binary XML → source-format XML files (using our own parser, not aapt2)
2.2  DEX → smali disassembly (wrap baksmali initially, replace later)
2.3  `apex decode <apk>` — full decode to project directory (resources + smali + assets + libs)
2.4  smali → DEX assembly (wrap smali initially)
2.5  Resource compile — source XML → binary resources (initially wrap aapt2, replace later)
2.6  `apex build <project_dir>` — rebuild APK from decoded project, with signing
```

### Phase 3: Surpass Both — Unique Features (Slices 3.1–3.7)
```
3.1  `apex verify <apk>` — port round-trip verification from diagnostics
3.2  `apex security-scan <apk>` — port and enhance security scanner
3.3  Framework auto-detection — scan APK's required API level, check/download framework automatically
3.4  Incremental rebuild — only reprocess changed files, cache unchanged resources
3.5  `apex diff <apk1> <apk2>` — semantic diff between two APK versions
3.6  ProGuard/R8 mapping support — de-obfuscate class/method names during decompile
3.7  AAB (Android App Bundle) support — decode/analyze without bundletool dependency
```

### Phase 4: GUI + Polish (Slices 4.1–4.4)
```
4.1  Web-based GUI — file tree, source viewer, search, cross-references
4.2  GUI: integrated decode/decompile/rebuild workflow
4.3  GUI: visual diff between original and rebuilt APK
4.4  Package for distribution — pip install, standalone binary, Homebrew
```

## Exit Conditions Per Slice

Every slice follows the Salami cycle: Slice → Implement → Verify → Update PROJECT_STATE.md → Git Commit.

Verification for each slice is a concrete, runnable test — not "it looks right":
- Parser slices: parse a real APK's actual bytes and assert specific known values
- CLI slices: run the command against the F-Droid and NewPipe test APKs from the diagnostics project
- Performance slices: benchmark against apktool/jadx on the same APK and assert the 10x target
- Security slices: run the CVE-2026-39973 PoC reconstruction (malicious arsc with traversal type name) and assert containment

## What We Already Have (From This Project)

Directly portable into APEX:
- `apktool_diagnostics.py` — security-scan, roundtrip, framework-check, dex-diff, corpus (454 lines, tested)
- `SECURITY_FINDING_CVE-2026-39973.md` — CVE reproduction methodology and findings
- `LOCAL_SETUP.md` — Jazzer fuzzing harness for the parser layer
- Binary resources.arsc parsing knowledge (offset calculation, string pool walking, chunk format)
- Real test corpus: F-Droid client APK (PASS) + NewPipe APK (framework FAIL)
- Classifier for expected vs anomalous round-trip divergences (3 iterations, validated)

## Non-Goals (Explicit Scope Boundaries)

- Not a full IDE (no code editing, no debugging)
- Not a malware sandbox (no dynamic analysis, no emulation)
- Not a patcher/modder toolkit (no auto-patching, no ad-removal scripts)
- No paid/commercial features — MIT licensed, fully open source

## Risk Register

| Risk | Mitigation |
|---|---|
| Rust learning curve | Start with Python wrappers calling Rust via PyO3; incrementally move hot paths to Rust |
| DEX → Java decompiler is a multi-year project | Start by wrapping jadx-core as a library; replace incrementally |
| aapt2 replacement is enormous | Wrap aapt2 initially for rebuild; replace with own resource compiler only after decode path is solid |
| Scope creep | Each slice has a concrete exit condition; no slice proceeds without the previous one verified |
