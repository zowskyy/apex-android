# AGENTS.md

## Cursor Cloud specific instructions

APEX ("Android Package EXaminer") is a **CLI tool + libraries**, not a long-running
service — there is no web server, database, or daemon to start. It has two layers:

- **Python CLI** (`apex/`, package `apex-android`, console script `apex`) — the actual
  product. Entry point is `apex.main` (`apex/__init__.py`). Run via `apex ...` or
  `python -m apex ...`.
- **Rust native core** (Cargo workspace at repo root; crates `core/zip_reader` and
  `core/dex_parser`). `core/zip_reader` is a PyO3 extension (`apex_zip_reader`) built
  with maturin. It provides the security-hardened ZIP extractor; `apex/__init__.py`
  falls back to a pure-Python implementation if the extension is not importable, so
  the CLI still runs without it (just without the Rust-backed path).

### Environment layout (already provisioned by the update script)

- Python deps live in a virtualenv at `.venv/` (Python 3.12). **Activate it first**
  (`. .venv/bin/activate`) or call binaries directly (`.venv/bin/python`,
  `.venv/bin/pytest`, `.venv/bin/apex`). The system Python is externally managed
  (PEP 668), so always use the venv.
- The native extension is installed into `.venv` via `maturin develop`. After editing
  Rust code under `core/zip_reader`, re-run
  `maturin develop --release --manifest-path core/zip_reader/Cargo.toml` (with the venv
  active) to rebuild and reinstall — an editable Python install does NOT pick up Rust
  changes automatically.

### Toolchain gotcha (non-obvious)

The pinned Rust deps in `Cargo.lock` (e.g. `zip 8.6.0`) require **edition 2024**, which
needs **Rust >= 1.85**. The base image's default Rust was 1.83 and fails with a
`feature 'edition2024' is required` error. The default toolchain has been switched to
stable (`rustup default stable`, currently 1.97+); if a build ever fails with that
edition2024 error, run `rustup default stable` again.

### Common commands

- Lint (Rust): `cargo clippy --all-targets -- -D warnings`
- Test (Python): `. .venv/bin/activate && python -m pytest tests/` (auto-generates the
  APK fixture under `tests/fixtures/`)
- Test (Rust): `cargo test`
- Full independent audit of the security slice: `bash scripts/audit_slice_1_1.sh`
- Run the product end to end:
  - `python scripts/generate_test_apk.py /tmp/sample.apk --clean` (creates a synthetic
    APK plus a `_malicious.apk` traversal variant; real APKs are not checked in)
  - `apex analyze /tmp/sample.apk --out /tmp/out` → writes `report.json`, `report.html`,
    and a minimal `bundle/`
  - `apex diff <left report.json> <right report.json>` → semantic dex/class/method diff
