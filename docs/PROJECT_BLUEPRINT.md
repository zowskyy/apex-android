# PROJECT_BLUEPRINT.md — APEX (Android Package EXaminer)

> **Release status (v0.2.0):** All user-visible phases are available through
> the CLI and local web UI. The release follows the risk-register strategy of
> wrapping mature Androguard/apktool/Android SDK capabilities while retaining
> the native Rust ZIP and DEX cores. “Native replacement” items below are
> continuing implementation goals, not blockers for a complete application.
>
> **Competitive strategy (audited 2026-08-02, second pass same day):** see
> `docs/COMPETITIVE_STRATEGY.md`. Near-term APEX **orchestrates** jadx /
> apktool 3.x / apksigner / bundletool / apkanalyzer with provenance; native
> parsers remain for proven hot paths (ZIP security today, more later).
> “Replace jadx/apktool entirely” is long-horizon research, not the beat plan.
>
> **Execution:** `docs/IMPLEMENTATION_GUIDE.md` is the current architecture
> contract and `docs/ROADMAP.md` is the authoritative slice order. Historical
> slice descriptions below remain useful for native research context.

## Vision

A single local workstation that unifies the current multi-tool Android RE
workflow (apktool for decode/rebuild, jadx for decompilation, SDK tools for
signing/AAB/oracle checks) behind one CLI + optional GUI — faster, safer,
more automatable, and more private than juggling those tools by hand — while
still using the best engine for each job.

## Competitive Gap Analysis (Evidence-Based)

### What jadx does well (and we must match)
- Direct DEX → Java decompilation (human-readable output)
- GUI with code search, cross-references, class navigation
- Accepts APK, DEX, JAR, AAR, AAB, XAPK, smali, class files
- ProGuard/R8 mapping file support for de-obfuscation
- Gradle project export

