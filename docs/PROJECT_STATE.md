# PROJECT_STATE.md — APEX

## Current Phase: Phase 1 — Read-Only Analysis (in progress)

## Completed Slices
- 0.3 — Core engine + 10-test suite, all passing on Windows (commit 9703652)
- 1.1 — Rust ZIP reader (`core/zip_reader`, PyO3 module `apex_zip_reader`):
  path-traversal + absolute-path + NUL-byte + oversized-name sanitization,
  bounded allocation (entry count cap, per-entry and cumulative uncompressed
  size caps with a true-decompressed-size re-check to catch lying headers),
  CLEAN/WARN verdict per entry. Replaces `zipfile.extractall()` in
  `apex/__init__.py:extract_apk()` (native path, with a pure-Python fallback
  mirroring the same checks if the extension isn't installed).
- Tooling: `tools/mobile_test_app/` builds a real, installable, debug-signed
  Android APK via the actual SDK toolchain (aapt2/javac/d8/zipalign/apksigner
  — all present locally under `%LOCALAPPDATA%\Android\Sdk` and Android
  Studio's bundled JBR). Verified with `apksigner verify` (v2/v3 signature
  valid) and `aapt2 dump badging` (manifest parses correctly), and round-tripped
  through `apex.extract_apk()` (7/7 entries CLEAN). Use this — not
  `sample_test.apk` — for anything needing genuine binary XML / arsc / dex,
  or for installing on a real device/emulator to debug. See
  `tools/mobile_test_app/README.md`.

- 1.5 (structural parsing + real instruction decoding; IR/CFG still open) —
  `core/dex_parser` (rlib `apex_dex_parser`, not yet PyO3-bridged): DEX
  header (all 23 fields, correct offsets), string pool (MUTF-8 decode),
  type_ids, class_defs (all 8 fields), class_data_item (ULEB128,
  delta-encoded field/method indices), code_item parsing, and a real
  per-format Dalvik instruction decoder (`opcode.rs` + `code.rs`): all ~28
  instruction formats (10x through 51l) with correct bit layouts, the full
  opcode→format table (0x00-0xff, including the quickened/ODEX-only tail
  and invoke-polymorphic/invoke-custom/const-method-handle at the high end),
  and the 3 inline switch/array-data payload pseudo-instructions
  (packed-switch, sparse-switch, fill-array-data), which are NOT part of
  the normal opcode space and must be detected via their nop-family marker
  bytes or every instruction after one desyncs.
  Verified against 6 integration tests reading a real `classes.dex`
  compiled by the actual Android `d8` tool (`core/dex_parser/tests/`,
  provenance in `tests/fixtures/README.md`): resolves all 7 real classes,
  walks class_data → method_idx → method_ids → string pool to find methods
  by name, and — the strongest check — for every real method with code,
  decoded instruction widths sum exactly to the method's declared
  `insns_size` (this is the property that would break immediately if any
  opcode's format/width were wrong). `onCreate` decodes to exactly its real
  source shape: `invoke-super` → `const/high16` (asserted to carry a
  `0x7f` AAPT app-resource-ID prefix in its top 32 bits) → `invoke-virtual`
  → `return-void`, matching `super.onCreate(...); setContentView(R.layout...)`.
  **Provenance**: this is a from-scratch rewrite, architecturally modeled
  on a separate personal project (`dex-hybrid`, not third-party — no
  license/attribution concern), after a review found 3 concrete format
  bugs in that project's parser (verified against
  source.android.com/docs/core/runtime/dex-format): header read only 4 of
  23 fields and mislabeled byte 0x2C as map_off (real map_off is 0x34);
  class_def_item was missing `static_values_off` (7 of 8 real fields),
  which would misalign every class after the first; class_data_item was
  read as fixed-width u32 fields instead of ULEB128 with delta-encoded
  indices. All three fixed here, plus the instruction decoder (below) was
  built from scratch rather than salvaging that project's disassembler,
  which only covered ~2 of ~30 real Dalvik instruction formats. Also NOT
  ported: that project's "SSA" builder (predecessor tracking was never
  wired up, so phi-node insertion was dead code) and its optimizer/AST/
  pretty-printer (every stage was a stub that discarded its input) — those
  remain scaffolding for the real Slice 1.6–1.7 work still ahead (CFG/SSA
  construction from the now-real instruction stream, IR → Java emitter).
  **Known gap in the opcode table**: the 0xe3-0xf9 quickened/ODEX-only
  range (iget-quick/invoke-virtual-quick/etc.) has width-correct but
  semantically-approximate format assignments — those opcodes never appear
  in build-time/APK-shipped DEX (only in on-device ART-optimized ODEX), so
  this hasn't mattered yet and isn't tested against real bytecode; treat it
  as unverified if `core/dex_parser` is ever pointed at a non-APK DEX source.

