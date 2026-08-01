# APEX Android Package EXaminer

APEX is a Rust/Python APK inspection and decompilation toolkit. The current
CLI focuses on fast read-only APK metadata, Android binary XML/resource parsing,
safe extraction, and a native DEX-to-Java emitter.

## Install from a checkout

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip maturin

(cd core/zip_reader && maturin develop --release)
(cd core/arsc_parser && maturin develop --release)
(cd core/dex_parser && maturin develop --release)

python -m pip install -e .
```

## Usage

Fast metadata overview without extracting the APK:

```bash
apex inspect app.apk
```

Decompile APK DEX files to Java:

```bash
apex decompile app.apk --out apex_out
```

Decode/extract an APK, convert binary XML files in place, and decompile DEX to
`java/`:

```bash
apex decode app.apk --out apex_out
```

Scan ZIP metadata, manifest strings, and resource strings for path traversal and
common suspicious indicators:

```bash
apex security-scan app.apk
```

Legacy report generation is still available:

```bash
apex analyze app.apk --out apex_out
apex diff old_report.json new_report.json
```

## Benchmarks

See `docs/BENCHMARKS.md` for the real F-Droid/NewPipe measurements from this
branch. The short benchmark runner is:

```bash
python benchmarks/run_benchmarks.py --runs 7 --jadx-apk "NewPipe 0.28.8"
```

Local benchmark APKs/tools/results are intentionally gitignored.
