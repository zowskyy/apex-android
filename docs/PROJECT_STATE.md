# PROJECT_STATE.md — APEX

## Current Phase: Pre-Build (Planning Complete)

## Completed Slices
(none yet)

## Next Slice
0.1 — Project scaffold: Cargo workspace + Python package + PyO3 bridge

## Blockers
- None. Planning is complete. Ready to begin Slice 0.1 in Claude Code.

## Test Corpus
- F-Droid client v1023051 (12.4MB) — round-trip PASS baseline
- NewPipe v0.28.8 (10.9MB) — framework-version FAIL baseline

## Key Decisions
- Tool name: APEX (Android Package EXaminer)
- License: MIT
- Core parsers: Rust (via PyO3)
- CLI + build pipeline: Python
- GUI: deferred to Phase 4
- DEX decompiler: wrap jadx-core initially, replace incrementally
- Resource compiler: wrap aapt2 initially, replace incrementally
