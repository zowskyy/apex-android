# KNOWLEDGE_BASE.md — APEX

## Binary Formats (Must-Read Before Parser Slices)

| Format | Spec Source | Notes |
|---|---|---|
| resources.arsc | [AOSP ResourceTypes.h](https://android.googlesource.com/platform/frameworks/base/+/master/libs/androidfw/include/androidfw/ResourceTypes.h) | Chunk-based binary format; our diagnostics tool already parses the string pool layer |
| DEX | [Android DEX format spec](https://source.android.com/docs/core/runtime/dex-format) | Header, string/type/proto/field/method ID pools, class data, bytecode |
| Binary XML | Same ResourceTypes.h | Compiled XML uses string pool + attribute IDs referencing resources.arsc |
| APK (ZIP) | [PKWARE ZIP spec](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT) | Central directory at end of file; APK signing uses ZIP comment field |

## Existing Tools (Reference Implementations)

| Tool | Source | What to learn from it |
|---|---|---|
| apktool | [github.com/iBotPeaches/Apktool](https://github.com/iBotPeaches/Apktool) | Resource decode/rebuild pipeline, framework management, aapt2 integration |
| jadx | [github.com/skylot/jadx](https://github.com/skylot/jadx) | DEX → Java decompilation, IR design, GUI architecture |
| baksmali/smali | [github.com/google/smali](https://github.com/baksmali/smali) | DEX ↔ smali assembly/disassembly |
| ABXML (Rust) | [github.com/niclas-nicecap/abxml-rs](https://github.com/niclas-nicecap/nicecap/tree/master/nicecap-abxml) | Rust-based binary XML decoder (inspiration for our parser) |
| androguard | [github.com/androguard/androguard](https://github.com/androguard/androguard) | Python APK/DEX analysis library |

## Our Own Prior Work (Directly Portable)

| Asset | Location | What it provides |
|---|---|---|
| apktool_diagnostics.py | [zowskyy/apktool-diagnostics](https://github.com/zowskyy/apktool-diagnostics) | Security scan, round-trip verify, framework check, dex diff, corpus runner |
| CVE-2026-39973 reproduction | Same repo, SECURITY_FINDING_CVE-2026-39973.md | Path-traversal attack methodology and defense validation |
| Binary arsc parsing code | apktool_diagnostics.py security-scan | String pool walker with bounded allocation (OOM fix baked in) |
| Jazzer fuzzing harness | Same repo, LOCAL_SETUP.md | JVM fuzzing setup targeting ResFileDecoder path construction |
| Real test APKs | F-Droid client v1023051 + NewPipe v0.28.8 | One PASS case, one framework-FAIL case |

## Rust Ecosystem (For Parser Slices)

| Crate | Purpose |
|---|---|
| PyO3 | Rust ↔ Python bridge (expose Rust parsers to Python CLI) |
| nom or winnow | Parser combinators for binary format parsing |
| rayon | Data parallelism (parallel per-class decompilation) |
| zip (crate) | ZIP file reading with security controls |
| clap | CLI argument parsing (if we add a Rust CLI layer) |

## Security Requirements (Non-Negotiable)

From our CVE-2026-39973 work:
- ALL string pool reads must sanitize for path traversal before use as file paths
- ALL zip entry names must be checked for `../` and absolute paths before extraction
- Bounded allocation on ALL pool sizes (our OOM fix pattern: check stringCount against chunk size before allocating)
- Framework version mismatch must produce a clear diagnostic, not a raw stack trace

## Performance Baselines (Measure Before Claiming 10x)

Must benchmark against BOTH tools on the same hardware, same APKs:
- apktool 2.9.3 / 3.0.2: decode + rebuild time, peak memory
- jadx 1.5.6: decompile time, peak memory, indexing time
- Our tool: same metrics on same APKs
- Use `hyperfine` for CLI benchmarks, `/usr/bin/time -v` for peak RSS
