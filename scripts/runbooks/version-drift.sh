#!/usr/bin/env bash
# Fix version drift — Python pyproject.toml is source of truth.
# Usage:
#   bash scripts/runbooks/version-drift.sh
#   bash scripts/runbooks/version-drift.sh --dry-run
set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python3 <<'PY'
import pathlib, re, sys
root = pathlib.Path(".")
text = (root / "pyproject.toml").read_text(encoding="utf-8")
m = re.search(r'^version = "([^"]+)"', text, flags=re.M)
if not m:
    sys.exit("could not parse pyproject.toml version")
print(m.group(1))
PY

VERSION="$(python3 -c "import re, pathlib; t=pathlib.Path('pyproject.toml').read_text(); print(re.search(r'^version = \"([^\"]+)\"', t, re.M).group(1))")"
echo "==> Truth version from pyproject.toml: ${VERSION}"

if $DRY_RUN; then
  echo "DRY RUN: would run bash scripts/release/sync_version.sh ${VERSION}"
  echo "DRY RUN: would run bash scripts/release/check_version_sync.sh"
  exit 0
fi

bash scripts/release/sync_version.sh "$VERSION"
bash scripts/release/check_version_sync.sh
echo "Version drift fixed."
