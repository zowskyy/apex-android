#!/usr/bin/env bash
# Sync release version across Python metadata and Android Gradle.
# Usage: scripts/release/sync_version.sh <version>   e.g. 0.4.11 or 0.4.11-test
set -euo pipefail

VERSION="${1:?version required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCKFILE="$ROOT/.version-sync.lock"

exec 200>"$LOCKFILE"
if ! flock -n 200; then
  echo "sync_version: another sync is in progress (lock: $LOCKFILE)" >&2
  exit 1
fi

python <<PY
import pathlib, re

version = "${VERSION}"
numeric = version.split("-", 1)[0]
parts = numeric.split(".")
while len(parts) < 3:
    parts.append("0")
major, minor, patch = (int(p) for p in parts[:3])
version_code = major * 10000 + minor * 100 + patch

root = pathlib.Path("${ROOT}")

pyproject = root / "pyproject.toml"
text = pyproject.read_text(encoding="utf-8")
pyproject.write_text(
    re.sub(r'^version = ".*"', f'version = "{version}"', text, count=1, flags=re.M),
    encoding="utf-8",
)

version_py = root / "apex" / "version.py"
vtext = version_py.read_text(encoding="utf-8")
version_py.write_text(
    re.sub(r'^__version__ = ".*"', f'__version__ = "{version}"', vtext, count=1, flags=re.M),
    encoding="utf-8",
)

gradle = root / "wrappers" / "android" / "standalone" / "app" / "build.gradle"
gtext = gradle.read_text(encoding="utf-8")
gtext = re.sub(r'versionName ".*"', f'versionName "{version}"', gtext, count=1)
gtext = re.sub(r"versionCode \d+", f"versionCode {version_code}", gtext, count=1)
gradle.write_text(gtext, encoding="utf-8")

print(f"Synced version {version} (versionCode {version_code})")
PY
