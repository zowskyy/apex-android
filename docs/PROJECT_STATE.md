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
  remain scaffolding for the real Slice 1.7 work still ahead (IR → Java
  emitter, now that both instructions and CFG are real).
  **Known gap in the opcode table**: the 0xe3-0xf9 quickened/ODEX-only
  range (iget-quick/invoke-virtual-quick/etc.) has width-correct but
  semantically-approximate format assignments — those opcodes never appear
  in build-time/APK-shipped DEX (only in on-device ART-optimized ODEX), so
  this hasn't mattered yet and isn't tested against real bytecode; treat it
  as unverified if `core/dex_parser` is ever pointed at a non-APK DEX source.
- 1.6 (CFG only — SSA/phi construction still open) — `core/dex_parser::cfg`:
  standard 3-rule leader-based basic-block splitting (first instruction,
  branch targets, instruction-after-a-branch) with correctly-computed
  successors AND predecessors — the direct fix for the exact bug found in
  dex-hybrid's `ir.rs`, where `BasicBlock.predecessors` was declared but
  nothing ever pushed to it, so its phi-node insertion loop iterated an
  always-empty list and never ran. Handles the DEX-specific wrinkle that
  packed-switch/sparse-switch's `branch_offset` points to a *payload* data
  block, not a code target — real jump targets live inside the payload's
  `targets` list, each relative to the *switch instruction's* offset, not
  the payload's; resolving that indirection correctly is what makes switch
  statements produce any successor edges at all.
  Verified: 4 unit tests using hand-built synthetic instruction sequences
  (the real fixture's methods are all straight-line, so branches/loops/
  switches can't be exercised against real bytecode) — an if/else diamond
  where the join block ends up with exactly 2 predecessors (the property
  dex-hybrid never achieved), a self-looping block, straight-line code
  producing exactly one block with no edges, and the switch-payload target
  resolution in isolation — plus 1 real-DEX test confirming `onCreate`
  (no branches) produces a single block with no edges. Clippy clean. Whole
  workspace: 20 Rust tests passing.
- 1.6 (complete) — real SSA form + def-use tracking, three new modules:
  - `core/dex_parser::defuse` — per-instruction register def/use extraction.
    One exhaustive match over the opcode byte (mirrors opcode.rs's
    `format_of` layout so it can be audited directly against the Dalvik
    reference table), correctly distinguishing which operand position is
    def vs. use *and* whether it's a single register or the low half of a
    64-bit pair (e.g. `add-long/2addr vA, vB` defines+uses the pair at vA
    and uses the pair at vB; `iput-wide vA, vB, field` uses the pair at vA
    but only the single register vB, since the object ref is never wide).
    Field/array/static accesses report only the vreg operands actually
    read/written — `iput` uses 2 registers but defines none (the def lands
    in a field, not a vreg). The quickened/ODEX-only range (0xe3-0xf9) is
    conservatively use-only, consistent with opcode.rs already flagging
    that range as unverified against real bytecode. 14 unit tests covering
    move/wide, 2addr binops (narrow and wide, including the shift-amount-
    stays-narrow case for shl/shr/ushr-long), iget/iput/aget/aput (wide and
    narrow), invoke, move-result-wide, check-cast, and the quickened
    fallback.
  - `core/dex_parser::dominators` — immediate dominators (Cooper/Harvey/
    Kennedy iterative algorithm) and dominance frontiers (Cytron et al.),
    over a real reverse-postorder DFS from the entry block (block ids are
    assigned in code-offset order, which is *not* the same as RPO once a
    forward branch skips a block, so RPO is computed explicitly rather than
    assumed). Found and fixed one real gap while testing against a
    self-looping entry block: the textbook Cytron algorithm implicitly
    assumes the entry block has an "outside" (caller) predecessor it never
    represents as a graph edge, so when entry's *only* real predecessor is
    itself (a single-block infinite loop, e.g. `while(true) { x++; }`
    compiled with no separate preheader/body blocks), the standard
    predecessors>=2 gate and the idom-walk both independently skip it,
    silently omitting entry from its own dominance frontier even though a
    register redefined every iteration and read at the top genuinely needs
    a phi there. Fixed with a targeted special case (see the code comment
    at the fix site); every other self-loop shape (one with a real,
    non-self predecessor too, e.g. a proper preheader+header) already
    handled this correctly via the general algorithm before the fix. 3 unit
    tests: the if/else diamond's dominance frontier, the self-loop-frontier
    case above, and straight-line triviality.
  - `core/dex_parser::ssa` — minimal-SSA construction: phi placement via
    iterated dominance frontier per register (Cytron et al.), then a
    dominator-tree-order renaming pass (explicit-stack DFS, not recursive,
    so adversarial/deeply-nested CFGs can't blow the stack) that assigns a
    fresh version to every def and resolves every use to its reaching
    definition, recording full def-use chains (`uses_of: SsaValue -> Vec<
    UseSite>`, covering both ordinary-instruction uses and phi-operand
    uses). Version 0 is the convention for "value live on entry" (parameter
    or genuinely-undefined read — this layer doesn't have `ins_size` to
    tell those apart, and doesn't need to for def-use purposes). Blocks
    unreachable from the entry (dead code) are still converted to output
    but renamed in isolation, with no phis and no cross-block merging,
    since there's no dominance relationship to justify one. 5 unit tests:
    the if/else diamond (a join-block phi with 2 distinct operand
    versions, one per branch), straight-line code (must reference the most
    *recent* def, not just some def), an undefined read resolving to
    version 0, a real 2-block loop header merging its preheader and
    back-edge defs via a phi, and the single-block self-loop case that
    exercised the dominators.rs fix above end-to-end (phi's back-edge
    operand must equal the loop body's own def of the carried register,
    confirming the value is genuinely loop-carried, not just structurally
    present). Clippy clean (`-D warnings`). Whole workspace: 42 Rust tests
    passing (20 prior + 14 defuse + 3 dominators + 5 ssa).
- 1.2 (complete) — `core/arsc_parser` (rlib `apex_arsc_parser`, not yet
  PyO3-bridged): resources.arsc structural parser — table header, string
  pools (both UTF-8 and UTF-16 encodings, plus style-span parsing for
  formatted strings like `Hello <b>World</b>!`), package chunk (both the
  legacy and modern/`typeIdOffset` `ResTable_package` header sizes),
  typeSpec + type chunks, and both simple and complex/map entries (the
  latter covers arrays, styles, and plurals). Bounded allocation on every
  count field (string/style/entry/map counts), matching the project's
  non-negotiable rule from KNOWLEDGE_BASE.md.
  **Provenance**: no Android SDK is available in this environment
  (`dl.google.com` is blocked by the outbound proxy), so real APK corpus
  files can't be built here the way `tools/mobile_test_app` was on a prior
  session's Windows machine. `pip install aapt2` (a PyPI package bundling
  just the prebuilt `aapt2` binary, reachable via the allowed proxy) filled
  the gap: `core/arsc_parser/tests/fixtures/resources.arsc` is genuine
  `aapt2 compile`+`link` output, not hand-crafted bytes — the one
  limitation is the fixture's `AndroidManifest.xml` has no `android:`
  attributes (those need a framework jar via `-I`, which isn't available
  either), but that's a manifest-linking constraint, not a resources.arsc
  one; the resource table itself is unaffected and exercises real string
  pools, a real styled string, and a real `<string-array>` complex entry.
  See `core/arsc_parser/tests/fixtures/README.md` for exact regeneration
  steps.
  Every byte offset in the parser was hand-verified against this real file
  with a throwaway Python decoder *before* writing the Rust, the same
  discipline as the DEX slice — this caught one real bug during test
  writing: `TypeChunk::is_default_config()` initially checked the whole raw
  `ResTable_config` byte array for all-zero, but that array's own first 4
  bytes are a self-describing size field (64 for the modern struct) which
  is never zero, so every config — including the real default/no-qualifiers
  one in the fixture — read as non-default. Fixed to skip those 4 bytes.
  **Known gaps, explicitly unverified** (no toolchain path in this sandbox
  could produce the bytes to check against, so these are implemented per
  the AOSP `ResourceTypes.h` spec only, same honesty standard as
  dex_parser's quickened-opcode range):
  - `FLAG_SPARSE` entry tables (`aapt2 link --enable-sparse-encoding`
    requires `--min-sdk-version`, which itself needs framework resolution
    to inject into the manifest — blocked by the same missing-SDK gap).
  - `ResTable_config` qualifier bytes are captured raw but not decoded
    field-by-field (locale/density/screen size/etc.) — only "is this the
    default config" is exposed. Real per-qualifier resolution is a
    separately-scoped follow-up.
  - `FLAG_OFFSET16` (a newer 16-bit-offset dense variant) is explicitly
    rejected with a dedicated error rather than silently misparsed.
  8 tests against the real fixture (global string pool + style span,
  package identity/name pools, simple string entries resolved through the
  global pool, simple non-string entries across 3 different `dataType`s,
  the complex `<string-array>` entry's synthetic item names and ordered
  values, typeSpec/type entry-count consistency) + 2 hand-built string-pool
  unit tests (round-trip, bounded-allocation rejection). Clippy clean
  (`-D warnings`). Whole workspace: 50 Rust tests passing (42 prior + 8
  arsc_parser).

## Next Slice
1.3 (binary XML decoder, `core/manifest_decoder` per the blueprint) is the
one remaining open Phase-1 read-only-analysis slice before `apex inspect`
(1.4) becomes buildable — it shares the string-pool format 1.2 just built
(binary XML files embed the same `ResStringPool` chunk for their tag/
attribute-value strings), so `core/arsc_parser::string_pool` should be
reused rather than re-implemented. The `resources.arsc`-fixture aapt2
toolchain path (`pip install aapt2`) is already proven and can produce a
real compiled binary `AndroidManifest.xml` the same way. After that, wire
`ssa::build_ssa` output into an actual IR->Java emitter (the still-open
"Slice 1.7" mentioned in the 1.5 note above), since instructions/CFG/
def-use/SSA are now all real.

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
