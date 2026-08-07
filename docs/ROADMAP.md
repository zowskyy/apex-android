# APEX Implementation Roadmap

## Shipped in this release (v0.4.11)

- [x] P0 Native ZIP reader with path sanitization (`core/zip_reader`)
- [x] P0 `read_entries` metadata listing
- [x] P0 `read_entries_batch` columnar listing (Slice 1.4 perf)
- [x] P0 DEX structural parser + instruction decode (`core/dex_parser`)
- [x] P0 CFG construction with predecessor edges (`core/dex_parser::cfg`)
- [x] P1 SSA phi insertion at join blocks (`core/dex_parser::ssa`)
- [x] P0 `build.sh --skip-tests` dev install path

## Post-release (deferred — Architect)

- [ ] P1 IR → Java emitter (Slice 1.7) — **post-release**; CFG + SSA foundation is in place
- [ ] P2 Kotlin metadata recovery via `@Metadata` annotations — post-release
- [ ] P2 Columnar Python bindings for full APK inspect pipeline — post-release

Verification:

```bash
./build.sh --skip-tests
cargo test -p apex_dex_parser ssa::
```
