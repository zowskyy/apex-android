#!/usr/bin/env bash
# Bundle APEX release artifacts into release-staging/ (local preflight before tag push).
#
# Usage:
#   bash scripts/bundle_release.sh [version] [--skip-desktop] [--skip-android]
#
# Full GitHub Release (Android + all desktop OS + gate + SBOM + SHA256SUMS):
#   git tag -s vX.Y.Z && git push origin vX.Y.Z
#
# Dry-run CI artifacts (no publish):
#   GitHub Actions → Release → workflow_dispatch → version X.Y.Z-test
set -euo pipefail

VERSION="${1:-0.4.11}"
SKIP_DESKTOP=false
SKIP_ANDROID=false
for arg in "${@:2}"; do
  case "$arg" in
    --skip-desktop) SKIP_DESKTOP=true ;;
    --skip-android) SKIP_ANDROID=true ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> APEX release bundle v${VERSION}"
bash scripts/release/check_version_sync.sh

if [[ "$VERSION" != "$(python3 -c "import re, pathlib; t=pathlib.Path('pyproject.toml').read_text(); print(re.search(r'^version = \"([^\"]+)\"', t, re.M).group(1))")" ]]; then
  echo "bundle_release: version arg ${VERSION} != pyproject.toml — run sync_version.sh first" >&2
  exit 1
fi

mkdir -p dist
echo "==> Building core wheels"
source .venv/bin/activate 2>/dev/null || {
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -q -e ".[dev]" maturin wheel
}
pip install -q maturin wheel
rm -f dist/*.whl
maturin build --release -m core/zip_reader/Cargo.toml -o dist/
maturin build --release -m core/dex_reader/Cargo.toml -o dist/
pip wheel . --no-deps -w dist/
ls -la dist/*.whl

if ! $SKIP_DESKTOP; then
  echo "==> Packaging desktop (linux)"
  export CORE_WHEEL_DIR=dist
  bash scripts/package_desktop_release.sh "$VERSION" linux
  ls -la release-staging/APEX-"${VERSION}"-linux-x64.tar.gz
fi

if ! $SKIP_ANDROID; then
  if [[ -f wrappers/android/dist/apex-mobile.apk ]]; then
    echo "==> Packaging Android"
    bash scripts/package_android_release.sh "$VERSION"
    ls -la release-staging/android/
  else
    echo "==> Android APK missing — build with wrappers/android/build_standalone.sh or use tag push (CI builds Android)"
  fi
fi

echo "==> SBOM"
python scripts/release/generate_sbom.py release-staging/sbom.json

echo "==> Gate sample APK"
python scripts/generate_test_apk.py tests/fixtures/sample_test.apk
apex gate tests/fixtures/sample_test.apk --msv 21 --stage candidate -o release-staging/gate-sample.json

echo ""
echo "Bundle complete: release-staging/"
find release-staging -type f 2>/dev/null | sort || true
echo ""
echo "Next: git tag -s v${VERSION} -m 'APEX v${VERSION}' && git push origin v${VERSION}"
