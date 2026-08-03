#!/usr/bin/env bash
# Verify pyproject.toml, apex/version.py, and Gradle versionName agree.
# Usage: scripts/release/check_version_sync.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 <<PY
import pathlib, re, sys

root = pathlib.Path("${ROOT}")

pyproject = root / "pyproject.toml"
text = pyproject.read_text(encoding="utf-8")
match = re.search(r'^version = "([^"]+)"', text, flags=re.M)
if not match:
    print("check_version_sync: could not parse pyproject.toml version", file=sys.stderr)
    sys.exit(1)
py_ver = match.group(1)

version_py = root / "apex" / "version.py"
vtext = version_py.read_text(encoding="utf-8")
match = re.search(r'^__version__ = "([^"]+)"', vtext, flags=re.M)
if not match:
    print("check_version_sync: could not parse apex/version.py", file=sys.stderr)
    sys.exit(1)
apex_ver = match.group(1)

gradle = root / "wrappers" / "android" / "standalone" / "app" / "build.gradle"
gtext = gradle.read_text(encoding="utf-8")
match = re.search(r'versionName "([^"]+)"', gtext)
if not match:
    print("check_version_sync: could not parse Gradle versionName", file=sys.stderr)
    sys.exit(1)
gradle_ver = match.group(1)

versions = {
    "pyproject.toml": py_ver,
    "apex/version.py": apex_ver,
    "build.gradle versionName": gradle_ver,
}
unique = set(versions.values())
if len(unique) != 1:
    print("VERSION MISMATCH — sync with scripts/release/sync_version.sh", file=sys.stderr)
    for key, value in versions.items():
        print(f"  {key}: {value}", file=sys.stderr)
    sys.exit(1)

print(f"Version sync OK: {py_ver}")
PY
