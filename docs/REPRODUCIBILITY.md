# APEX Reproducibility

## Golden baseline

```bash
bash scripts/create-golden-apk.sh tests/fixtures/sample_test.apk tests/fixtures/golden-apk-baseline.json
```

Compare regression gate scores against this file in CI or locally.

## SBOM

```bash
python scripts/release/generate_sbom.py sbom.json
```

Uses CycloneDX when `cyclonedx-bom` is installed; otherwise JSON fallback.

## Rust binaries

CI builds with `maturin develop --release`. For bit-identical verification:

```bash
cargo build --release -p apex-zip-reader
# compare with diffoscope (external tool)
```

## Docker (planned)

Multi-stage Docker builds with pinned base image SHA — not shipped in v0.4.11; track in Phase 4.

## Tests

```bash
pytest tests/test_reproducibility.py -q
```
