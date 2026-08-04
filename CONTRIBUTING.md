# Contributing to APEX

Thanks for helping improve APEX. This guide covers the local loop from clone to
a reviewable pull request.

## Prerequisites

- Python 3.10+
- Rust toolchain at or above the workspace **MSRV** (`rust-version = "1.74"` in
  root `Cargo.toml`)
- Optional: Android SDK (for mobile APK builds), Docker (for the container image)

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
./build.sh --skip-tests          # install + native extensions
# or full check:
./build.sh
```

Pinned dependency installs (optional, for reproducible environments):

```bash
pip install -r requirements.lock          # runtime
pip install -r requirements-dev.lock      # runtime + pytest/ruff/mcp
```

Regenerate lockfiles after dependency bumps:

```bash
bash scripts/generate_lockfiles.sh
```

## Development commands

```bash
ruff check apex tests
pytest -q
cargo test --workspace --locked
./build.sh --verbose --skip-tests   # noisy install/build diagnostics
apex -v doctor                      # CLI INFO logging
```

Before opening a PR:

```bash
bash scripts/validate_slice.sh
# or the full hard gate:
bash scripts/hard_gate.sh
```

## Pull requests

1. Branch from `master` with a focused change set.
2. Wire CLI / web / tests / docs when the change spans those layers.
3. Update `CHANGELOG.md` under **Unreleased** for user-visible changes.
4. Keep commits reviewable; prefer descriptive messages over noisy WIP stacks.
5. Do not claim CI is green until GitHub Actions succeeds on the pushed `HEAD`.

## Code style

- Python: `ruff` (see `pyproject.toml`)
- Rust: `edition = "2021"`, respect MSRV, keep `Cargo.lock` committed
- Prefer end-to-end wiring over orphan modules

## Security reports

Do not open public issues for undisclosed vulnerabilities. See
[SECURITY.md](SECURITY.md) / [docs/SECURITY.md](docs/SECURITY.md).

## Conduct

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
