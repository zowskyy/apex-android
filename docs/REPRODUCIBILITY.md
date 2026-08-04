# APEX Reproducibility

## Golden baseline

```bash
bash scripts/create-golden-apk.sh tests/fixtures/sample_test.apk tests/fixtures/golden-apk-baseline.json
```

Compare regression gate scores against this file in CI or locally.

## Lockfiles

| File | Purpose |
|------|---------|
| `Cargo.lock` | Rust workspace — commit and build with `--locked` |
| `requirements.lock` | Pinned Python runtime transitive deps |
| `requirements-dev.lock` | Runtime + pytest / ruff / fastmcp |

Regenerate after dependency bumps:

```bash
bash scripts/generate_lockfiles.sh
```

Install from locks:

```bash
pip install -r requirements.lock
pip install -r requirements-dev.lock
```

Minimum versions remain declared in `pyproject.toml` / `requirements.txt`;
lockfiles pin the resolved tree for CI and Docker.

## Rust MSRV

Workspace `rust-version = "1.74"` (see root `Cargo.toml`). CI and contributors
should use a toolchain at or above MSRV. Native builds:

```bash
maturin develop --release --locked -m core/zip_reader/Cargo.toml
maturin develop --release --locked -m core/dex_reader/Cargo.toml
cargo test --workspace --locked
```

## SBOM

```bash
python scripts/release/generate_sbom.py sbom.json
```

Uses CycloneDX when `cyclonedx-bom` is installed; otherwise JSON fallback.

## Docker

`wrappers/docker/Dockerfile` is multi-stage and:

- Pins `python:3.12-slim-bookworm` by **digest**
- Installs Python deps from `requirements.lock`
- Builds wheels with `maturin build --release --locked`
- Runs the server as non-root user `apex` (uid 10001)

```bash
./build.sh --docker
# or:
docker build -f wrappers/docker/Dockerfile -t apex-android:local .
```

## Tests

```bash
pytest tests/test_reproducibility.py -q
```
