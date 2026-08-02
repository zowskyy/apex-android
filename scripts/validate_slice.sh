#!/usr/bin/env bash
# Mirror .github/workflows/ci.yml locally — run before push.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> validate_slice: mirroring GitHub CI workflow"

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -e ".[dev,mcp]"
pip install maturin
maturin develop --release -m core/zip_reader/Cargo.toml
maturin develop --release -m core/dex_reader/Cargo.toml

.venv/bin/ruff check apex tests
.venv/bin/pytest -q
cargo test --workspace

echo ""
echo "validate_slice: PASS (matches GitHub CI job steps)"