### What jadx does poorly (and we beat *as a product*)
- OOMs on large APKs (4GB+ RAM usage on 36MB APK, issue #469) — mitigate with lazy/on-demand class decompile and process isolation
- High CPU in background even when idle (issues #1000, #1413) — CLI subprocess model avoids idle GUI cost
- Slow single-file decompilation (issue #1345) — prefer `--single-class` on-demand paths in UI
- Fails on non-ASCII characters in some paths — sanitize workspace paths in APEX
- Limited rebuild capability — APEX owns rebuild orchestration via apktool/raw backends
- Not a full analysis workstation — APEX adds inspect, security, device sync, diff, verify

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

These remain stretch research goals for native hot paths. Competitive beat
criteria for v0.3+ are defined in `docs/COMPETITIVE_STRATEGY.md` (report
parity, jadx-quality decompile, automation/JSON, device sync, privacy) and
must not be confused with unproven 10x claims.

| Operation | jadx/apktool today | APEX stretch target | Near-term approach |
|---|---|---|---|
| Full decode (12MB APK) | ~8-12s (apktool) | <1s | Wrap apktool; accelerate inspect via native ZIP/metadata |
| Metadata-only inspect | Not possible (full decode required) | <100ms | Stream zip central directory + selective parsers |
| DEX → Java decompile | ~15-30s (jadx full tree) | Fast interactive class view | jadx `--single-class` + Androguard fallback |
| Rebuild from modified sources | ~10-20s (apktool) | Faster incremental later | apktool 3.x wrapper now |
| Memory on large APKs | jadx GUI can be heavy | Bounded worker processes | Subprocess isolation, lazy decompile |

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
3.7  AAB (Android App Bundle) support — wrap `bundletool` first for `.aab` → `.apks` / device targeting; native AAB only if a proven gap remains
```

### Phase 3b / Competitive hardening (see COMPETITIVE_STRATEGY.md)
```
C.1  Provider abstraction + provenance for jadx/apktool/apksigner/apkanalyzer/bundletool/androguard/rust
C.2  apex device list/pull/sync — ADB local corpus
C.3  Permission catalog + granted-state enrichment
C.4  Signing UX via apksigner oracle
C.5  Web UI Devices tab + corpus stats
```

### Phase 5: Analysis-depth slices (AND-01 – AND-04)

These four slices target defects that separate a metadata viewer from a real
reverse-engineering workstation. They were scoped against Ghidra's Android
workflow; the root causes were then **re-verified against the APEX codebase**,
and the fixes are stated in APEX terms. Where the original Ghidra framing does
not apply (Ghidra has an address space, a Listing view, and its own decompiler;
APEX has none of these), the mapping note records what actually applies here.

Each slice is complete only when every verification step passes.

---

#### SLICE: AND-01 — Unified multidex symbol and cross-reference space

- **Difficulty:** H
- **Scope:** spike + follow-on slices for full merge logic
- **Root cause (verified in APEX):** `analysis.load_dex` constructs a separate
  Androguard `Analysis(dex)` per DEX file and calls `create_xref()` on each in
  isolation. `scan_dex_metadata` then concatenates the per-DEX results. A call
  from `classes2.dex` into `classes.dex` therefore never resolves — the callee
  is absent from that DEX's analysis, so the edge is dropped or left dangling.
  `build_crossrefs` compounds this by synthesizing nodes from unresolved edge
  strings.
- **Ghidra mapping note:** APEX has no address space, so there is nothing to
  allocate. The transferable requirement is the **unified symbol and xref table
  spanning all DEX files**, plus the absence of a per-DEX method ceiling.
- **Implemented fix:** Build a single cross-DEX symbol table keyed by
  fully-qualified `class::method(descriptor)`, resolve every call edge against
  that table (recording the defining DEX per symbol), and expose the owning DEX
  on both endpoints of each edge.
- **Verification steps:**
  1. Import a multidex APK (3+ `classes#.dex`) — every class from every DEX is
     present exactly once in one merged index.
  2. A call from `classes2.dex` into `classes.dex` resolves to a live
     cross-reference with both endpoints marked resolved, not a synthesized stub.
  3. An APK whose combined method count exceeds 65,536 analyzes with no
     per-DEX ceiling error and no dropped edges.
  4. Cross-DEX edge count is reported and is greater than zero on the fixture.
- **Commit:** `git commit -m "Slice AND-01: unified multidex symbol and xref space"`
- **Status:** DONE — `apex/dex/unified.py`; edges carry `resolved`/`caller_dex`/`callee_dex`/`cross_dex`

---

#### SLICE: AND-02 — Deterministic content-based format detection

- **Difficulty:** M
- **Root cause (verified in APEX):** Format dispatch is purely filename-based.
  `ios/ipa.py:is_ipa` uses `splitext`, `cli.py` and `web.py` branch on
  `suffix.lower() == ".ipa"`, and `inspect_apk` derives `format` from the
  suffix. A renamed or extensionless file is routed to the wrong engine; an IPA
  named `.apk` is parsed as an Android package and silently produces an empty
  Android report rather than an error.
- **Implemented fix:** A single `detect_format()` that inspects content —
  ZIP central directory plus member layout (`AndroidManifest.xml`/`classes*.dex`
  vs `Payload/*.app/`), DEX magic (`dex\n035\0` and later variants), Mach-O and
  fat magic, ELF magic, and AAB/APKS shapes — before any extension heuristic.
  Every entry point (CLI, web, services) routes through it. Extension is a
  tiebreaker only, never the decision.
- **Verification steps:**
  1. A corpus of APK/AAB/APKS/IPA/DEX/`.so` fixtures, each also copied with a
     wrong extension and with no extension, is detected correctly in 100% of
     cases with zero manual overrides.
  2. An IPA renamed to `.apk` produces an iOS report, not an empty Android one.
  3. An unsupported or corrupt file returns one actionable `ApexError` naming
     the detected type — never a partial report.
  4. Detection reads a bounded prefix and does not extract the archive.
- **Commit:** `git commit -m "Slice AND-02: deterministic content-based format detection"`
- **Status:** DONE — `apex/format_detect.py`; `apex detect` command; all entry points routed

---

#### SLICE: AND-03 — Exception-handler blocks as first-class CFG nodes

- **Difficulty:** H
- **Root cause (verified in APEX):** `core/dex_parser/src/code.rs` reads
  `tries_size` from the `code_item` header but never parses the `try_item`
  array or the `encoded_catch_handler_list` that follows the instruction
  stream. `cfg.rs` therefore builds basic blocks from branch targets only, so
  handler entry points are unreachable blocks with no predecessors and
  protected ranges are invisible.
- **Ghidra mapping note:** APEX has no Listing view or Ghidra decompiler to
  synchronize. The transferable requirement is that **handler boundaries are
  first-class CFG/IR nodes rather than synthetic or missing jumps**, which is
  the precondition for any correct try/catch reconstruction later.
- **Implemented fix:** Parse `try_item` (start_addr, insn_count, handler_off)
  and `encoded_catch_handler_list` (ULEB128 size, typed handler pairs, optional
  catch-all), then model each protected range and handler as explicit CFG
  regions with exception edges from every instruction in the protected range to
  each reachable handler entry.
- **Verification steps:**
  1. A synthetic method with 3+ catch blocks plus a catch-all: every handler
     entry is a block with at least one predecessor, and each protected range
     maps to its handlers with correct type descriptors.
  2. Nested and overlapping try ranges produce correct handler sets per range.
  3. Across a 50-method regression corpus with exception handling, zero handler
     blocks remain unreachable and instruction widths still sum exactly to
     `insns_size` for every method.
  4. Methods with `tries_size == 0` are byte-for-byte unchanged from today.
- **Commit:** `git commit -m "Slice AND-03: exception handler blocks in CFG"`
- **Status:** DONE — `code.rs` exception tables, `cfg.rs` exception edges, `core/dex_bridge` PyO3 bridge, `apex exceptions` command

---

#### SLICE: AND-04 — Unified Dalvik + native `.so` cross-reference graph

- **Difficulty:** H
- **Root cause (verified in APEX):** `scan_native_libs` records only path, ABI,
  size, and SHA-256 per `.so`. Nothing parses ELF symbol tables, detects
  `System.loadLibrary` call sites, or correlates `native`-declared methods with
  exported JNI symbols. The Dalvik and native layers share no graph, so a JNI
  boundary crossing is invisible.
- **Implemented fix:** Detect `System.loadLibrary`/`loadLibrary` call sites and
  `native`-modifier methods in DEX; parse `.dynsym`/`.dynstr` exports from each
  bundled ELF; resolve both JNI naming conventions — static
  (`Java_pkg_Class_method`, including the `_1`/`_0002E` mangling rules and the
  `__signature` overload suffix) and dynamic registration evidence via
  `JNI_OnLoad`/`RegisterNatives` — then emit unified edges into the existing
  crossref graph with a `jni` edge kind and the owning library recorded.
- **Verification steps:**
  1. A test APK with a bundled `.so` and `native` method declarations: every
     JNI-declared method resolves to its exported `.so` symbol automatically,
     with no manual step.
  2. Resolution is bidirectional — the graph answers Java call site → native
     symbol and native symbol → declaring Java method.
  3. Mangled names (`_1`, `_3`, overload `__` suffixes) resolve correctly on a
     fixture exercising each rule.
  4. A method that is `native` but has no matching export is reported as
     `unresolved` with a reason (likely `RegisterNatives`), never silently
     dropped and never guessed.
  5. Libraries for non-selected ABIs are excluded from the graph, and stripped
     binaries degrade to an explicit `no-symbols` state.
- **Commit:** `git commit -m "Slice AND-04: unified Dalvik/native JNI xref graph"`
- **Status:** DONE — `apex/native/elf.py` + `apex/jni/`; `apex jni` command

---

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
| DEX → Java decompiler is a multi-year project | Prefer jadx CLI/provider for quality; keep Androguard fallback; native emitter is research only |
| aapt2 / compiled-resource rebuild is enormous | Wrap apktool 3.x (aapt2-only); raw backend for lossless archive edits |
| External tool drift (jadx/apktool/SDK) | Provider abstraction, version pinning, doctor diagnostics, fallbacks |
| Scope creep | Each slice has a concrete exit condition; competitive slices follow COMPETITIVE_STRATEGY.md |