## Next Slice
1.6 — CFG/basic-block construction and real SSA form from the instruction
stream `core/dex_parser::code` now produces (branch_offset/index are
already resolved per-instruction, so this is graph-building, not more
format parsing). Then 1.2 (resources.arsc) and 1.3 (binary XML) remain
open in parallel — order between them is free, 1.5 was pulled forward
opportunistically because of the dex-hybrid review.

## Blockers
- None.

## Known Gaps / Follow-ups
- **Slice 0.1 (Cargo workspace scaffold) was never done as its own slice** —
  the workspace was created as part of 1.1 instead. No functional gap, just
  noting the renumbering for the record.
- **Slice 1.1 performance finding (do not treat 10x as proven yet):**
  measured against `tests/fixtures/sample_test.apk` (generated by
  `scripts/generate_test_apk.py`: 9.3MB, 1080 entries, real APK directory
  layout — manifest, dex, arsc, res/, lib/*.so, META-INF — but not the actual
  F-Droid/NewPipe corpus, which isn't present in this checkout):
  - `extract_apk` (native) vs `zipfile.extractall`: ~parity (0.9x — disk I/O
    dominates, not parser speed, at this entry count).
  - `read_entries` (native, metadata-only) vs `zipfile.infolist()`: **native
    is ~2.4x SLOWER** (0.41x). Reproduced at two different scales (2000
    synthetic entries: 0.34x; 1080 realistic entries: 0.41x), so this is a
    real, consistent finding, not noise. Cause: each entry round-trips
    through a fresh PyDict built with 8 individual `set_item` FFI calls.
    Matters for Slice 1.4 (`apex inspect`, <100ms target) as entry counts
    grow — still under 100ms at ~1000 entries (~34ms), so not yet a blocker.
    Fix candidate for later: batch/columnar return (one dict of parallel
    lists) instead of N per-entry dicts — not implemented yet, flagged
    instead of prematurely optimized without real-corpus entry counts.
  - Malicious-variant end-to-end check (`sample_test_malicious.apk`, also
    generated by the same script): 7 entries, 4 extracted clean, 3 correctly
    WARNed (two `../` traversal variants + one absolute path), none escaped
    the extraction root.

## Test Corpus
- F-Droid client v1023051 (12.4MB) — round-trip PASS baseline
- NewPipe v0.28.8 (10.9MB) — framework-version FAIL baseline
- **Neither real APK file is present in this repo checkout.** In its place,
  `scripts/generate_test_apk.py` builds a deterministic, locally-generated
  APK-shaped fixture (`tests/fixtures/sample_test.apk`, gitignored, built
  on demand by the pytest suite) at comparable scale to the F-Droid
  baseline. It is a reasonable stand-in for structure/entry-count-shaped
  testing but is not a substitute for the real corpus for round-trip or
  framework-compatibility slices (2.x) — those need the actual APKs.

## Pending Decision: Kotlin / R8-obfuscation support
Not yet integrated, but scoped: `android-reverse-engineering-skill`
(github.com/SimoneAvogadro/android-reverse-engineering-skill, Apache-2.0)
is confirmed as a legally-reusable reference/stopgap for exactly the
Kotlin-metadata-recovery + Ktor/Apollo/Koin API-extraction capability
discussed for APEX. Its `recover-kotlin-names.sh` technique (mine
`@DebugMetadata`/`@Metadata` d2 strings that R8 can't strip) is sound and
directly portable. Plan: wrap it as an interim jadx-based stopgap (per the
Risk Register's own "wrap jadx-core initially, replace incrementally"),
then move the technique into `core/dex_parser`'s own annotation-parsing
once that exists (annotations_off is already captured per class_def, just
not parsed yet). If reused, must keep its LICENSE/attribution per
Apache-2.0 terms — not yet done since nothing's been copied in yet.

## Key Decisions
- Tool name: APEX (Android Package EXaminer)
- License: MIT
- Core parsers: Rust (via PyO3)
- CLI + build pipeline: Python
- GUI: deferred to Phase 4
- DEX decompiler: wrap jadx-core initially, replace incrementally
- Resource compiler: wrap aapt2 initially, replace incrementally
